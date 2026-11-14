"""Registro della radio: ogni evento in una riga, legata alla precedente con un hash.

È la base della "scatola nera": se qualcuno modifica o cancella una riga, la catena
degli hash non torna più. Il sigillo giornaliero sulla blockchain si aggiunge dopo.
"""
import hashlib
import json
from datetime import datetime

from config import DATI

FILE = DATI / "registro.jsonl"
_ultimo_hash = None


def _hash(testo: str) -> str:
    return hashlib.sha256(testo.encode("utf-8")).hexdigest()


def _leggi_ultimo_hash() -> str:
    if not FILE.exists():
        return "0" * 64
    ultima = ""
    with FILE.open(encoding="utf-8") as f:
        for riga in f:
            if riga.strip():
                ultima = riga
    return json.loads(ultima)["hash"] if ultima else "0" * 64


def annota(tipo: str, **dati) -> dict:
    """Aggiunge un evento al registro e restituisce la riga scritta."""
    global _ultimo_hash
    if _ultimo_hash is None:
        _ultimo_hash = _leggi_ultimo_hash()
    voce = {"ora": datetime.now().isoformat(timespec="seconds"), "tipo": tipo, **dati, "precedente": _ultimo_hash}
    voce["hash"] = _hash(json.dumps(voce, ensure_ascii=False, sort_keys=True))
    DATI.mkdir(exist_ok=True)
    with FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(voce, ensure_ascii=False, sort_keys=True) + "\n")
    _ultimo_hash = voce["hash"]
    return voce


def verifica() -> tuple[bool, str]:
    """Ricalcola tutta la catena. Restituisce (integro, spiegazione)."""
    if not FILE.exists():
        return True, "Registro vuoto."
    precedente = "0" * 64
    with FILE.open(encoding="utf-8") as f:
        for numero, riga in enumerate(f, 1):
            if not riga.strip():
                continue
            voce = json.loads(riga)
            atteso = voce.pop("hash")
            if voce.get("precedente") != precedente:
                return False, f"Riga {numero}: manca o è stata spostata una riga prima di questa."
            if _hash(json.dumps(voce, ensure_ascii=False, sort_keys=True)) != atteso:
                return False, f"Riga {numero}: il contenuto è stato modificato."
            precedente = atteso
    return True, f"Registro integro, ultimo hash {precedente[:12]}…"


if __name__ == "__main__":
    print(verifica()[1])
