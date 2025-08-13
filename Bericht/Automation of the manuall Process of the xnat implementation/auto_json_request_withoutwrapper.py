'''the main idea of my Skript is to take the inpust Skript and build the 
docker image combinen the information in the json file and evrything with the Request an xnat senden:::::
alll the Stept that i did now manually must be done by the Skript'''

import json
import requests #https://wiki.xnat.org/container-service/container-service-api
import os 

#------------------------------------esrtmal Skript from the users Fragen-----------------------------------------------------
def check_user_Skript(skript_path):#https://realpython.com/python-import/#importing-a-source-file-directly
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
    url = f"{xnat_host}/xapi/commands"
    print(f"Uploading command to {url}")
    with open(json_file_path, "r") as f:
        response = requests.post(url, auth=(xnat_user, xnat_password), json=json.load(f))
    headers = {"Content-Type": "application/json"}# in welchem Format die im Request enthaltenden Daten gesendet werden.
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
#ich brauche ertmal eine Wrapper ID um den container zu starten 




















if __name__ == "__main__":

    script_path = input("Pfad zu Ihrem Python-Skript (.py): ").strip()
    if not check_user_Skript(script_path):
        exit(1)

    # Docker-Basis-Image abfragen
    docker_image = input("Docker-Image-Name, z.B. 'python:3.10-slim': ").strip()

    # Dateinamen extrahieren und Dockerfile schreiben
    script_filename = os.path.basename(script_path)
    dockerfile_path = dockerfile(script_filename, docker_image)

    print(f"Dockerfile created at {dockerfile_path}")


    #korrektur with HAWK Ki 