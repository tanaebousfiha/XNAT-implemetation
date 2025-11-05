import sys# um die Kommandozeilenargumente zu lesen
import os# um mit dem Dateisystem zu arbeiten
import pandas as pd# um Daten zu verarbeiten
import subprocess# um Shell-Befehle auszuführen
#--------------------------------------------------------------------------------------------------

# Argumente von der Kommandozeile
input_file_path = sys.argv[1] if len(sys.argv) > 1 else None
output_dir = sys.argv[2] if len(sys.argv) > 2 else "/app/output"
output_file = "osa_result.csv"

#-------------------------------------OSA Risk fonction calculation --------------------------------------

def calculate_osa_risk_single(row):

    positive_answers = {"yes", "ja", "1", "x", "wahr", "true"}
    
    male_words = {"m", "mann", "maennlich", "männlich", "manlich", "männlcih"}

    row = {k.strip().lower(): str(v).strip().lower() for k, v in row.items() if pd.notnull(v)}



    geschlecht = row.get("geschlecht", "")
    geschlecht_score = 1 if geschlecht in male_words else 0 
    score = geschlecht_score
    for key, value in row.items():
        if key != 'geschlecht':
            
            if any(p in value for p in positive_answers):
                score += 1

    risiko = "hoch" if score >= 5 else "mittel" if score >= 3 else "niedrig"
    return pd.DataFrame([{"stopbang_score": score, "osa_risiko": risiko}])

     


#------------------------------------------------------------------------------------------------------------------------------

def main():
    print(" Start OSA-Analyse")
    os.makedirs(output_dir, exist_ok=True)
    print(f" Eingabedatei: {input_file_path}")

    result_df = pd.DataFrame([{"stopbang_score": "Fehler", "osa_risiko": "Keine Eingabedatei gefunden"}])

    try:
        
        if input_file_path.endswith(".csv"):
            sep = ","
        elif input_file_path.endswith(".tsv"):
            sep = "\t"
            
        elif input_file_path.endswith(".txt"):
            with open(input_file_path, 'r', encoding='utf-8') as f:
                first_line = f.readline()
                if first_line.count(';') > first_line.count(',') and first_line.count(';') > first_line.count('\t'):
                    sep = ';'
                elif first_line.count('\t') > first_line.count(','):
                    sep = '\t'
                else:
                    sep = ','
        else:
            sep = ","

#-------------------------------------------------------------------------------------------
        df = pd.read_csv(input_file_path, sep=sep)
        print(" Gelesene Daten:")
        print(df)

        if df.empty or len(df) != 1:
            raise ValueError("Datei ist leer oder enthält mehr als einen Patienten.")

        result_df = calculate_osa_risk_single(df.iloc[0].to_dict())

    except Exception as e:
        print(f" Fehler bei der Verarbeitung von {input_file_path}: {e}")
        result_df = pd.DataFrame([{"stopbang_score": "Fehler", "osa_risiko": str(e)}])

    output_path = os.path.join(output_dir, output_file)
    print(" Speichere Ergebnis nach:", output_path)

    try:
        result_df.to_csv(output_path, index=False)
        print(" Datei erfolgreich gespeichert.")
    except Exception as e:
        print(" Fehler beim Speichern:", e)
   
    print(" ls -al Output-Verzeichnis:")
    subprocess.run(f"ls -al {output_dir}", shell=True)

    
    print(" Inhalt von OUTPUT_DIR:", os.listdir(output_dir))

if __name__ == "__main__":
    main()

