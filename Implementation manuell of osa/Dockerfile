FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY OSA_xnat.py .

CMD ["python", "OSA_xnat.py"]

