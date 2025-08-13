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
import requests  # type: ignore # # für die Kommunikation mit der XNAT-API
import os #Arbeiten mit Dateien und Pfaden
import subprocess  # # für die Ausführung von Docker-Befehlen
import getpass #Passwort-Eingabe im Terminal ohne Anzeige
import sys#Für sys.exit() bei Fehlern
import urllib3# type: ignore #Wird von requests genutzt – hier zur Abschaltung von Warnungen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)# Deaktiviert SSL-Warnungen, wenn XNAT ohne gültiges Zertifikat läuft


#-----------------------------------1)dockerfile ausfüllen------------------------------------------------------

#hier wird die dockerfile erstellt und mit dem Skript und erfüllt
def write_dockerfile(docker_dir, script_filename, docker_base_image="python:3.10-slim"):
    dockerfile_content = f"""FROM {docker_base_image}

WORKDIR /app
COPY {script_filename} /app/{script_filename}
RUN pip install --no-cache-dir pandas
"""
    #no cache dir um wenig Platz zu sparen 

    os.makedirs(docker_dir, exist_ok=True)
    dockerfile_path = os.path.join(docker_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile written to {dockerfile_path}")
    return dockerfile_path

#CMD weglassen>>Fehler entsteht(runing contaienr in xnat),weil im Dockerfile und in der command.json "python3" jeweils als Prefix stehen und es dadurch zu einer doppelten Übergabe kommt.

#--------------------------------------2)Image bauen>>pushen>>taggen --------------------------------------

def build_and_push_docker_image(dockerfile_path, docker_image_name):

    dockerhub_username = input("Docker Hub username (to push the image): ").strip()
    if not dockerhub_username:
        print("No Docker Hub username provided. Skipping push.")
        return docker_image_name  

    #>>Ersat form zum : docker build -f Dockerfile -t docker_image_name .
    print(f"Building Docker image '{docker_image_name}'...")
    build_result = subprocess.run(["docker", "build", "-f", dockerfile_path, "-t", docker_image_name, "."],  capture_output=True, text=True)
    if build_result.returncode != 0:
        print(f"Build failed:\n{build_result.stderr}")
        sys.exit(1)
    print(f"Image '{docker_image_name}' built successfully.")

# docker build -t image name  .
#https://stackoverflow.com/questions/61090027/how-to-run-a-docker-volume-mount-as-a-python-subprocess

 #-------------------------------/Tagen/-------------------------------------------------------------------------------
    full_tag = f"{dockerhub_username}/{docker_image_name}"#/>Trennung Benutzername und Image-Name.
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

#docker tag imagename 
#docker push imagename 
#-----------------------------------3)User-Input----------------------------------------- -----------------------------------------   

#prepare the input for the json command :https://www.digitalocean.com/community/tutorials/how-to-receive-user-input-python
def get_input(prompt):
    while True:
        value = input(prompt)
        if value.strip():
            return value
        else:
            print("Cannot be empty.")

def modification():
    context_options = [
        ("xnat:subjectData", "Subject-Ebene (Patientenebene)"),
        ("xnat:mrSessionData", "MRI-Session-Ebene (häufigste Session-Ebene)"),
        ("xnat:petSessionData", "PET-Session-Ebene"),
        ("xnat:ctSessionData", "CT-Session-Ebene"),
        ("xnat:sessionData", "Allgemeine Session (für alle Modalitäten)"),
        ("xnat:imageScanData", "Scan-Ebene innerhalb einer Session"),
        ("xnat:resource", "Resource-Ebene (z.B. für Datei-Uploads direkt)"),
        ("xnat:projectData", "Projekt-Ebene"),
    ]
    print("\nWähle einen Kontext:")#https://www.coursera.org/tutorials/enumerate-python
    for i, (context, options) in enumerate(context_options, 1):
        print(f"{i} : {context},{options}")
    while True:
        context_input = input("Nummer eingeben: ")
        try:
            i = int(context_input.strip())
            if i < 1 or i > len(context_options):
                raise ValueError
            selected_context = context_options[i-1][0]
            break
        except Exception:
            print("Ungültige Eingabe. Bitte erneut versuchen.")

    # Zusätzliche Eingaben einholen:
    command_name = input("Name des Commands: ")
    command_description = input("Beschreibung des Commands: ")
    
    # Ausgabe oder Rückgabe eines Dictionaries mit den Werten
    return {
        "selected_context": selected_context,
        "command_name": command_name,
        "command_description": command_description
    }

# es wiederholt sich weil in der jsoncommand muss mehr als eine varial geschreiben werden
#und ich wollte nicht dass der user mehr mals etwas ähnliches schreibt, deshalb habe ich es so gemacht
#-----------------------------------4)json File erstellen-------------------------------

def create_json_file(docker_image, script_filename, mod_data):
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # Mapping Kontext >>external-input + as-a-child-of
    context_mappings = {
        "xnat:projectData": {"input_name": "project", "input_type": "Project", "child_of": "project"},
        "xnat:subjectData": {"input_name": "subject", "input_type": "Subject", "child_of": "subject"},
        "xnat:mrSessionData": {"input_name": "session", "input_type": "Session", "child_of": "session"},
        "xnat:petSessionData": {"input_name": "session", "input_type": "Session", "child_of": "session"},
        "xnat:ctSessionData": {"input_name": "session", "input_type": "Session", "child_of": "session"},
        "xnat:sessionData": {"input_name": "session", "input_type": "Session", "child_of": "session"},
        "xnat:imageScanData": {"input_name": "scan", "input_type": "Scan", "child_of": "scan"},
        "xnat:resource": {"input_name": "resource", "input_type": "Resource", "child_of": "resource"},
    }

    # Dynamische Listen
    external_inputs = []
    output_handlers = []
    used_inputs = set()  # Duplikate vermeiden

    for context in mod_data["contexts"]:
        mapping = context_mappings.get(context)
        if not mapping:
            continue  # unbekannter Kontext wird übersprungen

        # External input nur einmal pro Name
        input_key = (mapping["input_name"], mapping["input_type"])
        if input_key not in used_inputs:
            external_inputs.append({
                "name": mapping["input_name"],
                "type": mapping["input_type"],
                "required": True
            })
            used_inputs.add(input_key)

        output_handlers.append({
            "name": "output",
            "accepts-command-output": "result_file",
            "as-a-child-of": mapping["child_of"],
            "type": "Resource",
            "label": "Results",
            "format": "csv"
        })

    # JSON zusammenbauen
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
                "external-inputs": external_inputs,
                "output-handlers": output_handlers
            }
        ]
    }

    with open("command.json", "w") as json_out:
        json.dump(json_file, json_out, indent=4)
        print(" Corrected command.json created.")
    return "command.json"

