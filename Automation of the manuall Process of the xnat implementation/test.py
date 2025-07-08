import os
import pandas as pd
import requests
import warnings

INPUT_DIR = "/input"
OUTPUT_DIR = "/output"

 

def find_input_files(input_dir):
    """Rekursiv nach relevanten Dateien in input_dir suchen."""
    files = []
    for root, dirs, filenames in os.walk(input_dir):
        for f in filenames:
            if f.lower().endswith((".csv", ".tsv", ".txt", ".dcm")) and f != "meta_map.csv":
                files.append(os.path.join(root, f))
    return files
def process_file(filepath):
   
    try:
        if filepath.lower().endswith(".dcm"):
            return pd.DataFrame([{"filename": os.path.basename(filepath), "note": "DICOM skipped"}])
        df = pd.read_csv(filepath, sep=None, engine='python')
        result = {
            "filename": os.path.basename(filepath),
            "mean_age": df.get("age", pd.Series(dtype=float)).mean()
        }
        return pd.DataFrame([result])
    except Exception as e:
        print(f"Error processing {filepath}: {e}")
        return pd.DataFrame([{"filename": os.path.basename(filepath), "error": str(e)}])

def upload_to_xnat(local_file, xnat_level, level_id, xnat_host, session, resource="container_results"):
    """Lädt eine Datei auf eine bestimmte XNAT-Ebene hoch."""
    if not os.path.exists(local_file):
        print(f"Datei nicht vorhanden: {local_file}")
        return False
    if xnat_level == "project":
        url = f"{xnat_host}/data/projects/{level_id}/resources/{resource}/files"
    elif xnat_level == "subject":
        url = f"{xnat_host}/data/subjects/{level_id}/resources/{resource}/files"
    elif xnat_level in ("session", "experiment"):
        url = f"{xnat_host}/data/experiments/{level_id}/resources/{resource}/files"
    elif xnat_level == "scan":
        url = f"{xnat_host}/data/scans/{level_id}/resources/{resource}/files"
    else:
        print(f"Unbekanntes xnat_level: {xnat_level}")
        return False
    try:
        with open(local_file, "rb") as fp:
            resp = session.post(url, files={"file": fp}, verify=False)
        print(f"Upload {local_file} → {url}: {resp.status_code} {resp.text[:200]}")
        return resp.ok
    except Exception as e:
        print(f"Fehler beim Upload: {e}")
        return False

def main():
    print("Inhalt von /input:", os.listdir(INPUT_DIR))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    input_files = find_input_files(INPUT_DIR)
    print(f"{len(input_files)} Eingabedatei(en) gefunden.")

    # meta_map lesen
    meta_map_path = os.path.join(INPUT_DIR, "meta_map.csv")
    if os.path.exists(meta_map_path):
        meta_df = pd.read_csv(meta_map_path)
        # Mapping mit str für Kompatibilität
        file2meta = {str(row["filename"]): row for _, row in meta_df.iterrows()}
    else:
        print("Warnung: Keine meta_map.csv gefunden! Kontext-Upload nicht möglich.")
        file2meta = {}

    print("Alle gefundenen Dateien (relativ):", [os.path.relpath(f, INPUT_DIR) for f in input_files])
    print("Einträge in file2meta:", list(file2meta.keys()))

    
    xnat_host = os.environ.get("XNAT_HOST")
    xnat_user = os.environ.get("XNAT_USER")
    xnat_pass = os.environ.get("XNAT_PASS")

    if all([xnat_host, xnat_user, xnat_pass]):
        do_upload = True
        session = requests.Session()
        session.auth = (xnat_user, xnat_pass)
    else:
        do_upload = False
        print("Warnung: Kein XNAT-Upload, da XNAT-Daten nicht in Umgebungsvariablen gesetzt!")

    files_written = 0

    for i, filepath in enumerate(input_files, 1):
        filename = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, INPUT_DIR)
        output_path = os.path.join(OUTPUT_DIR, f"result_{filename}.csv")

        result_df = process_file(filepath)
        result_df.to_csv(output_path, index=False)
        print(f"[{i}] {filename} verarbeitet → {output_path}")
        files_written += 1

        meta = None
        if rel_path in file2meta:
            meta = file2meta[rel_path]
        elif filename in file2meta:
            meta = file2meta[filename]

        if do_upload and meta is not None:
            level = meta.get("xnat_level")
            level_id = meta.get("xnat_id")
            if level and level_id:
                ok = upload_to_xnat(output_path, level, level_id, xnat_host, session)
                if not ok:
                    print(f"[!] Fehler beim Upload für {filename}")
            else:
                print(f"Fehlende Metainformation für {filename}: {meta}")

    if files_written == 0:
       
        dummy_path = os.path.join(OUTPUT_DIR, "no_output_generated.txt")
        with open(dummy_path, "w") as f:
            f.write("Keine gültigen Eingabedateien verarbeitet.")
        print(f"Keine Ergebnisse erzeugt. Dummy-Datei geschrieben: {dummy_path}")

    print("Inhalt von /output:", os.listdir(OUTPUT_DIR))

if __name__ == "__main__":
    main()