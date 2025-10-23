import os
import csv
import tempfile
import shutil
from pyxnat import Interface

# Verbindung zu XNAT (env vars müssen gesetzt sein)
xnat_host = os.environ["XNAT_HOST"]
xnat_user = os.environ["XNAT_USER"]
xnat_pass = os.environ["XNAT_PASS"]

xnat = Interface(server=xnat_host, user=xnat_user, password=xnat_pass)

# Projekt-ID (optional via env XNAT_PROJECT)
project_id = os.environ.get("XNAT_PROJECT", "tanae_osa_Pred")
project = xnat.select.project(project_id)

# Temp- und Output-Verzeichnisse
tmp_dir = tempfile.mkdtemp()
output_dir = "/output"
os.makedirs(output_dir, exist_ok=True)

all_csvs = []

# --- Project-level resources (optional) ---
try:
    for pres_name in project.resources().get():
        pres_obj = project.resource(pres_name)
        for fname in pres_obj.files().get():
            if fname.lower().endswith(".csv"):
                local_name = f"{project_id}_{pres_name}_{fname}"
                local_path = os.path.join(tmp_dir, local_name)
                print(f"Downloading project resource {fname} -> {local_path}")
                pres_obj.file(fname).download(local_path)
                all_csvs.append(local_path)
except Exception as e:
    print(f"Projekt-Ressourcen: {e}")

# --- Subjects -> Sessions -> Scans ---
for subj_label in project.subjects().get():
    subject_obj = project.subject(subj_label)

    # Subject-level resources
    try:
        for sres_name in subject_obj.resources().get():
            sres_obj = subject_obj.resource(sres_name)
            for fname in sres_obj.files().get():
                if fname.lower().endswith(".csv"):
                    local_name = f"{subj_label}_{sres_name}_{fname}"
                    local_path = os.path.join(tmp_dir, local_name)
                    print(f"Downloading subject resource {fname} -> {local_path}")
                    sres_obj.file(fname).download(local_path)
                    all_csvs.append(local_path)
    except Exception as e:
        print(f"Subject-Ressourcen für {subj_label}: {e}")

    # Sessions (Experiments)
    for sess_label in subject_obj.experiments().get():
        session_obj = subject_obj.experiment(sess_label)

        # Session-level resources
        try:
            for sres_name in session_obj.resources().get():
                sres_obj = session_obj.resource(sres_name)
                for fname in sres_obj.files().get():
                    if fname.lower().endswith(".csv"):
                        local_name = f"{subj_label}_{sess_label}_{sres_name}_{fname}"
                        local_path = os.path.join(tmp_dir, local_name)
                        print(f"Downloading session resource {fname} -> {local_path}")
                        sres_obj.file(fname).download(local_path)
                        all_csvs.append(local_path)
        except Exception as e:
            print(f"Session-Ressourcen für {sess_label}: {e}")

        # Scans
        for scan_label in session_obj.scans().get():
            scan_obj = session_obj.scan(scan_label)

            # Scan-level resources
            try:
                for rname in scan_obj.resources().get():
                    res_obj = scan_obj.resource(rname)
                    for fname in res_obj.files().get():            # <-- korrekt: .get() liefert Dateinamen
                        if fname.lower().endswith(".csv"):
                            local_name = f"{subj_label}_{sess_label}_{scan_label}_{rname}_{fname}"
                            local_path = os.path.join(tmp_dir, local_name)
                            print(f"Downloading scan resource {fname} -> {local_path}")
                            res_obj.file(fname).download(local_path)  # <-- korrekt: res_obj.file(fname)
                            all_csvs.append(local_path)
            except Exception as e:
                print(f"Scan-Ressourcen für {scan_label}: {e}")

# Ergebnisprüfung
if not all_csvs:
    print("Keine CSV-Dateien gefunden.")
else:
    print(f"Heruntergeladene CSVs: {all_csvs}")

# Beispiel-Verarbeitung: copy + combine
for csv_file in all_csvs:
    shutil.copy(csv_file, os.path.join(output_dir, os.path.basename(csv_file)))

result_file_path = os.path.join(output_dir, "result.csv")
with open(result_file_path, "w", newline="") as outfile:
    writer = None
    for csv_file in all_csvs:
        with open(csv_file, "r") as infile:
            reader = csv.DictReader(infile)
            if writer is None:
                writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
                writer.writeheader()
            for row in reader:
                writer.writerow(row)

print(f"Ergebnisse geschrieben nach {result_file_path}")

# Aufräumen
shutil.rmtree(tmp_dir)
print("Temporary files cleaned up. Fertig!")
