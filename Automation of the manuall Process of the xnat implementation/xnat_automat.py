'''the main idea of my Skript is to take the inpust Skript and build the 
docker image combinen the information in the json file and evrything with the Request an xnat senden:::::
alll the Stept that i did now manually must be done by the Skript'''

import json
import requests 
import os 


def user_Skript(input,output):#https://realpython.com/python-import/#importing-a-source-file-directly
    unser_skript_path =input("Please provide the path to your Python script (.py): ").strip()
    if not os.path.isfile(unser_skript_path):
        print(f"File not found: {unser_skript_path}")
        return
    if not unser_skript_path.endswith(".py"):
        print("File invalid, please provide a file with python script")

def dockerfile(user_Skript,docker_image):
    dockerfile_content=f"""
    FROM python:3.10-slim
    WORKDIR /app
    Copy {user_Skript /app/user_Skript}
    CMD ["python3", "/app/user_Skript"]
    """
    with open("Dockerfile","w")as f:
        f.write(dockerfile_content)
    print(f"Dockerfile written to {dockerfile_path}")
















if __name__ == "__main__":
    # Get the path to the Python script from the user
    user_script_path = input("Please provide the path to your Python script (.py): ").strip()

    # Get the Docker image name from the user
    docker_image = input("Please provide the Docker image name (e.g., 'python:3.10-slim'): ").strip()

    # Create Dockerfile
    dockerfile_path = dockerfile(user_script_path, docker_image)

       