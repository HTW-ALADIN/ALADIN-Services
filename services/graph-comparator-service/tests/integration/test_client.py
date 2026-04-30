import json
import sys
from pathlib import Path

import urllib.request
import urllib.error

SERVICE_URL = "http://localhost:8000"


def check_health() -> None:
    try:
        with urllib.request.urlopen(f"{SERVICE_URL}/health", timeout=3) as r:
            print(f"[health] {r.status} -> {r.read().decode()}")
    except urllib.error.URLError as e:
        print(f"[health] Service nicht erreichbar: {e}")
        sys.exit(1)


def compare(reference: dict, candidate: dict) -> None:
    # Vergleichs-Request an die API schicken und Ergebnis ausgeben.
    # dumps = dict → JSON-String & loads = JSON-String → dict
    payload = json.dumps({"reference": reference, "candidate": candidate}).encode()
    
    # POST-Request an /compare schicken, Antwort lesen und ausgeben.
    req = urllib.request.Request(
        f"{SERVICE_URL}/compare",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=5) as r:
        # (read) liest die Rohdaten aus r (HTTP-Response) Das Ergebnis sind Bytes.
        # (decode) wandelt diese Bytes in einen String um.
        # (json.loads) wandelt diesen String in ein Dict um.
        result = json.loads(r.read().decode())
    # print(f"[compare] Status {r.status} -> {result}")
    print(json.dumps(result, indent=2, ensure_ascii=False)) # Schönes JSON-Format


def load_json(path: str) -> dict:
    # Lädt eine JSON-Datei und gibt sie als dict zurück.
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    # Läuft der Container?
    check_health()

    # Wenn 3 Argumente angegeben sind (Skriptname + 2 Dateien), lade die Dateien.
    # Sonst (= Skriptname allein) nimm die Dummy-JSONs.
    if len(sys.argv) == 3:
        ref_path = sys.argv[1]
        cand_path = sys.argv[2]
        print(f"[info] verwende Dateien: {sys.argv[1]} vs {sys.argv[2]}")
    else:
        # Standardpfade, wenn nichts angegeben wird
        print("[info] Keine Dateien angegeben, nutze Standard-Testdaten.")
        ref_path = "test_musterloesung.json"
        cand_path = "test_studentischeloesung.json"

    try:
        ref = load_json(ref_path)
        cand = load_json(cand_path)
        print(f"[info] Vergleiche: {ref_path} vs {cand_path}")
        compare(ref, cand)
    except FileNotFoundError as e:
        print(f"[error] Datei nicht gefunden: {e}")