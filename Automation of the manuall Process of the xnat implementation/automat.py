
#-----------------Bibliotheken----------------------------------------------------------------------------------------------------------------------------
import json 
import requests  # type: ignore 
import os #Arbeiten mit Dateien und Pfaden
import subprocess 
import getpass 
import sys
import urllib3 # type: ignore 
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
#-----------------------------------1)dockerfile ausfüllen------------------------------------------------------
def write_dockerfile(docker_dir, script_filename, docker_base_image="python:3.10-slim"):
    dockerfile_content = f"""
    
FROM {docker_base_image}
WORKDIR /app
COPY {script_filename} /app/{script_filename}
RUN pip install --no-cache-dir pandas
COPY requirements.txt /app/requirements.txt

"""

    os.makedirs(docker_dir, exist_ok=True)
    dockerfile_path = os.path.join(docker_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile written to {dockerfile_path}")
    return dockerfile_path
#--------------------------------------2)Image bauen>>pushen>>taggen --------------------------------------

def build_and_push_docker_image(dockerfile_path, docker_image_name):
    dockerhub_username = input("Docker Hub username (to push the image): ").strip()
    if not dockerhub_username:
        print("No Docker Hub username provided. Skipping push.")
        return None

    full_tag = f"{dockerhub_username}/{docker_image_name}"
    print(f"Building Docker image '{full_tag}'...")
    build_result = subprocess.run(
        ["docker", "build", "-f", dockerfile_path, "-t", full_tag, "."],
        capture_output=True, text=True)
    if build_result.returncode != 0:
        print(f"Build failed:\n{build_result.stderr}")
        sys.exit(1)
    print(f"Image '{full_tag}' built successfully.")

    print(f"Pushing image to Docker Hub as '{full_tag}'...")
    push_result = subprocess.run(["docker", "push", full_tag], capture_output=True, text=True)
    if push_result.returncode != 0:
        print(f"Push failed:\n{push_result.stderr}")
        sys.exit(1)

    print(f"Image successfully pushed: {full_tag}")
    return full_tag 
#-----------------------------------3)User-Input----------------------------------------------------------------------------------
def get_input(prompt):
    while True:
        value = input(prompt)
        if value.strip():
            return value
        else:
            print("Cannot be empty.")
#---------------------------------------------------------------------------------------------------------
def modification():
    context_options = [
        ("xnat:subjectData", "Subject-Ebene"),
        ("xnat:mrSessionData", "MRI-Session-Ebene"),
        ("xnat:petSessionData", "PET-Session-Ebene"),
        ("xnat:ctSessionData", "CT-Session-Ebene"),
        ("xnat:imageScanData", "Scan-Ebene"),
        ("xnat:projectData", "Projekt-Ebene"),
    ]
    print("\nWähle einen Kontext:")
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

   
    command_name = input("Name des Commands: ")
    command_description = input("Beschreibung des Commands: ")
    
    
    return {
        "selected_context": selected_context,
        "command_name": command_name,
        "command_description": command_description
    }
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
        "xnat:imageScanData": {"input_name": "scan", "input_type": "Scan", "child_of": "scan"},
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
                "required": True,
                "load-children": False
            })
            used_inputs.add(input_key)

        output_handlers.append({
            "name": "output",
            "accepts-command-output": "result_file",
            "as-a-child-of": mapping["child_of"],
            "type": "Resource",
            "label": "Results",
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
    url = f"{xnat_host}/xapi/commands"
    resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False) 
    if resp.status_code != 200:
        print(f"Error fetching commands: {resp.status_code}")
        sys.exit(1)
    data = resp.json()
    if isinstance(data, dict) and "commands" in data:
        command_list = data["commands"]
    else:
        command_list = data
    for command in command_list:
        if command.get("name") == command_name:
            return command["id"]
    print("Command not found.")
    sys.exit(1)

#----------------------7)Wrapper auslesen/erstellen------------------------------------------------------------------------------------------------------------
def get_command_wrapper_id(xnat_host, xnat_user, xnat_password, command_name, wrapper_name=None):
    url = f"{xnat_host}/xapi/commands"
    try:
        resp = requests.get(url, auth=(xnat_user, xnat_password), verify=False)
    except Exception as e:
        print(f"Verbindungsfehler: {e}")
        sys.exit(1)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Commands: {resp.status_code}")
        sys.exit(1)
    data = resp.json()
    commands = data.get("commands", data) if isinstance(data, dict) else data

    for command in commands:
        if command.get("name") == command_name:
            if not wrapper_name:
                return command.get("id")
            for wrappers_field in ["xnat", "wrappers"]:
                for wrapper in command.get(wrappers_field, []):
                    if wrapper.get("name") == wrapper_name:
                        return wrapper.get("id") or wrapper_name
            print("Kein Wrapper für diesen Command gefunden.")
            sys.exit(1)
    print("Command nicht gefunden.")
    sys.exit(1)

#----------------------9)Wrapper Aktivierung---------------------------------------------


def enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password):

    url = f"{xnat_host}/xapi/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde global aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits global aktiviert.")
    else:
        print(f"Fehler beim globalen Aktivieren: {resp.status_code} - {resp.text}")


def enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password):
    
    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde im Projekt '{project_id}' aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits im Projekt aktiviert.")
    else:
        print(f"Fehler beim Aktivieren für das Projekt: {resp.status_code} - {resp.text}")

