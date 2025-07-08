import os

INPUT_DIR = "/input"
OUTPUT_DIR = "/output"
no_FILENAME = "no_output.txt"


def find_input_files(input_dir):
    
    files = []
    for root, dirs, filenames in os.walk(input_dir):
        for f in filenames:
            if f.lower().endswith((".csv", ".tsv", ".txt", ".dcm")) and f != "meta_map.csv":
                files.append(os.path.join(root, f))
    return files


def main():
    print("Inhalt von /input:", os.listdir(INPUT_DIR))
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_files = find_input_files(INPUT_DIR)
    print(f"{len(input_files)} Eingabedatei(en) gefunden.")

    if not input_files:
       
        no_path = os.path.join(OUTPUT_DIR, no_FILENAME)
        with open(no_path, "w") as f:
            f.write("Keine gültigen Eingabedateien verarbeitet.")
        print(f"Keine Ergebnisse erzeugt.  {no_path}")

    print("Inhalt von /output:", os.listdir(OUTPUT_DIR))


if __name__ == "__main__":
    main()