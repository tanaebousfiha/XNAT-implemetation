'''
This script is desingned to achied a automatisation of xnat container sevice.
The skript folows different steps to achieve this purpose:
1.ask the users tor the input of the external skript 
2.create a Dockerfile with the skript and the base name of the docker image 
3. build the docker image and tag it and pushe it to the docker hub 
4.create a command json file with theh docker image and the skript name
now we start using REST APIS from xnat to upload the command json file
5.send the command json file to xnat 
6.get the command id from xnat 
7.get the wrapper id from xnat or create a new wrapper if it does not exist
8.enable the wrapper sitewide and for the project
9.get the input file from the session
10.launch the container with the input file and the wrapper
this script is desingned to achied a automatisation of xnat container sevice
---------------------------------------------------------------------------------------------------------------------------------
to use the skript you need to have the following requirements:
1. Docker installed and running
2. Python 3.10 or higher installed
3. XNAT server running and accessible with admin rights 
4. Docker hub account to push the image
5. An external python skript that you want to run in the container
>>The script must be a valid python script with the .py extension
'''

#-----------------Bibliotheken----------------------------------------------------------------------------------------------------------------------------
import json # wir brauchen json für xnat damit er den Command anlegen kann
import requests  # # für die Kommunikation mit der XNAT-API
import os #Arbeiten mit Dateien und Pfaden
import subprocess  # # für die Ausführung von Docker-Befehlen
import getpass #Passwort-Eingabe im Terminal ohne Anzeige
import sys#Für sys.exit() bei Fehlern
import urllib3#Wird von requests genutzt – hier zur Abschaltung von SSL-Warnungen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)# Deaktiviert SSL-Warnungen, wenn XNAT ohne gültiges Zertifikat läuft