#---------------------5)Command zu XNAT senden------------------------------------------

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

#-----------------------------------6)Command-Liste------------------------------------------------------------------------------------------------------------

def get_command_id_by_name(xnat_host, xnat_user, xnat_password, command_name):
    url = f"{xnat_host.rstrip('/')}/xapi/commands"#Baut die vollständige URL zur Command-Liste der XNAT REST-API>>keinen doppelten Schrägstrich gibt
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)# wird hier die get me request benutzt laut der APIS 
    if resp.status_code != 200:
        print(f"Error fetching commands: {resp.status_code}")
        sys.exit(1)
    data = resp.json()# # Die Antwort wird als JSON interpretiert
    if isinstance(data, dict) and "commands" in data:#do the check if the the variable a dictionnar ist 
        command_list = data["commands"]# # Wenn die Antwort ein Dictionary ist, das "commands" enthält, dann wird es extrahiert
    else:
        command_list = data
    for command in command_list:
        if command.get("name") == command_name:
            return command["id"]
    print("Command not found.")
    sys.exit(1)

#-------------------------------------- 8)get_wrapper_id_by_command_name---------------------------------------------------------------------------------

def get_wrapper_id_by_command_name(xnat_host, xnat_user, xnat_password, command_name, wrapper_name):
    
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

