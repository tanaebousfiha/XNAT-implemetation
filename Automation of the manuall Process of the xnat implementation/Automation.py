'''THE Skript folows the folowing the steps:
1) the Skript must have a input and a  result output file 
2) build the dockerfile
3)create the docker image 
4)create json file 
5) send the json file to xnat 
6) enable the commad 
7) run the conatiner in xnat '''

#-----------------Bibliotheken---------------------------------------------------------

import json
import requests  #https://wiki.xnat.org/container-service/container-service-api
import os 
import subprocess
#------------------------------------esrtmal Skript from the users Fragen-----------------------------------------------------
def check_user_skript(skript_path):     #https://realpython.com/python-import/#importing-a-source-file-directly
    if not os.path.isfile(skript_path):
        print(f"Datei nicht gefunden: {skript_path}")
        return False 
    if not skript_path.endswith(".py"):
        print("Datei nicht korrekt, bitte eine .py Datei angeben.")
        return False 
    return True 
#------------------------------------dann kommt dockerfile ausfüllen------------------------------------------------------

def dockerfile(script_filename, docker_base_image):
    dockerfile_content = f"""FROM {docker_base_image}
WORKDIR /app
COPY {script_filename} /app/
#RUN pip install -r requirements.txt
CMD ["python", "/app/{script_filename}"]
"""
    dockerfile_path = "Dockerfile"
    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile created at {dockerfile_path}")
    return dockerfile_path
#--------------------------------------------------------------------------------------------------------------------------n-----
#https://www.reddit.com/r/learnpython/comments/qn0quk/how_to_have_user_input_change_my_python_code/
#hawkki korrektur
def get_input(prompt):
    while True:
        value = input(prompt)
        if value.strip():
            return value
        else:
            print("Cannot be empty.")

def modification():
    data = {}
    data["command_name"] = get_input("What is the name of the command in XNAT: ")
    data["command_description"] = get_input("What is the description of the command in XNAT: ")
    data["label_name"] = get_input("What is the name of the Label in XNAT: ")
    data["label_description"] = get_input("What is the description of the Label in XNAT: ")
    return data

#-----------------------------------json Fileerstellen-----------------------------------------------------------------


def create_json_file(docker_image, script_filename, mod_data):
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
                "name": mod_data["command_name"],
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
                        "matcher": "@.name =~ \".*\\.(csv|tsv|txt)$\"",
                        "required": True,
                        "load-children": True,
                        "derived-from-wrapper-input": "csv_resource"
                    },
                    {
                        "name": "input_file_name",
                        "type": "string",
                        "required": True,
                        "provides-value-for-command-input": "INPUT_FILE",
                        "user-settable": False,
                        "derived-from-wrapper-input": "input_file",
                        "derived-from-xnat-object-property": "name"
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


#-------------------------------------JSON is being written ------------------------------------------------------------------
#https://www.geeksforgeeks.org/writing-to-file-in-python/

    with open("command.json", "w") as json_out:
        json.dump(json_file, json_out, indent=4)
        print(f"JSON file created at command.json")
    return "command.json"
#-------------------------------------JSON is being sent to XNAT----------------------------------------------------------
#https://www.datacamp.com/tutorial/making-http-requests-in-python
#https://wiki.xnat.org/container-service/container-service-api
#https://stackoverflow.com/questions/22567306/how-to-upload-file-with-python-requests

def send_json_to_xnat(json_file_path, xnat_url, xnat_user, xnat_password): 
    url = f"{xnat_url}/xapi/commands"
    print(f"Uploading command to {url}")
    with open(json_file_path, "r") as f:
        response = requests.post(url, auth=(xnat_user, xnat_password), json=json.load(f))
    # The following line was removed because 'command_data' is not defined and the request is already made above.
    if response.status_code == 200:
        print("Command uploaded successfully.")
    elif response.status_code == 201:
        print("Command created successfully.")
    elif response.status_code == 409:
        print("Command already exists.")
    else:
        print(f"Failed to upload command: {response.status_code} - {response.text}")

#------------------------------------enable the command in Projekt und commands ----------------------------------------------------------------------------

def enable_command_in_project(xnat_host, project_id, command_name, xnat_user, xnat_password): 
    url = f"{xnat_host}/xapi/projects/{project_id}/commands/{command_name}"
    headers = {"Content-Type": "application/json"}# in welchem Format die im Request enthaltenden Daten gesendet werden.
    response = requests.put(url, auth=(xnat_user, xnat_password), headers=headers)
    if response.status_code == 200:
        print(f"Command '{command_name}' enabled in project '{project_id}'.")
    else:
        print(f"Failed to enable command: {response.status_code} - {response.text}")
        
    #------------------------------------------run container in xnat ---------------------------------------------------
def run_container_in_xnat(xnat_host, project_id, session_id, command_name, xnat_user, xnat_password):
    url = f"{xnat_host}/xapi/projects/{project_id}/sessions/{session_id}/commands/{command_name}"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, auth=(xnat_user, xnat_password), headers=headers)
    if response.status_code == 200:
        print(f"Container '{command_name}' started successfully.")
    else:
        print(f"Failed to start container: {response.status_code} - {response.text}")
        

#------------------------------------------build docker image -----------------------------------------------------

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

#------------------------------------------main part -----------------------------------------------------

def main():
   
    xnat_host = get_input("XNAT WEB URL:")
    xnat_user = get_input("XNAT Username:")
    xnat_password = get_input("XNAT Password: ")
    project_id = get_input("Project ID:")
    session_id = get_input("Session ID:")
    script_path = get_input("Path to the Python script:")
    docker_base_image = get_input(" Docker Name base image:")

    #checking the user skript 
    if not check_user_skript(script_path):
        return

    mod_data = modification()

    # Create Dockerfile
    dockerfile_path = dockerfile(os.path.basename(script_path), docker_base_image)

    # Build Docker image
    docker_image_name = f"{mod_data['command_name'].lower().replace(' ', '_')}:latest"
    build_docker_image(dockerfile_path, docker_image_name)

    # Create JSON file
    json_file_path = create_json_file(docker_image_name, os.path.basename(script_path), mod_data)

    # Send JSON to XNAT
    send_json_to_xnat(json_file_path, xnat_host, xnat_user, xnat_password)

    # Enable command in project
    enable_command_in_project(xnat_host, project_id, mod_data["command_name"], xnat_user, xnat_password)

    # Run container in XNAT
    run_container_in_xnat(xnat_host, project_id, session_id, mod_data["command_name"], xnat_user, xnat_password)

    if __name__ == "__main__":
        main()