#-----------------------------------dockerfile ausfüllen------------------------------------------------------
#hier wird die dockerfile erstellt und mit dem Skript und erfüllt
def write_dockerfile(docker_dir, script_filename, docker_base_image):
    dockerfile_content = f"""FROM {docker_base_image}

WORKDIR /app# Setze das Arbeitsverzeichnis im Container
COPY {script_filename} /app/{script_filename}
RUN pip install pandas # Installiere benötigte Python-Pakete
""" 
    os.makedirs(docker_dir, exist_ok=True)# # Erstelle das Verzeichnis, falls es nicht existiert
    dockerfile_path = os.path.join(docker_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:# # Schreibe den Inhalt in die Dockerfile
        f.write(dockerfile_content)
    print(f"Dockerfile written to {dockerfile_path}")
    return dockerfile_path

#CMD weglassen>>Fehler entsteht(runing contaienr in xnat),weil im Dockerfile und in der command.json "python3" jeweils als Prefix stehen und es dadurch zu einer doppelten Übergabe kommt.

#--------------------------------------Image bauen>>pushen>>taggen --------------------------------------

def build_and_push_docker_image(dockerfile_path, docker_image_name):

    dockerhub_username = input("Docker Hub username (to push the image): ").strip()
    if not dockerhub_username:
        print("No Docker Hub username provided. Skipping push.")
        return docker_image_name  # 

    #>>Ersat form zum : docker build -f Dockerfile -t docker_image_name .
    print(f"Building Docker image '{docker_image_name}'...")
    build_result = subprocess.run(["docker", "build", "-f", dockerfile_path, "-t", docker_image_name, "."],  capture_output=True, text=True)
    if build_result.returncode != 0:
        print(f"Build failed:\n{build_result.stderr}")
        sys.exit(1)
    print(f"Image '{docker_image_name}' built successfully.")


 
    full_tag = f"{dockerhub_username}/{docker_image_name}"
    print(f"Tagging image as '{full_tag}'...")
    tag_result = subprocess.run(["docker", "tag", docker_image_name, full_tag], capture_output=True, text=True)
    if tag_result.returncode != 0:
        print(f"Tagging failed:\n{tag_result.stderr}")
        sys.exit(1)

    print(f"Pushing image to Docker Hub as '{full_tag}'...")
    push_result = subprocess.run(["docker", "push", full_tag], capture_output=True, text=True)
    if push_result.returncode != 0:
        print(f"Push failed:\n{push_result.stderr}")
        sys.exit(1)

    print(f"Image successfully pushed: {full_tag}")
    return full_tag  


#-----------------------------------User-Input-----------------------------------------
#prepare th e input for the json command 
def get_input(prompt):
    while True:
        value = input(prompt)
        if value.strip():
            return value
        else:
            print("Cannot be empty.")

def modification():
    data = {}
    name = get_input("What is the name of the command in XNAT: ")
    description = get_input("What is the description of the command in XNAT: ")
    data["command_name"] = name
    data["command_description"] = description
    data["label_name"] = name
    data["label_description"] = description

    context_options = [
        ("xnat:subjectData", "Subject-Ebene (Patientenebene)"),
        ("xnat:mrSessionData", "MRI-Session-Ebene (häufigste Session-Ebene)"),
        ("xnat:petSessionData", "PET-Session-Ebene"),
        ("xnat:ctSessionData", "CT-Session-Ebene"),
        ("xnat:sessionData", "Allgemeine Session (für alle Modalitäten)"),
        ("xnat:imageScanData", "Scan-Ebene innerhalb einer Session"),
        ("xnat:resource", "Resource-Ebene (z. B. für Datei-Uploads direkt)"),
        ("xnat:projectData", "Projekt-Ebene"),
    ]
    print("\nWähle einen oder mehrere Kontexte (durch Komma getrennt):")
    for idx, (ctx, desc) in enumerate(context_options, 1):
        print(f"{idx}: {ctx} - {desc}")
    while True:
        ctx_input = input("Nummern eingeben (z.B. 2,5): ")
        try:
            indices = [int(i.strip()) for i in ctx_input.split(",") if i.strip()]
            if not indices or any(i < 1 or i > len(context_options) for i in indices):
                raise ValueError
            data["contexts"] = [context_options[i-1][0] for i in indices]
            break
        except Exception:
            print("Ungültige Eingabe. Bitte erneut versuchen.")

    return data

# es wiederholt sich weil in der jsoncommand muss mehr als eine varial geschreiben werden
#und ich wollte nicht dass der user meher mals etwas ähnliches schreibt, deshalb habe ich es so gemacht
#-----------------------------------json File erstellen-------------------------------
def create_json_file(docker_image, script_filename, mod_data):
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"#ersetz leere zeichen durch _>wandelt die kleinbuchstaben um>hängt dem Suffix wrapper am Ende an  
    json_file = {
        "name": mod_data["command_name"],
        "description": mod_data["command_description"],
        "version": "1.5",
        "type": "docker",
        "image": docker_image,
        "command-line": f"python3 /app/{script_filename} /input/#input_file# /output",
        "mounts": [
            {"name": "input", "path": "/input", "writable": False},
            {"name": "output", "path": "/output", "writable": True}
        ],
        "inputs": [
            {
                "name": "input_file",
                "type": "file",
                "required": True,
                "description": "Input file for analysis",
                "mount": "input"
            }
        ],
        "outputs": [
            {
                "name": "result_file",
                "type": "file",
                "description": "Result file output",
                "mount": "output",
                "path": "result.csv"
            }
        ],
        "xnat": [
            {
                "name": wrapper_name,
                "label": mod_data["label_name"],
                "description": mod_data["label_description"],
                "contexts": mod_data["contexts"],
                "external-inputs": [
                    {
                        "name": "session",
                        "type": "Session",
                        "required": True
                    }
                ],
                "output-handlers": [
                    {
                        "name": "output",
                        "accepts-command-output": "result_file",
                        "as-a-child-of": "session",
                        "type": "Resource",
                        "label": "Results",
                        "format": "csv"
                    }
                ]
            }
        ]
    }

    with open("command.json", "w") as json_out:
        json.dump(json_file, json_out, indent=4)
        print(" Corrected command.json created.")
    return "command.json"
#-------------------------------------------json modelanlegen------------------------------------------------



#---------------------Command zu XNAT senden------------------------------------------

def send_json_to_xnat(json_file_path, xnat_url, xnat_user, xnat_password): 

    url = f"{xnat_url}/xapi/commands"
    print(f"Uploading command to {url}")
    with open(json_file_path, "r") as f:
        response = requests.post(url, auth=(xnat_user, xnat_password), json=json.load(f))
    if response.status_code == 200:
        print("Command uploaded successfully.")
    elif response.status_code == 201:
        print("Command created successfully.")
    elif response.status_code == 409:
        print("Command already exists.")
    else:
        print(f"Failed to upload command: {response.status_code} - {response.text}")

#-----------------------------------Command-Liste-------------------------------------

def get_command_id_by_name(xnat_host, xnat_user, xnat_password, command_name):
    url = f"{xnat_host.rstrip('/')}/xapi/commands"#Baut die vollständige URL zur Command-Liste der XNAT REST-API>>keinen doppelten Schrägstrich gibt
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)# wird hier die get me request benutzt laut der APIS 
    if resp.status_code != 200:
        print(f"Error fetching commands: {resp.status_code}")
        sys.exit(1)
    data = resp.json()# # Die Antwort wird als JSON interpretiert
    if isinstance(data, dict) and "commands" in data:
        command_list = data["commands"]# # Wenn die Antwort ein Dictionary ist, das "commands" enthält, dann wird es extrahiert
    else:
        command_list = data
    for command in command_list:
        if command.get("name") == command_name:
            return command["id"]
    print("Command not found.")
    sys.exit(1)

