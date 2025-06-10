#-----------------Bibliotheken---------------------------------------------------------
import datetime
import json # wir brachen json für xnat damit er den Command anlegen kann
import requests  # https://wiki.xnat.org/container-service/container-service-api
import os #Arbeiten mit Dateien und Pfaden
import subprocess  # https://www.datacamp.com/tutorial/python-subprocess
import getpass #Passwort-Eingabe im Terminal ohne Anzeige
import sys#Für sys.exit() bei Fehlern
import urllib3#Wird von requests genutzt – hier zur Abschaltung von SSL-Warnungen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)# Deaktiviert SSL-Warnungen, wenn XNAT ohne gültiges Zertifikat läuft


#------------------------------------erstmal Skript from the users Fragen-----------------------------------------------------

def check_user_skript(skript_path):
    if not os.path.isfile(skript_path):
        print(f"Datei nicht gefunden: {skript_path}")
        return False
    if not skript_path.endswith(".py"):
        print("Datei nicht korrekt, bitte eine .py Datei angeben.")
        return False
    return True

#-----------------------------------dockerfile ausfüllen------------------------------------------------------
#Docker ofiziel Dokumentation>https://docs.docker.com/engine/reference/commandline/build/
def write_dockerfile(docker_dir, script_filename, docker_base_image):
    dockerfile_content = f"""FROM {docker_base_image}

WORKDIR /app

COPY {script_filename} /app/{script_filename}

ENTRYPOINT ["python3", "/app/{script_filename}"]
CMD ["example.csv", "/app/output"]
"""
    os.makedirs(docker_dir, exist_ok=True)
    dockerfile_path = os.path.join(docker_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile written to {dockerfile_path}")
    return dockerfile_path

#--------------------------------------Image bauen--------------------------------------
#https://docs.docker.com/develop/develop-images/dockerfile_best-practices/
def build_docker_image(dockerfile_path, docker_image_name):
    build_command = [
        "docker", "build", "-f", dockerfile_path, "-t", docker_image_name, "."
    ]
    print(f"Building Docker image '{docker_image_name}'...")
    result = subprocess.run(build_command, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Docker image '{docker_image_name}' built successfully.")
    else:
        print(f"Failed to build Docker image: {result.stderr}")
        exit(1)

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
    return data

#-----------------------------------json File erstellen-------------------------------
def create_json_file(docker_image, script_filename, mod_data):#fonktion with th esam eold version of my osa prediction succes json comamnd
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"
    json_file = {
        "name": mod_data["command_name"],
        "description": mod_data["command_description"],
        "version": "1.0",
        "image": docker_image,
        "type": "docker",
        "command-line": f"python /app/{script_filename} /app/input/#INPUT_FILE# /app/output",
        "mounts": [
            {"name": "output_mount", "writable": True, "path": "/app/output"},
            {"name": "input_mount", "writable": False, "path": "/app/input"}
        ],
        "inputs": [
            {
                "name": "INPUT_FILE",
                "description": mod_data["command_description"],
                "type": "string",
                "required": True
            }
        ],
        "outputs": [
            {
                "name": "result_file",
                "description": "Result",
                "required": True,
                "mount": "output_mount",
                "path": "result.csv"
            }
        ],
        "xnat": [
            {
                "name": wrapper_name,
                "label": mod_data["label_name"],
                "description": mod_data["label_description"],
                "contexts": ["xnat:mrSessionData"],
                "external-inputs": [
                    {"name": "session", "type": "Session", "required": True, "load-children": True}
                ],
                "derived-inputs": [
                    {
                        "name": "csv_resource",
                        "type": "Resource",
                        "matcher": "@.label == 'CSV'",
                        "required": True,
                        "provides-files-for-command-mount": "input_mount",
                        "load-children": True,
                        "derived-from-wrapper-input": "session"
                    },
                    {
                        "name": "input_file",
                        "type": "File",
                        "matcher": "@.name =~ \".*\\.(csv|tsv|txt)$\"",#https://github.com/json-path/JsonPath/blob/master/README.md
                        "required": True,
                        "load-children": True,
                        "derived-from-wrapper-input": "csv_resource"
                    },
                    {
                        "name": "input_file_name",
                        "type": "string",
                        "derived-from-wrapper-input": "input_file"
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
    #----------------------------------------------------------------
    #write the json in an external File
    with open("command.json", "w") as json_out:
        json.dump(json_file, json_out, indent=4)
        print(f"JSON file created at command.json")
    return "command.json"

#---------------------Command zu XNAT senden------------------------------------------
#here is the APIS XNAT dokumentation 
#https://wiki.xnat.org/container-service/container-service-api
#https://wiki.xnat.org/container-service/container-command-json
#
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
def get_command_id_by_name(xnat_host, xnat_user, xnat_password, command_name):# #https://wiki.xnat.org/container-service/container-service-api#ContainerServiceAPI-Commands
    url = f"{xnat_host.rstrip('/')}/xapi/commands"# # Hier wird die URL für die XNAT-API definiert
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
def get_command_io(xnat_host, xnat_user, xnat_password, command_id):# #https://wiki.xnat.org/container-service/container-service-api#ContainerServiceAPI-Commands
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

def get_wrapper_id_by_command_name(xnat_host, xnat_user, xnat_password, command_name, wrapper_name):#
    url = f"{xnat_host.rstrip('/')}/xapi/commands"# url wird zusammengebaut 
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)# get request geschickt
    if resp.status_code != 200:
        print(f"Error fetching commands: {resp.status_code}")
        sys.exit(1)
    data = resp.json()#Antwort wird als JSON interpretiert
    # Wenn nötig, "commands"-Verschachtelung auflösen:
    if isinstance(data, dict) and "commands" in data:# # Überprüfen, ob die Antwort ein Dictionary ist und "commands" enthält
        commands = data["commands"]
    else:
        commands = data
    for command in commands:
        if command.get("name") == command_name:
            # Erst im Feld "xnat" suchen
            for wrapper in command.get("xnat", []):
                if wrapper.get("name") == wrapper_name:
                    # Falls "id" vorhanden, nimm id, sonst name
                    return wrapper.get("id") or wrapper_name
            # Fallback: Ältere XNATs können wrapper auch unter "wrappers" speichern
            for wrapper in command.get("wrappers", []):
                if wrapper.get("name") == wrapper_name:
                    return wrapper.get("id") or wrapper_name
    print("No wrapper found for this command.")
    sys.exit(1)
#------------------------------------------

def create_wrapper(xnat_host, command_id, wrapper_name, label_name, description, xnat_user, xnat_password, outputs, external_inputs, derived_inputs):
    url = f"{xnat_host.rstrip('/')}/xapi/commands/{command_id}/wrappers"# # URL zum Erstellen eines Wrappers
    output_handlers = [{# # Definition der Output-Handler
        "name": "output",
        "accepts-command-output": "result_file",
        "as-a-child-of": "session",
        "type": "Resource",
        "label": "Results",
        "format": "csv"
    }]
    wrapper = {
        "name": wrapper_name,
        "label": label_name,
        "description": description,
        "contexts": ["xnat:mrSessionData"],
        "outputs": outputs,
        "external-inputs": external_inputs,
        "derived-inputs": derived_inputs,
        "output-handlers": output_handlers
    }
    print("Wrapper-Payload:", json.dumps(wrapper, indent=2))# Debug-Ausgabe des Wrappers
    resp = requests.post(url, auth=(xnat_user, xnat_password),headers={"Content-Type": "application/json"},json=wrapper, verify=False)# request mit POST 
    # Korrekte Behandlung von Status-Code:
    if resp.status_code == 201:
        wrapper_id = resp.text.strip()
        print(f"Wrapper created successfully. ID: {wrapper_id}")
        return wrapper_id
    elif resp.status_code == 200:
        print("Wrapper created successfully (200).")
        # extrahiere ggf. return-id
    elif resp.status_code == 409:
        print("Wrapper already exists.")
        return None
    else:
        print(f"Wrapper creation failed: {resp.status_code} - {resp.text}")
        return None

#----------------------Wrapper Aktivierung---------------------------------------------
def enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password):
    url = f"{xnat_host.rstrip('/')}/xapi/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde global aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits global aktiviert.")
    else:
        print(f"Fehler bei globalem Enable: {resp.status_code} - {resp.text}")


def enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password):
    url = f"{xnat_host.rstrip('/')}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde im Projekt '{project_id}' aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits im Projekt aktiviert.")
    else:
        print(f"Fehler beim Projekt-Enable: {resp.status_code} - {resp.text}")

#---------------------Container in XNAT starten----------------------------------------
def run_container_in_xnat(xnat_host, project_id, wrapper_id, session_id, xnat_user, xnat_password):
    url = f"{xnat_host}/xapi/projects/{project_id}/wrappers/{wrapper_id}/launch"
    headers = {"Content-Type": "application/json"}
    payload = {
        "session": session_id
    }

    print("Launching container with payload:", json.dumps(payload, indent=2))
    response = requests.post(url, auth=(xnat_user, xnat_password), headers=headers, json=payload, verify=False)

    if response.status_code in [200, 201]:
        print(" Container launched successfully.")
    else:
        print(f" Failed to launch container: {response.status_code} - {response.text}")

#https://hawki.hawk.de/chat/jjitmwrbb5vaeemt
#https://xnat-dev.gwdg.de/xapi/swagger-ui.html#/launch-rest-api

#-----------------------------------------------Main Teil-----------------------------------------------

def main():
    # Fixe Werte
    xnat_host = "https://xnat-dev.gwdg.de"
    docker_base_image = "python:3.10"

    # Nur noch diese Felder werden interaktiv abgefragt:
    xnat_user = get_input("XNAT Username:")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID:")
    session_id = get_input("Session ID:")
    script_path = get_input("Path to the Python script:")

    if not check_user_skript(script_path):
        return

    mod_data = modification()
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # Dockerfile erstellen und Image bauen
    dockerfile_path = write_dockerfile(".", os.path.basename(script_path), docker_base_image)
    docker_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}:latest"
    build_docker_image(dockerfile_path, docker_image_name)

    # JSON erstellen und an XNAT senden
    json_file_path = create_json_file(docker_image_name, os.path.basename(script_path), mod_data)
    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)

    # Command-ID holen
    command_id = get_command_id_by_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"])

    # Wrapper erstellen oder holen
    wrapper_id = None
    try:
        wrapper_id = get_wrapper_id_by_command_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name)
        print(f"Wrapper existiert bereits: {wrapper_id}")
    except SystemExit:
        print("Wrapper existiert noch nicht, wird erstellt...")
        outputs, external_inputs, derived_inputs = get_command_io(xnat_host, xnat_user, xnat_password, command_id)
        wrapper_id = create_wrapper(
            xnat_host, command_id, wrapper_name,
            mod_data["label_name"], mod_data["label_description"],
            xnat_user, xnat_password,
            outputs, external_inputs, derived_inputs
        )
        if not wrapper_id:
            print("Wrapper konnte nicht erstellt werden, versuche existierenden Wrapper zu verwenden ...")
            try:
                wrapper_id = get_wrapper_id_by_command_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name)
                print(f"Existierenden Wrapper gefunden: {wrapper_id}")
            except SystemExit:
                print("Kein Wrapper gefunden oder schwerwiegender Fehler – Abbruch.")
                return

    enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password)
    enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password)

    run_container_in_xnat(xnat_host, project_id, wrapper_id, session_id, xnat_user, xnat_password)


if __name__ == "__main__":
    main()



   