#----------------------9)Wrapper Aktivierung---------------------------------------------


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

#----------------------------------------10)get_input_file-------------------------------------------
#Je nachdem, welcher Kontext gewählt wird, wird die Datei aus diesem Kontext geholt. 

def get_input_files(xnat_host, entity_id, entity_type, xnat_user, xnat_password, scan_id=None):
    """
    Gibt alle Dateien vom angegebenen XNAT-Objekt zurück (OHNE Benutzerauswahl).
    """
    
    if entity_type == "project":
        base_url = f"{xnat_host.rstrip('/')}/data/projects/{entity_id}/resources"
    elif entity_type == "subject":
        base_url = f"{xnat_host.rstrip('/')}/data/subjects/{entity_id}/resources"
    elif entity_type in ["session", "experiment"]:
        base_url = f"{xnat_host.rstrip('/')}/data/experiments/{entity_id}/resources"
    elif entity_type == "scan" and scan_id:
        base_url = f"{xnat_host.rstrip('/')}/data/experiments/{entity_id}/scans/{scan_id}/resources"
    else:
        print("Unbekannter oder nicht unterstützter Entitätstyp.")
        return []

    resp = requests.get(base_url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Ressourcen ({entity_type}): {resp.status_code}")
        return []

    resources = resp.json().get("ResultSet", {}).get("Result", [])
    all_files = []
    for resource in resources:
        res_label = resource["label"]
        file_url = f"{base_url}/{res_label}/files"
        file_resp = requests.get(file_url, auth=(xnat_user, xnat_password), verify=False)
        if file_resp.status_code != 200:
            continue

        files = file_resp.json().get("ResultSet", {}).get("Result", [])
        for f in files:
            all_files.append({
                "name": f["Name"],
                "uri": f"{base_url}/{res_label}/files/{f['Name']}",
                "resource": res_label
            })
    return all_files
#------------------------------------------------- Entities auflisten und auswählen lassen----------------------------
def select_data(entities, id_key="ID", name_key="label"):
    if not entities:
        print("Keine Datei gefunden.")
        return None
    print("Verfügbare Dateis:")
    for idx, entity in enumerate(entities, 1):
        print(f"{idx}: {entity.get(id_key, '---')} ({entity.get(name_key, '')})")
    while True:
        choice = input(f"Wähle eine Data (1-{len(entities)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(entities):
            return entities[int(choice)-1]
        print("Ungültige Auswahl!")
#-------------------------------------------------------Datei-Auswahl-Menü-----------------------------
def select_files_from_list(all_files):
    if not all_files:
        print("Keine Dateien gefunden.")
        return []
    print("Verfügbare Dateien:")
    for idx, f in enumerate(all_files, 1):
        print(f"{idx}: {f['name']} [Resource: {f['resource']}]")
    while True:
        choice = input("Welche Datei(en) sollen verwendet werden? Gib Nummern ein (z.B. 1,3,5): ")
        indices = [c.strip() for c in choice.split(",") if c.strip()]
        if all(i.isdigit() and 1 <= int(i) <= len(all_files) for i in indices):
            unique_indices = list(set(int(i) for i in indices))
            selected = [all_files[i-1] for i in unique_indices]
            print("Ausgewählt:")
            for s in selected:
                print(f"- {s['name']}")
            return selected
        print("Ungültige Auswahl.")
 #---------------------------------sessions_for_project---------------------------------------------
        
def get_sessions_for_project(xnat_host, project_id, xnat_user, xnat_password):
    """
    Listet alle Sessions (Experimente) für ein Projekt auf.
    """
    url = f"{xnat_host.rstrip('/')}/data/projects/{project_id}/experiments?format=json"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Sessions für Projekt {project_id}: {resp.status_code}")
        return []
    return resp.json().get("ResultSet", {}).get("Result", [])

#---------------------------------------------------------------------------------------------------------
def get_subjects_for_project(xnat_host, project_id, xnat_user, xnat_password):
    url = f"{xnat_host.rstrip('/')}/data/projects/{project_id}/subjects?format=json"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Subjects für Projekt {project_id}: {resp.status_code}")
        return []
    return resp.json().get("ResultSet", {}).get("Result", [])

def get_scans_for_session(xnat_host, session_id, xnat_user, xnat_password):
    url = f"{xnat_host.rstrip('/')}/data/experiments/{session_id}/scans?format=json"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Scans für Session {session_id}: {resp.status_code}")
        return []
    return resp.json().get("ResultSet", {}).get("Result", [])
#---------------------11)Lanch Container------------------------------------------------------------------

def launch_container_rest(xnat_host, project_id, command_id, wrapper_name,
                          entity_id, xnat_user, xnat_password, input_file_info,
                          entity_type="session", scan_id=None):

    headers = {"Content-Type": "application/json"}#Server>>Der Inhalt (body) dieser Anfrage ist im JSON-Format 
   

    root_path_mapping = {
        "session": "session",
        "subject": "subject",
        "project": "project",
        "scan": "scan"
    }

    root_type = root_path_mapping.get(entity_type)
    if not root_type:
        print(f"Containerstart für entity_type '{entity_type}' wird nicht unterstützt.")
        return

    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/root/{root_type}/launch"

    input_file_path = f"resources/{input_file_info['resource']}/files/{input_file_info['name']}"

    if entity_type == "scan":
        if not scan_id:
            print("Scan-ID fehlt für den Scan-Kontext.")
            return
        xnat_entity_path = f"/experiments/{entity_id}/scans/{scan_id}"
    elif entity_type == "session":
        xnat_entity_path = f"/experiments/{entity_id}"
    elif entity_type == "subject":
        xnat_entity_path = f"/subjects/{entity_id}"
    elif entity_type == "project":
        xnat_entity_path = f"/projects/{entity_id}"
    else:
        print("Unbekannter entity_type. Abbruch.")
        return

    payload = {
        root_type: xnat_entity_path,
        "input_file": input_file_path,
        "project": project_id
    }

    print("Launching container :")
    print(json.dumps(payload, indent=2))

    response = requests.post(
        url,
        auth=(xnat_user, xnat_password),
        headers=headers,
        json=payload,
        verify=False
    )

    if response.status_code in [200, 201, 202]:
        print("Container wurde erfolgreich über die REST-API gestartet.")
        print(response.text)
    else:
        print(f"Fehler beim Containerstart ({response.status_code}):")
        print(response.text)

#-----------------------------------------------Main Teil-----------------------------------------------


def main():
   
    xnat_host = "https://xnat-dev.gwdg.de"
    docker_base_image = "python:3.10"

    xnat_user = get_input("XNAT Username: ")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID: ").strip()
    script_path = get_input("Path to the Python script: ")

    # Step 1: Gather Command/Wrapper Data
    mod_data = modification()
    mod_data["contexts"] = [mod_data["selected_context"]]
    mod_data["label_name"] = mod_data["command_name"]
    mod_data["label_description"] = mod_data["command_description"]
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # Step 2: Prepare and upload Docker image and command
    dockerfile_path = write_dockerfile(".", os.path.basename(script_path), docker_base_image)
    local_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}:latest"
    full_image_name = build_and_push_docker_image(dockerfile_path, local_image_name)

    json_file_path = create_json_file(full_image_name, os.path.basename(script_path), mod_data)
    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)

    command_id = get_command_id_by_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"])

    try:
        wrapper_id = get_wrapper_id_by_command_name(
            xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name
        )
        print(f"Wrapper already exists: {wrapper_id}")
    except SystemExit:
        print("Wrapper not found")
 
        
    enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password)
    enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password)

    CONTEXT_ENTITY_MAPPING = {
        "xnat:projectData": {"entity_type": "project", "id_label": "Project ID"},
        "xnat:subjectData": {"entity_type": "subject", "id_label": "Subject ID"},
        "xnat:mrSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:petSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:ctSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:sessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:imageScanData": {"entity_type": "scan", "id_label": "Session ID + Scan ID"},
        "xnat:resource": {"entity_type": "resource", "id_label": "Resource (not supported)"}
    }

    first_context = mod_data["contexts"]
    context_info = CONTEXT_ENTITY_MAPPING.get(first_context)

    if not context_info:
        print(f"Unknown context: {first_context}. Aborting.")
        return

    entity_type = context_info["entity_type"]

    # ----------- ENTITY CHOOSER -------------------------------------------------------------------------------------------------------------------

    all_files, container_entity_id, scan_id = [], None, None# Parallele Zuweisung

    if entity_type == "scan":
        session_list = get_sessions_for_project(xnat_host, project_id, xnat_user, xnat_password)
        if not session_list:
            print("No sessions found in project.")
            return
        chosen_session = select_data(session_list, id_key="ID", name_key="label")
        if not chosen_session:
            print("No session selected.")
            return
        session_id = chosen_session["ID"]

        scan_list = get_scans_for_session(xnat_host, session_id, xnat_user, xnat_password)
        if not scan_list:
            print("No scans found in session.")
            return
        # Find a good key for human-readable scan name:
        scan_name_key = "series_description" if "series_description" in scan_list[0] else "ID"
        chosen_scan = select_data(scan_list, id_key="ID", name_key=scan_name_key)
        if not chosen_scan:
            print("No scan selected.")
            return
        scan_id = chosen_scan["ID"]
        container_entity_id = session_id

        all_files = get_input_files(
            xnat_host, session_id, 'scan', xnat_user, xnat_password, scan_id=scan_id
        )

    elif entity_type == "session":
        session_list = get_sessions_for_project(xnat_host, project_id, xnat_user, xnat_password)
        if not session_list:
            print("No sessions found in project.")
            return
        chosen_session = select_data(session_list, id_key="ID", name_key="label")
        if not chosen_session:
            print("No session selected.")
            return
        session_id = chosen_session["ID"]
        container_entity_id = session_id
        all_files = get_input_files(
            xnat_host, session_id, 'session', xnat_user, xnat_password
        )

    elif entity_type == "subject":
        subject_list = get_subjects_for_project(xnat_host, project_id, xnat_user, xnat_password)
        if not subject_list:
            print("No subjects found in project.")
            return
        chosen_subject = select_data(subject_list, id_key="ID", name_key="label")
        if not chosen_subject:
            print("No subject selected.")
            return
        subject_id = chosen_subject["ID"]
        container_entity_id = subject_id
        all_files = get_input_files(
            xnat_host, subject_id, 'subject', xnat_user, xnat_password
        )

    elif entity_type == "project":
        container_entity_id = project_id
        all_files = get_input_files(
            xnat_host, project_id, 'project', xnat_user, xnat_password
        )

    else:
        print("This context is currently not supported.")
        return

    # ------------- --------------------------------- -----------
    selected_files = select_data(all_files)

    if selected_files:
        for input_file_info in selected_files:
            launch_container_rest(
                xnat_host,
                project_id,
                command_id,
                wrapper_name,
                container_entity_id,
                xnat_user,
                xnat_password,
                input_file_info,
                entity_type=entity_type,
                scan_id=scan_id if entity_type == "scan" else None
            )
    else:
        print("No file selected. Container launch aborted.")

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