#----------------------------------------10)get_input_file-------------------------------------------

def get_input_files(xnat_host, entity_id, entity_type, xnat_user, xnat_password, scan_id=None):
    # REST-Pfad je nach Kontexttyp
    if entity_type == "project":
        base_url = f"{xnat_host}/data/projects/{entity_id}/resources"
    elif entity_type == "subject":
        base_url = f"{xnat_host}/data/subjects/{entity_id}/resources"
    elif entity_type in ["session", "experiment"]:
        base_url = f"{xnat_host}/data/experiments/{entity_id}/resources"
    elif entity_type == "scan" and scan_id:
        base_url = f"{xnat_host}/data/experiments/{entity_id}/scans/{scan_id}/resources"
    else:
        print("Unbekannter oder nicht unterstützter Entitätstyp.")
        return None

    # Ressourcen abfragen
    resp = requests.get(base_url, auth=(xnat_user, xnat_password), verify=False)
    if resp.status_code != 200:
        print(f"Fehler beim Abrufen der Ressourcen ({entity_type}): {resp.status_code}")
        return None

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

    if not all_files:
        print("Keine Dateien gefunden.")
        return None

    
    print("\nVerfügbare Dateien:")
    for n, f in enumerate(all_files):
        print(f"{n + 1}: {f['name']} (Resource: {f['resource']})")

    while True:
        choice = input("Welche Dateien sollen verwendet werden? Gib die Nummern durch Komma getrennt ein: ")
        selected_files = []
        try:
            indices = [int(c.strip()) for c in choice.split(",")]
            valid = all(1 <= i <= len(all_files) for i in indices)
            if valid:
                selected_files = [all_files[i - 1] for i in indices]
                print("Ausgewählte Dateien:")
                for f in selected_files:
                    print(f" - {f['name']}")
                return selected_files
        except ValueError:
            pass
        print("Ungültige Auswahl, bitte Nummern korrekt eingeben (z.B. 1,3,5).")



#---------------------11)Lanch Container-----------------------------------------

def launch_container_rest(xnat_host, project_id, command_id, wrapper_name,
                          entity_id, xnat_user, xnat_password, input_file_info,
                          entity_type="session", scan_id=None):

    headers = {"Content-Type": "application/json"}
   

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

    # 1. Credentials & inputs
    xnat_user = get_input("XNAT Username: ")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID: ").strip()
    script_path = get_input("Path to the Python script: ")

    # 2. Get command metadata
    mod_data = modification()
    mod_data["contexts"] = [mod_data["selected_context"]]
    mod_data["label_name"] = mod_data["command_name"]
    mod_data["label_description"] = mod_data["command_description"]
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # 3. Build Docker image
    dockerfile_path = write_dockerfile(".", os.path.basename(script_path), docker_base_image)
    local_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}"
    full_image_name = build_and_push_docker_image(dockerfile_path, local_image_name)

    # 4. Create & upload command JSON
    json_file_path = create_json_file(full_image_name, os.path.basename(script_path), mod_data)
    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)

    # 5. Get command & wrapper IDs
    command_id = get_command_id_by_name(xnat_host, xnat_user, xnat_password, mod_data["command_name"])
    try:
        wrapper_id = get_command_wrapper_id(xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name)
        print(f"Wrapper already exists: {wrapper_id}")
    except SystemExit:
        print("Wrapper not found; will create it automatically")

    # 6. Enable wrapper
    enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password)
    enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password)

    # 7. Map contexts to XNAT entity types
    CONTEXT_ENTITY_MAPPING = {
        "xnat:projectData": {"entity_type": "project", "id_label": "Project ID"},
        "xnat:subjectData": {"entity_type": "subject", "id_label": "Subject ID"},
        "xnat:mrSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:petSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:ctSessionData": {"entity_type": "session", "id_label": "Session ID"},
        "xnat:imageScanData": {"entity_type": "scan", "id_label": "Session ID + Scan ID"},
    }

    first_context = mod_data["contexts"][0]
    context_info = CONTEXT_ENTITY_MAPPING.get(first_context)
    if not context_info:
        print(f"Unbekannter Kontext: {first_context}. Abbruch.")
        return

    entity_type = context_info["entity_type"]

    # 8. Ask user for entity IDs
    if entity_type == "scan":
        session_id = get_input("Gib die Session-ID ein: ")
        scan_id = get_input("Gib die Scan-ID ein: ")
        input_file_info = get_input_files(
            xnat_host, session_id, entity_type, xnat_user, xnat_password, scan_id=scan_id
        )
        container_entity_id = session_id
    else:
        entity_id = get_input(f"Gib die {context_info['id_label']} ein: ")
        input_file_info = get_input_files(
            xnat_host, entity_id, entity_type, xnat_user, xnat_password
        )
        container_entity_id = entity_id
        scan_id = None

    # 9. Launch container
    if input_file_info:
        if input_file_info:
         launch_container_rest(
        xnat_host,
        project_id,
        command_id,
        wrapper_name,
        container_entity_id,
        xnat_user,
        xnat_password,
        input_file_info[0],
        entity_type=entity_type,
        scan_id=scan_id if entity_type == "scan" else None
    )

    else:
        print("Keine Datei ausgewählt. Containerstart abgebrochen.")


if __name__ == "__main__":
    main()