#----------------------Wrapper auslesen/erstellen-------------------------------------
def get_command_io(xnat_host, xnat_user, xnat_password, command_id):
    url = f"{xnat_host.rstrip('/')}/xapi/commands/{command_id}"#url wird zusammengebaut, um die spezifischen Informationen für den Command zu erhalten
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)#GET-Anfrage an die XNAT-API gesendet
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen des Commands: {resp.status_code}")
        sys.exit(1)# # Überprüfen des Statuscodes der Antwort
    cmd = resp.json()# # Die Antwort wird als JSON interpretiert
    outputs = cmd.get("outputs", [])# # Extrahieren der Outputs aus dem Command
    external_inputs = []# # Initialisieren der externen Inputs
    derived_inputs = []# # Initialisieren der abgeleiteten Inputs
    for wrapper in cmd.get("xnat", []):# # Durchlaufen der "xnat"-Sektion des Commands
        external_inputs = wrapper.get("external-inputs", [])
        derived_inputs = wrapper.get("derived-inputs", [])
        break  # Nur den ersten Wrapper verwenden
    return outputs, external_inputs, derived_inputs# # Rückgabe der Outputs, externen Inputs und abgeleiteten Inputs
#--------------------------------------

def get_wrapper_id_by_command_name(xnat_host, xnat_user, xnat_password, command_name, wrapper_name):
    """
    Gibt die Wrapper-ID zurück, die zu einem gegebenen Command-Namen gehört.
    Falls kein Wrapper gefunden wird, wird das Skript beendet.
    """
    url = f"{xnat_host.rstrip('/')}/xapi/commands"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Commands: {resp.status_code}")
        sys.exit(1)

    data = resp.json()
    if isinstance(data, dict) and "commands" in data:
        commands = data["commands"]
    else:
        commands = data

    for command in commands:
        if command.get("name") == command_name:
            for wrapper in command.get("xnat", []):
                if wrapper.get("name") == wrapper_name:
                    return wrapper.get("id") or wrapper_name
            for wrapper in command.get("wrappers", []):
                if wrapper.get("name") == wrapper_name:
                    return wrapper.get("id") or wrapper_name

    print("Kein Wrapper für diesen Command gefunden.")
    sys.exit(1)


#----------------------Wrapper Aktivierung---------------------------------------------


def enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password):
    """
    Aktiviert den Wrapper global (für alle Projekte).
    """
    url = f"{xnat_host.rstrip('/')}/xapi/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde global aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits global aktiviert.")
    else:
        print(f"Fehler beim globalen Aktivieren: {resp.status_code} - {resp.text}")


def enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password):
    """
    Aktiviert den Wrapper für ein bestimmtes Projekt.
    """
    url = f"{xnat_host.rstrip('/')}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde im Projekt '{project_id}' aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits im Projekt aktiviert.")
    else:
        print(f"Fehler beim Aktivieren für das Projekt: {resp.status_code} - {resp.text}")

#-----------------------------------------------------------------------------------
def get_input_file_from_session(xnat_host, session_id, xnat_user, xnat_password):
    """
    Fragt XNAT nach allen Dateien in der gegebenen Session (egal ob CSV oder anderes Format),
    zeigt sie dem Benutzer zur Auswahl, und gibt den ausgewählten Dateinamen zurück.
    """
    url = f"{xnat_host.rstrip('/')}/data/experiments/{session_id}/resources"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Ressourcen: {resp.status_code}")
        return None

    resources = resp.json()["ResultSet"]["Result"]
    all_files = []

    for resource in resources:
        res_label = resource["label"]
        file_url = f"{xnat_host.rstrip('/')}/data/experiments/{session_id}/resources/{res_label}/files"
        file_resp = requests.get(file_url, auth=(xnat_user, xnat_password), verify=False)
        if file_resp.status_code != 200:
            continue

        files = file_resp.json()["ResultSet"]["Result"]
        for f in files:
            all_files.append({
                "name": f["Name"],
                "uri": f"/data/experiments/{session_id}/resources/{res_label}/files/{f['Name']}",
                "resource": res_label
            })

    if not all_files:
        print("Keine Dateien gefunden.")
        return None

    # Benutzer wählt Datei aus
    print("\nVerfügbare Dateien:")
    for idx, f in enumerate(all_files):
        print(f"{idx + 1}: {f['name']} (Resource: {f['resource']})")

    while True:
        choice = input("Welche Datei soll verwendet werden? Gib die Nummer ein: ")
        if choice.isdigit() and 1 <= int(choice) <= len(all_files):
            selected = all_files[int(choice) - 1]
            print(f"Ausgewählte Datei: {selected['name']}")
            return selected
        else:
            print("Ungültige Auswahl.")


