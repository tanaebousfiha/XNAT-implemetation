
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
#docker_dir> Verzeichniss,in das die Dockerfile geschrieben werden. 
#Speicher Platz Problem 
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

# -f [dockerfile_path]>Gibt den Pfad zum Dockerfile explizit an, falls den Dockerfile nicht Dockerfile heißt
#docker build -t
#https://stackoverflow.com/questions/61090027/how-to-run-a-docker-volume-mount-as-a-python-subprocess

 #-------------------------------/Tag/Push/--------------------------------------------------------------------------------------------------
 
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
#FCT nimmrt eine Parameter "promt">Endlosschleifen>Code unundlich

def get_modification_data():
    # Kontext-Auswahl
    print("Wähle den Kontext für den Command:")
    context_options = [
        ("xnat:projectData", "Projekt"),
        ("xnat:subjectData", "Subject"),
        ("xnat:mrSessionData", "MR-Session"),
        ("xnat:petSessionData", "PET-Session"),
        ("xnat:ctSessionData", "CT-Session"),
        ("xnat:imageScanData", "Scan"),
    ]
    for idx, (_, label) in enumerate(context_options, 1):
        print(f"{idx}: {label}")
    while True:
        context_choice = input(f"Kontext wählen (1-{len(context_options)}): ")
        if context_choice.isdigit() and 1 <= int(context_choice) <= len(context_options):
            selected_context = context_options[int(context_choice)-1][0]
            break
        print("Ungültige Auswahl.")

    # Zusätzliche Eingaben einholen:
    command_name = input("Name des Commands: ")
    command_description = input("Beschreibung des Commands: ")
    
    # Ausgabe oder Rückgabe eines Dictionaries mit den benötigten Werten
    return {
        "selected_context": selected_context,
        "command_name": command_name,
        "command_description": command_description
    }

# es wiederholt sich weil in der jsoncommand muss mehr als eine varial geschreiben werden
#und ich wollte nicht dass der user meher mals etwas ähnliches schreibt, deshalb habe ich es so gemacht
#-----------------------------------4)json File erstellen------------------------------------------------------------------
def create_json_file(docker_image, script_filename, mod_data):
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"

    # Mapping Kontext >>external-input + as-a-child-of
    context_mappings = {
        "xnat:projectData": {"input_name": "project", "input_type": "Project", "child_of": "project"}, 
    }

    # Dynamische Listen
    external_inputs = []
    output_handlers = []
    used_inputs = set()  # Duplikate vermeiden
#Mehrfachauswahlen sammeln und dabei Duplikate automatisch ausfiltern
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
        "command-line": f"python3 /app/{script_filename} #input_file# /output",
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
                "path":"." 
                           
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

#---------------------5)Command zu XNAT senden---------------------------------------------------------------------------------------------------------------

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
    if isinstance(data, dict) and "commands" in data:
        command_list = data["commands"]# # Wenn die Antwort ein Dictionary ist, das "commands" enthält, dann wird es extrahiert
    else:
        command_list = data
    for command in command_list:
        if command.get("name") == command_name:
            return command["id"]
    print("Command not found.")
    sys.exit(1)
    #Überprüft, ob das Objekt data ein Dictionary (also eine „dict“-Instanz) ist.
    
    
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

#----------------------------------------------------------------------------------------------------------------
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
    # REST-Pfad je nach Kontexttyp
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
                "url": f"{base_url}/{res_label}/files/{f['Name']}",
                "resource": res_label
            })
    return all_files
#sammelst also mit jedem Durchlauf alle gefundenen Dateien in einer Liste 
#>>am Ende enthält all_files die gesamte Übersicht aller gefundenen Dateien.
#-------------------------------------------------------------------------------------------------------------------
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
            unique_indices = list(set(int(i) for i in indices))#Zeichenkette in indices wird in eine Ganzzahl (int(i)) umgewandelt.
            selected = [all_files[i-1] for i in unique_indices]#werden die Objekte aus all_files ausgewählt
            print("Ausgewählt:")
            for s in selected:#Es werden die Namen der gewählten Dateien einzeln aufgelistet.
                print(f"- {s['name']}")
            return selected
        print("Ungültige Auswahl.")
