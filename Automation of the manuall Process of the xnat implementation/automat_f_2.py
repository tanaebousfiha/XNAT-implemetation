

#-----------------Bibliotheken----------------------------------------------------------------------------------------------------------------------------
import json 
import requests
import os 
import subprocess  
import getpass 
import sys
import urllib3 
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
    dockerfile_path = os.path.join(docker_dir, "Dockerfile")
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile geschrieben nach {dockerfile_path}")
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
#-----------------------------------3)User-Input----------------------------------------- -----------------------------------------   
def get_input(prompt):
    while True:
        value = input(prompt)
        if value.strip():
            return value
        else:
            print("Cannot be empty.")
#-----------------------------------4)json File erstellen------------------------------------------------------------------

def create_json_file(docker_image, script_filename, mod_data):
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"
    
    json_file = {
        "name": mod_data["command_name"],
        "description": mod_data["command_description"],
        "version": "1.5",
        "type": "docker",
        "image": docker_image,
        "command-line": f"python3 /app/{script_filename} /input/output",
        "mounts": [
            {"name": "input", "path": "/input", "writable": False},
            {"name": "output", "path": "/output", "writable": True}
        ],
        "inputs": [
            {
                "name": "input_files",
                "description": "Input files",
                "type": "files",
                "element_type": "file",
                "required": True,
                "mount": "input",
                "multiple": True
            }
        ],
        "outputs": [
            {
                "name": "result_file",
                "type": "file",
                "description": "Result file output",
                "mount": "output",
                "path": "."
            }
        ],
        "xnat": [
            {
                "name": wrapper_name,
                "label": mod_data.get("label_name", ""),
                "description": mod_data.get("label_description", ""),
                "contexts": ["xnat:projectData"],
                "external-inputs": [
                    {
                        "name": "project",
                        "type": "Project",
                        "required": True,
                        "load-children": True
                    }
                ],
                
                "output-handlers": [
                    {
                        "name": "output",
                        "accepts-command-output": "result_file",
                        "as-a-child-of": "project",
                        "type": "Resource",
                        "label": "Results"
                    }
                ]
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

def get_command_wrapper_id(xnat_host, xnat_user, xnat_password, command_name, wrapper_name=None):
    url = f"{xnat_host.rstrip('/')}/xapi/commands"
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
    
    url = f"{xnat_host.rstrip('/')}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/enabled"
    resp = requests.put(url, auth=(xnat_user, xnat_password), verify=False)

    if resp.status_code == 200:
        print(f"Wrapper '{wrapper_name}' wurde im Projekt '{project_id}' aktiviert.")
    elif resp.status_code == 409:
        print(f"Wrapper '{wrapper_name}' war bereits im Projekt aktiviert.")
    else:
        print(f"Fehler beim Aktivieren für das Projekt: {resp.status_code} - {resp.text}")

#----------------------------------------10)get_input_file-------------------------------------------


def get_all_files_all_levels(xnat_host, project_id, xnat_user, xnat_password):
    session = requests.Session()
    session.auth = (xnat_user, xnat_password)

    all_files = []

    # PROJECT-Ebene
    proj_res_url = f"{xnat_host}/data/projects/{project_id}/resources?format=json"
    resp = session.get(proj_res_url, verify=False)
    for res in resp.json().get("ResultSet", {}).get("Result", []):
        res_name = res['label']
        file_url = f"{xnat_host}/data/projects/{project_id}/resources/{res_name}/files?format=json"
        fresp = session.get(file_url, verify=False)
        for f in fresp.json().get("ResultSet", {}).get("Result", []):
            all_files.append({
                "Ebene":"project",
                "Name":f["Name"],
                "Resource":res_name,
                "URI": f"{xnat_host}/data/projects/{project_id}/resources/{res_name}/files/{f['Name']}"
            })

    # SUBJECT-Ebene
    subj_url = f"{xnat_host}/data/projects/{project_id}/subjects?format=json"
    subjects = session.get(subj_url, verify=False).json().get("ResultSet", {}).get("Result", [])
    for subj in subjects:
        subj_id = subj['ID']
        sres_url = f"{xnat_host}/data/subjects/{subj_id}/resources?format=json"
        resp = session.get(sres_url, verify=False)
        for res in resp.json().get("ResultSet", {}).get("Result", []):
            res_name = res['label']
            file_url = f"{xnat_host}/data/subjects/{subj_id}/resources/{res_name}/files?format=json"
            fresp = session.get(file_url, verify=False)
            for f in fresp.json().get("ResultSet", {}).get("Result", []):
                all_files.append({
                    "Ebene":"subject",
                    "SubjectID":subj_id,
                    "Name":f["Name"],
                    "Resource":res_name,
                    "URI": f"{xnat_host}/data/subjects/{subj_id}/resources/{res_name}/files/{f['Name']}"
                })

    # 3. SESSION-Ebene (MR/PET/CT)
    sess_url = f"{xnat_host}/data/projects/{project_id}/experiments?format=json"
    sessions = session.get(sess_url, verify=False).json().get("ResultSet", {}).get("Result", [])
    for sess in sessions:
        sess_id = sess['ID']
        stype = sess.get('xsiType','')
        # Nur MR/PET/CT Sessions
        if stype not in ["xnat:mrSessionData", "xnat:petSessionData", "xnat:ctSessionData"]:
            continue
        sres_url = f"{xnat_host}/data/experiments/{sess_id}/resources?format=json"
        resp = session.get(sres_url, verify=False)
        for res in resp.json().get("ResultSet", {}).get("Result", []):
            res_name = res['label']
            file_url = f"{xnat_host}/data/experiments/{sess_id}/resources/{res_name}/files?format=json"
            fresp = session.get(file_url, verify=False)
            for f in fresp.json().get("ResultSet", {}).get("Result", []):
                all_files.append({
                    "Ebene":stype,
                    "SessionID":sess_id,
                    "Name":f["Name"],
                    "Resource":res_name,
                    "URI": f"{xnat_host}/data/experiments/{sess_id}/resources/{res_name}/files/{f['Name']}"
                })

        # 4. SCAN-Ebene innerhalb jeder SESSION
        scan_url = f"{xnat_host}/data/experiments/{sess_id}/scans?format=json"
        scans = session.get(scan_url, verify=False).json().get("ResultSet", {}).get("Result", [])
        for scan in scans:
            scan_id = scan['ID']
            scres_url = f"{xnat_host}/data/experiments/{sess_id}/scans/{scan_id}/resources?format=json"
            resp = session.get(scres_url, verify=False)
            for res in resp.json().get("ResultSet", {}).get("Result", []):
                res_name = res['label']
                file_url = f"{xnat_host}/data/experiments/{sess_id}/scans/{scan_id}/resources/{res_name}/files?format=json"
                fresp = session.get(file_url, verify=False)
                for f in fresp.json().get("ResultSet", {}).get("Result", []):
                    all_files.append({
                        "Ebene":"scan",
                        "SessionID":sess_id,
                        "ScanID":scan_id,
                        "Name":f["Name"],
                        "Resource":res_name,
                        "URI": f"{xnat_host}/data/experiments/{sess_id}/scans/{scan_id}/resources/{res_name}/files/{f['Name']}"
                    })

    return all_files
#---------------------------------------------------------------------------------------------------------
def is_valid_filename(name):
    return "(" not in name and ")" not in name
#---------------------11)Lanch Container------------------------------------------------------------------
def launch_container_with_all_files(xnat_host, project_id, command_id, wrapper_name,
                                    xnat_user, xnat_password, files):

    if not files:
        print("Keine Dateien übergeben.")
        return

    valid_files = [f for f in files if is_valid_filename(f["Name"])]
    input_file_names = [f["Name"] for f in valid_files]
    input_files_str = " ".join(input_file_names)  

    payload = {
        "project": project_id,
        "input_files": input_files_str
    }

    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_id}/wrappers/{wrapper_name}/root/project/launch"

    print("Starte Container für alle Dateien im Projekt.")
    print("Dateien:", input_file_names)
    print("Launch-URL:", url)
    print("Payload:", json.dumps(payload, indent=2))

    headers = {"Content-Type": "application/json"}
    response = requests.post(
        url, auth=(xnat_user, xnat_password),
        headers=headers, json=payload, verify=False
    )

    print("Status:", response.status_code)
    print("Antwort:", response.text)
    if response.status_code in [200, 201, 202]:
        print("Container erfolgreich gestartet mit ALLEN Dateien!")
    else:
        print("Fehler beim Container-Start:", response.status_code, response.text)



#-------------------------------------------------------------------------------------------------------
def main():
    xnat_host = "https://xnat-dev.gwdg.de"
    docker_base_image = "python:3.10"
    # Benutzerabfrage
    xnat_user = get_input("XNAT Username: ")
    xnat_password = getpass.getpass("XNAT Password: ")
    project_id = get_input("Project ID: ").strip()
    script_path = get_input("Path to the Python script: ").strip()
    # Command/Wrapper-Daten erfassen
    # Collect command/label/description from user
    mod_data = {}
    mod_data["command_name"] = get_input("Name des Commands: ")
    mod_data["command_description"] = get_input("Beschreibung des Commands: ")
    mod_data["contexts"] = ["xnat:projectData"]
    mod_data["label_name"] = mod_data["command_name"]
    mod_data["label_description"] = mod_data["command_description"]
    wrapper_name = mod_data["command_name"].replace(" ", "_").lower() + "_wrapper"
    # Docker-Image bauen & pushen
    dockerfile_path = write_dockerfile(".", os.path.basename(script_path), docker_base_image)
    local_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}:latest"
    full_image_name = build_and_push_docker_image(dockerfile_path, local_image_name)
    # Command-JSON erzeugen & hochladen
    json_file_path = create_json_file(full_image_name, os.path.basename(script_path), mod_data)



    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)
   
    try:
        command_id = get_command_wrapper_id(xnat_host, xnat_user, xnat_password, mod_data["command_name"])
        wrapper_id = get_command_wrapper_id(
            xnat_host, xnat_user, xnat_password, mod_data["command_name"], wrapper_name
        )
        print(f"Command-ID: {command_id}")
        print(f"Wrapper-ID: {wrapper_id}")
    except Exception as e:
        print(f"Fehler bei der Abfrage von Command/Wrapper ID: {e}")
        return
    enable_wrapper_sitewide(xnat_host, command_id, wrapper_name, xnat_user, xnat_password)
    enable_wrapper_for_project(xnat_host, project_id, command_id, wrapper_name, xnat_user, xnat_password)


    all_files = get_all_files_all_levels(xnat_host, project_id, xnat_user, xnat_password)
    if not all_files:
        print("Keine Dateien im Projekt gefunden.")
        return
 

    file_info = all_files[0]
    dateiname = file_info.get("Name")
    print(f"Starte nur einen Container für Datei: {dateiname} (Ebene: {file_info['Ebene']})")

    launch_container_with_all_files(
        xnat_host=xnat_host,
        project_id=project_id,
        command_id=command_id,
        wrapper_name=wrapper_name,
        xnat_user=xnat_user,
        xnat_password=xnat_password,
        files=all_files
    )

if __name__ == "__main__":
    main()