#---------------------Bulklaunch----------------------------------------
def launch_container_rest(xnat_host, project_id, command_id, wrapper_name, session_id, xnat_user, xnat_password, input_file_info):

    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/root/session/launch"
    headers = {"Content-Type": "application/json"}

    # Beispiel: resources/CSV/files/correct_patient.csv
    input_file_path = f"resources/{input_file_info['resource']}/files/{input_file_info['name']}"

    payload = {
        "session": f"/experiments/{session_id}",
        "input_file": input_file_path,
        "project": project_id
    }

    print("Launching container with payload:")
    print(json.dumps(payload, indent=2))

    response = requests.post(
        url,
        auth=(xnat_user, xnat_password),
        headers=headers,
        json=payload,
        verify=False
    )

    if response.status_code in [200, 201, 202]:
        print("Container launched successfully via REST.")
        print(response.text)
    else:
        print(f"Failed to launch container via REST: {response.status_code} - {response.text}")

#----------------------------------------------------------------------------------




#-----------------------------------------------Main Teil-----------------------------------------------

def main():
    xnat_host = "https://xnat-dev.gwdg.de"
    docker_base_image = "python:3.10"

    xnat_user = get_input("XNAT Username: ")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID: ").strip()
    session_id = get_input("Session ID: ").strip()
    script_path = get_input("Path to the Python script: ")


    mod_data = modification()
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # Step 1: Dockerfile
    dockerfile_path = write_dockerfile(".", os.path.basename(script_path), docker_base_image)

    # Step 2: Docker image name
    local_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}:latest"

    # Step 3: Build and push image
    full_image_name = build_and_push_docker_image(dockerfile_path, local_image_name)

    # Step 4: Generate command.json
    json_file_path = create_json_file(full_image_name, os.path.basename(script_path), mod_data)
    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)

    # Step 5: Get command ID
    command_id = get_command_id_by_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"])

    # Step 6: Create or fetch wrapper
    wrapper_id = None
    try:
        wrapper_id = get_wrapper_id_by_command_name(
            xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name
        )
        print(f"Wrapper already exists: {wrapper_id}")
    except SystemExit:
        print("Wrapper not found, creating...")
        outputs, external_inputs, derived_inputs = get_command_io(
            xnat_host, xnat_user, xnat_password, command_id
        )

    # Step 7: Enable wrapper
    enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password)
    enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password)

    # Step 8: Select input file from session
    input_file_info = get_input_file_from_session(xnat_host, session_id, xnat_user, xnat_password)

    # Step 9: Launch container
    if input_file_info:
        launch_container_rest(xnat_host, project_id, command_id, wrapper_name, session_id, xnat_user, xnat_password, input_file_info)

    else:
        print("No input file selected. Aborting container launch.")

if __name__ == "__main__":
    main()


#Quellen:
'''
https://wiki.xnat.org/container-service/container-service-api
https://www.datacamp.com/tutorial/python-subprocess
Docker ofiziel Dokumentation>https://docs.docker.com/engine/reference/commandline/build/
with open write>>https://docs.python.org/3/library/functions.html#open
Dockerinhlat>>https://docs.docker.com/reference/dockerfile/#from
https://docs.docker.com/reference/dockerfile/#workdir
https://docs.docker.com/reference/dockerfile/#copy
https://docs.docker.com/reference/dockerfile/#run
https://docs.docker.com/build/building/best-practices/
https://docs.python.org/3/library/subprocess.html#subprocess.run
https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess.returncode
https://docs.docker.com/reference/cli/docker/image/tag/
https://docs.docker.com/reference/cli/docker/image/push/
https://wiki.xnat.org/container-service/json-command-definition

#here is the APIS XNAT dokumentation 
#https://wiki.xnat.org/container-service/container-service-api
#https://wiki.xnat.org/container-service/container-command-json
https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status
https://requests.readthedocs.io/en/latest/user/quickstart/#make-a-request
https://wiki.xnat.org/container-service/container-service-api#ContainerServiceAPI-Commands
https://wiki.xnat.org/container-service/container-service-api#ContainerServiceAPI-Commands

'''