#choice.split(",")>Das Ergebnis ist eine Liste von (meist) Strings
#for c in>Die List läuft über jedes dieser Teilstücke (also "1", " 2", "3 " usw.)
#if c.strip()>Das filtert leere Einträge heraus
#------------------------------------------------- Entities auflisten und auswählen lassen----------------------------
#Bei Session, damit den User bestimmt Session auswählen kann
def select_entity(entities, id_key="ID", name_key="label"):
    if not entities:
        print("Keine Session gefunden.")
        return None
    print("Verfügbare Session:")
    for idx, entity in enumerate(entities, 1):
        print(f"{idx}: {entity.get(id_key, '---')} ({entity.get(name_key, '')})")
    while True:
        choice = input(f"Wähle eine Datei/File (1-{len(entities)}): ")
        if choice.isdigit() and 1 <= int(choice) <= len(entities):
            return entities[int(choice)-1]
        print("Ungültige Auswahl!")
        #choice.isdigit()>ob die Eingabe ausschließlich aus Ziffern besteht
        #1 <= int(choice) <= len(entities)>ob sie zwischen 1 und der Anzahl der auswählbaren Elemente liegt.

 #---------------------------------sessions_for_project---------------------------------------------
        #Session for den user muss aufgelistet werden weil es mehr als eine im Projekt gibt 
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
#um aus einer JSON-Response immer eine verarbeitbare Liste zu extrahieren
#---------------------11)Lanch Container------------------------------------------------------------------

def launch_container_rest(xnat_host, project_id, command_id, wrapper_name,
                          entity_id, xnat_user, xnat_password, input_file_info,
                          entity_type="session", scan_id=None):

    headers = {"Content-Type": "application/json"}

    if entity_type == "session":
        root_type = "session"
    elif entity_type == "subject":
        root_type = "subject"
    elif entity_type == "project":
        root_type = "project"
    elif entity_type == "scan":
        root_type = "scan"
    else:
        print(f"Containerstart für entity_type '{entity_type}' wird nicht unterstützt.")
        return

    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/root/{root_type}/launch"

    # Nur den Dateinamen übergeben, da XNAT die Datei unter /input/ zur Verfügung stellt
    input_file_path = input_file_info['name']

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

    print("Launching container:")
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
    else:
        print(f"Fehler beim Containerstart ({response.status_code}):")
        print(response.text)


#-------------------------------------------------------------------------------------------------------

def main():

    xnat_host = "https://xnat-dev.gwdg.de"
    docker_base_image = "python:3.10"

    xnat_user = get_input("XNAT Username: ")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID: ").strip()
    script_path = get_input("Path to the Python script: ")

    # Step 1: Gather Command/Wrapper Data
    mod_data = get_modification_data()
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
#-----------------------------------------------------------------------------------------------------

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
        print(f"Unknown context: {first_context}. Aborting.")
        return

    entity_type = context_info["entity_type"]

    all_files, container_entity_id, scan_id = [], None, None

    if entity_type == "scan":
        session_list = get_sessions_for_project(xnat_host, project_id, xnat_user, xnat_password)
        if not session_list:
            print("No sessions found in project.")
            return
        chosen_session = select_entity(session_list, id_key="ID", name_key="label")
        if not chosen_session:
            print("No session selected.")
            return
        session_id = chosen_session["ID"]

        scan_list = get_scans_for_session(xnat_host, session_id, xnat_user, xnat_password)
        if not scan_list:
            print("No scans found in session.")
            return
        scan_name_key = "series_description" if "series_description" in scan_list[0] else "ID"
        chosen_scan = select_entity(scan_list, id_key="ID", name_key=scan_name_key)
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
        chosen_session = select_entity(session_list, id_key="ID", name_key="label")
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
        chosen_subject = select_entity(subject_list, id_key="ID", name_key="label")
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

    selected_files = select_files_from_list(all_files)
    if not selected_files:
        print("Keine Dateien ausgewählt.")
        return

    for file_info in selected_files:
        print(f"Starte Container für Datei: {file_info['name']}")
        launch_container_rest(
            xnat_host, project_id, command_id, wrapper_name,
            container_entity_id, xnat_user, xnat_password,
            file_info,
            entity_type=entity_type,
            scan_id=scan_id
        )
   


if __name__ == "__main__":
    main()


