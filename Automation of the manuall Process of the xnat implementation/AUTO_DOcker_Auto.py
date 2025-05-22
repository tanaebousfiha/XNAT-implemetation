'''the main idea of my Skript is to take the inpust Skript and build the 
docker image combinen the information in the json file and evrything with the Request an xnat senden:::::
alll the Stept that i did now manually must be done by the Skript'''

import json
import requests 
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