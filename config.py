"""Configurazione della radio: legge il file .env e le impostazioni.

Ogni valore si può cambiare nel .env senza toccare il codice.
"""
import os
from pathlib import Path

CARTELLA = Path(__file__).resolve().parent
DATI = CARTELLA / "dati"  # dati reali della nonna: restano sul Raspberry, fuori dal repository


def _carica_env(percorso: Path) -> None:
    if not percorso.exists():
        return
    for riga in percorso.read_text(encoding="utf-8").splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        chiave, valore = riga.split("=", 1)
        os.environ.setdefault(chiave.strip(), valore.strip().strip('"').strip("'"))


_carica_env(CARTELLA / ".env")


def _leggi(nome: str, predefinito: str = "") -> str:
    return os.environ.get(nome, predefinito).strip()


# Chiavi (ANTHROPIC_API_KEY la legge da sola la libreria di Anthropic)
ELEVENLABS_API_KEY = _leggi("ELEVENLABS_API_KEY")
TELEGRAM_TOKEN = _leggi("TELEGRAM_TOKEN")

# Cervello: Haiku per provare, Opus per la demo
MODELLO = _leggi("NINA_MODELLO", "claude-haiku-5-5")

# Voce e trascrizione (ElevenLabs)
VOCE_ID = _leggi("NINA_VOCE_ID")
MODELLO_VOCE = _leggi("NINA_MODELLO_VOCE", "eleven_flash_v2_5")
MODELLO_TRASCRIZIONE = _leggi("NINA_MODELLO_TRASCRIZIONE", "scribe_v2")
VELOCITA_VOCE = float(_leggi("NINA_VELOCITA_VOCE", "0.9"))

# Audio: sul Raspberry la webcam si chiama "Camera" e l'uscita è il jack "Headphones"
MICROFONO = _leggi("NINA_MICROFONO", "plughw:CARD=Camera,DEV=0")
ALTOPARLANTE = _leggi("NINA_ALTOPARLANTE", "plughw:CARD=Headphones,DEV=0")
VAD_AGGRESSIVITA = int(_leggi("NINA_VAD", "2"))  # 0 = sente tutto, 3 = solo voce chiara

# Persona
NOME_NONNA = _leggi("NINA_NOME_NONNA", "Rosa")
