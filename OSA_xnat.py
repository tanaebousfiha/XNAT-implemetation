import pandas as pd #Einlesen von CSV>>Speichern von Ergebnissen als CSV 
#https://pandas.pydata.org/docs/

#Variablen definiert
input_file = "patient.csv"
output_file = "osa_result.csv"
#http://www.stopbang.ca/osa/screening.php OSA Questionaire

# STOP-Bang Score berechnen#https://pandas.pydata.org/pandas-docs/stable/user_guide/io.html#csv-text-files
def calculate_stopbang(row):#row ist ein Dictionary mit den Patientendaten
    row = {k.strip().lower(): str(v).strip().lower() for k, v in row.items()}
# Schlüssel (k) und Werte (v)>>strip:entfernt leerzeichen>>lower:klwinbuchstaben>>

    # initialiserung der Variablen 
    score = 0

    # Geschlecht
    if row.get("geschlecht") in ["m", "mann", "männlich", "manlich"]:
        score += 1

    # Alle anderen Fragen ("yes" = 1 Punkt)
    for key, value in row.items():#über alle Schlüssel-Wert-Paare in einem Dictionary gehen(items)
        if key != "geschlecht" and value == "yes":
            score += 1

    
    if score >= 5:
        risiko = "hoch"
    elif score >= 3:
        risiko = "mittel"
    else:
        risiko = "niedrig"

    return score, risiko


def main():
    try:#Fehlerbehandlungsblock
        df = pd.read_csv(input_file)#panda liest die csv datei 
        if df.empty or len(df) != 1:#ob die datei leer oder mehr als eine zeile hat
            print("Die Datei muss genau eine Zeile mit Patientendaten enthalten.")
            return

        score, risiko = calculate_stopbang(df.iloc[0].to_dict())#data frame>.iloc[0] gibt die erste Zeile zurück 
        #und to_dict() wandelt sie in ein Dictionary um>

        # Ergebnis speichern
        result_df = pd.DataFrame([{"stopbang_score": score, "osa_risiko": risiko}])#erstellt eine Tabelle (DataFrame) aus dieser einen Zeile
        result_df.to_csv(output_file, index=False)# speichert die Tabelle in einer CSV-Datei>index=False: keine Zeilenindizes in der CSV-Datei
        print(f"Ergebnis gespeichert in: {output_file}")

    except Exception as e:#Fehlerbehandlungsblock
        print(f"Fehler beim Verarbeiten der Datei: {e}")

if __name__ == "__main__":
    main()

#HAWKKI
