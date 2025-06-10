import sys# um die Kommandozeilenargumente zu lesen
import os# um mit dem Dateisystem zu arbeiten
import pandas as pd# um Daten zu verarbeiten
import subprocess# um Shell-Befehle auszuführen
#--------------------------------------------------------------------------------------------------

# Argumente von der Kommandozeile
input_file_path = sys.argv[1] if len(sys.argv) > 1 else None
output_dir = sys.argv[2] if len(sys.argv) > 2 else "/app/output"
output_file = "osa_result.csv"

'''
 in diesem teil wird eine eine liste aller argummente erstellt, die beim sartr des Programms übergeben werden soll.
wenn er sys.arg[0]>>dateiname des Skripts selbst 
wenn er sys.arg[1]>>erster Parameter, der übergeben wird 
wenn er mehr als eine Argument findet dann nimmt er nur die erste
wenn keine dann setzt er das auf none 
Wenn zwei oder mehr Argumente übergeben wurden (len(sys.argv) > 2), wird das zweite Argument (sys.argv[2]) als Ausgabeverzeichnis gesetzt.
Ordner wo das Ergebniss gespeichrt weerden soll 
'''
#-------------------------------------OSA Risk fonction calculation --------------------------------------

def calculate_osa_risk_single(row):

     #Die Spaltennamen und Zellwerte einer Zeile aus der CSV-Datei werden vereinheitlicht
    positive_answers = {"yes", "ja", "1", "x", "wahr", "true"}
    
    male_words = {"m", "mann", "maennlich", "männlich", "manlich", "männlcih"}

    #Die Spaltennamen und Zellwerte einer Zeile aus der CSV-Datei werden vereinheitlicht
    row = {k.strip().lower(): str(v).strip().lower() for k, v in row.items() if pd.notnull(v)}



    geschlecht = row.get("geschlecht", "")#Werte für das Geschlecht zu holen >>wenn nichts dann ""
    geschlecht_score = 1 if geschlecht in male_words else 0 #erhöht die werte auf 1 wenn das geschlecht in der liste ist 

    score = geschlecht_score# starten mit dem schon berechnete score 
    for key, value in row.items():#hier werden alle Spalten außer geschlecht durchgegangen
        if key != 'geschlecht':
            # Auch Teilstrings wie 'ja', 'yes' usw. als positiv zählen
            if any(p in value for p in positive_answers):
                score += 1

    risiko = "hoch" if score >= 5 else "mittel" if score >= 3 else "niedrig"
    return pd.DataFrame([{"stopbang_score": score, "osa_risiko": risiko}])

     #Die Funktion gibt das Ergebnis als kleinen DataFrame zurück>>df hat nur eine Zeile mit 2 Spalten 


#------------------------------------------------------------------------------------------------------------------------------

def main():
    print(" Start OSA-Analyse")
    os.makedirs(output_dir, exist_ok=True)#Erstllung eines Ordner für die Ausgabe>OUTPU
    print(f" Eingabedatei: {input_file_path}")

    result_df = pd.DataFrame([{"stopbang_score": "Fehler", "osa_risiko": "Keine Eingabedatei gefunden"}])#Default dataframe mit Fehlernachricht, falls etwas passiert 

    try:
        
        if input_file_path.endswith(".csv"):
            sep = ","
        elif input_file_path.endswith(".tsv"):
            sep = "\t"
            #-----------------------------------------------------------
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
#welches Trennzeichen verwendet wurde
#https://www.geeksforgeeks.org/python-sep-parameter-print/
#https://www.datacamp.com/de/tutorial/pandas
#https://www.reddit.com/r/learnpython/comments/ijvww1/i_need_to_find_out_what_separator_is_used_in_a/?tl=de
#-------------------------------------------------------------------------------------------
        df = pd.read_csv(input_file_path, sep=sep)# Lese die CSV-Datei mit dem ermittelten Trennzeichen
        print(" Gelesene Daten:")
        print(df)

        if df.empty or len(df) != 1:
            raise ValueError("Datei ist leer oder enthält mehr als einen Patienten.")

        result_df = calculate_osa_risk_single(df.iloc[0].to_dict())

    except Exception as e:
        print(f" Fehler bei der Verarbeitung von {input_file_path}: {e}")
        result_df = pd.DataFrame([{"stopbang_score": "Fehler", "osa_risiko": str(e)}])

    output_path = os.path.join(output_dir, output_file)#Dateipfad zusamnmenstellen
    print(" Speichere Ergebnis nach:", output_path)

    try:
        result_df.to_csv(output_path, index=False)#osarisiko Analyse>>tocsv gespeichert am Pfad output_path
        print(" Datei erfolgreich gespeichert.")
    except Exception as e:
        print(" Fehler beim Speichern:", e)
#https://docs.python.org/3/tutorial/errors.html
#https://www.geeksforgeeks.org/python-try-except/
    try:
        os.chmod(output_path, 0o666)
        print(" chmod erfolgreich gesetzt.")
    except Exception as e:
        print(" chmod Fehler:", e)
#https://docs.python.org/3/library/os.html#os.chmod >>#Dateiberechtigungen (permissions) der Datei output_path



    # Ausgabe von ls -al zur Fehlersuche (wie empfohlen)
    print(" ls -al Output-Verzeichnis:")
    subprocess.run(f"ls -al {output_dir}", shell=True)

    # Zusätzlich: Python-Version der Verzeichnisübersicht
    print(" Inhalt von OUTPUT_DIR:", os.listdir(output_dir))

    #Diese Zeile war game changer für den upload von File auf xnat 
    #https://groups.google.com/g/xnat_discussion/c/WgcP3VgXLX4/m/MD4kWSdMBAAJ
    #shell=True bedeutet: Der Befehl wird wie in einer normalen Bash-Shell interpretiert.
    
    #subprocess.run(...) führt diesen Befehl im Terminal aus.

if __name__ == "__main__":
    main()

#https://wiki.xnat.org/container-service/container-development-quickstart-guide
#http://www.stopbang.ca/osa/screening.php


#https://docs.python.org/3/library/sys.html#sys.argv
#https://docs.python.org/3/tutorial/stdlib.html#command-line-arguments