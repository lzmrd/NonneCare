"""Bacheca tra il bot della famiglia e la radio.

Sono due programmi separati (famiglia.py e main.py) che si parlano con qualche file in dati/:
i messaggi da annunciare alla nonna e la pausa dell'ascolto.
"""
import json
import os
import time
from datetime import datetime

from config import DATI

ANNUNCI = DATI / "da_annunciare.jsonl"
PAUSA = DATI / "pausa_fino.txt"


def aggiungi_annuncio(testo: str, mittente: str) -> None:
    DATI.mkdir(exist_ok=True)
    with ANNUNCI.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ora": datetime.now().isoformat(timespec="seconds"), "da": mittente, "testo": testo},
                           ensure_ascii=False) + "\n")


def prendi_annunci() -> list[dict]:
    """Prende tutti gli annunci in attesa e svuota la coda (il rename evita di perderne mentre il bot scrive)."""
    if not ANNUNCI.exists():
        return []
    in_lettura = ANNUNCI.with_suffix(".in_lettura")
    os.replace(ANNUNCI, in_lettura)
    annunci = [json.loads(r) for r in in_lettura.read_text(encoding="utf-8").splitlines() if r.strip()]
    in_lettura.unlink()
    return annunci


def metti_in_pausa(minuti: int) -> None:
    DATI.mkdir(exist_ok=True)
    if minuti <= 0:
        PAUSA.unlink(missing_ok=True)
    else:
        PAUSA.write_text(str(time.time() + minuti * 60))


def in_pausa() -> bool:
    try:
        return time.time() < float(PAUSA.read_text())
    except (FileNotFoundError, ValueError):
        return False
