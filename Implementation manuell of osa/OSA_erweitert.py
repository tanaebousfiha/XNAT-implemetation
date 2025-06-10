import pandas as pd
import os
import sys
import subprocess

output_file = "osa_result.csv"# Name der Ausgabedatei

def calculate_osa_risk_single(row):
    positive_answers = {"yes", "ja", "x", "whar", "true", "1", "wahr"}
    negative_answers = {"no", "nein", "0", "falsch", "false", "nix", "nichts", "nichts davon"}
    man_words = {"m", "mann", "maennlich", "männlich", "manlich"}
    woman_words = {"w", "frau", "weiblich", "woman", "feminine"}
    row = {k.strip().lower(): str(v).strip().lower() for k, v in row.items() if pd.notnull(v)}
    score = 0
    for value in row.values():
        if value in positive_answers or value in man_words:
            score += 1
        # weder noch = keine Erhöhung
    risiko = "hoch" if score >= 5 else "mittel" if score >= 3 else "niedrig"
    return pd.DataFrame([{"stopbang_score": score, "osa_risiko": risiko}])

def write_error_result(output_path, message="bitte die fragen nochmal beantworten"):
    pd.DataFrame([{"stopbang_score": "Fehler", "osa_risiko": message}]).to_csv(output_path, index=False)

def main(input_file_path, output_dir="/app/output"):
    print("Start Osa-Analyse")
    os.makedirs(output_dir, exist_ok=True)
    input_path = input_file_path
    output_path = os.path.join(output_dir, output_file)

    
    if not input_path or not os.path.exists(input_path):
        print("Fehler: Keine oder ungültige Eingabedatei angegeben.")
        write_error_result(output_path)
        return

   
    if os.path.isdir(input_path):
        found = False
        for fname in os.listdir(input_path):
            if fname.lower().endswith((".csv", ".tsv", ".txt")):
                input_path = os.path.join(input_path, fname)
                found = True
                break
        if not found:
            print("Fehler: Keine CSV-, TSV- oder TXT-Datei im Verzeichnis gefunden.")
            write_error_result(output_path)
            return

    ext = os.path.splitext(input_path)[1].lower()
    delimiter = ',' if ext == ".csv" else '\t' if ext == ".tsv" else ','

    try:
        df = pd.read_csv(input_path, delimiter=delimiter, dtype=str, encoding='utf-8')
    except Exception as e:
        print(f"Fehler beim Einlesen der Datei: {e}")
        write_error_result(output_path)
        return


    for col in df.select_dtypes(['object']):
        df[col] = df[col].str.strip()


    if df.empty or len(df) != 1:
        print("Fehler: Datei ist leer oder enthält mehr als einen Patienten.")
        write_error_result(output_path)
        return

    
    if df.isna().any().any():
        print("Die Datei enthält leere Zellen.")
        write_error_result(output_path, "Bitte alle Fragen beantworten und Datei erneut einreichen.")
        return

   
    result_df = calculate_osa_risk_single(df.iloc[0].to_dict())
    result_df.to_csv(output_path, index=False)
    print(f"Ergebnis gespeichert unter: {output_path}")

    subprocess.run(f"ls -al {output_dir}", shell=True)

if __name__ == "__main__":
    input_file_path = sys.argv[1] if len(sys.argv) > 1 else None
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "/app/output"
    main(input_file_path, output_dir)