#https://docs.docker.com/get-started/docker-concepts/building-images/writing-a-dockerfile/
#https://hub.docker.com/_/python

FROM python:3.11-slim  
#Python 3.11 Docker image/smaller and faster image in the docker hub
#https://hub.docker.com/_/python

# Arbeitsverzeichnis setzen>>commands will execute in this directory
WORKDIR /app
#https://docs.docker.com/reference/dockerfile/#workdir



# Systempakete installieren (für vollen Support)
#https://docs.docker.com/build/building/best-practices/#run
RUN apt-get update && \                        
    apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

    
# Python-Abhängigkeiten installieren
#https://docs.docker.com/reference/dockerfile/#copy
#https://pip.pypa.io/en/stable/cli/pip_install/#cmdoption-no-cache-dir
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Eingabe-/Ausgabe-Verzeichnisse vorbereiten
RUN mkdir -p /app/input /app/output
ENV INPUT_DIR=/app/input
ENV OUTPUT_DIR=/app/output
#1)Erstellt Input-/Output-Verzeichnisse
#2)Setzt Umgebungsvariablen für die Eingabe- und Ausgabeverzeichnisse
#3)Die Umgebungsvariablen INPUT_DIR und OUTPUT_DIR werden auf die Verzeichnisse /app/input und /app/output gesetzt.
# Skript kopieren
COPY OSA_xnat.py .

# Standardbefehl
CMD ["python", "OSA_xnat.py"]
#https://docs.docker.com/reference/dockerfile/#cmd
#i found xnat dockerfile exemples on https://github.com/NrgXnat/docker-images
# alles zusammengepasst mit HAWKKI