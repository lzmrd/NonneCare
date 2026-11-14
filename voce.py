"""Voce di Nina: trascrizione di quello che sente e sintesi di quello che dice (ElevenLabs)."""
import subprocess

from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

from config import (ALTOPARLANTE, DATI, ELEVENLABS_API_KEY, MODELLO_TRASCRIZIONE, MODELLO_VOCE,
                    NOME_NONNA, VELOCITA_VOCE, VOCE_ID)

FREQUENZA_VOCE = 22050
_client = None


def _elevenlabs() -> ElevenLabs:
    global _client
    if _client is None:
        if not ELEVENLABS_API_KEY:
            raise RuntimeError("Manca ELEVENLABS_API_KEY nel file .env")
        _client = ElevenLabs(api_key=ELEVENLABS_API_KEY, timeout=20)
    return _client


def trascrivi(pcm: bytes) -> str:
    """Da audio PCM 16 kHz mono a testo italiano."""
    risposta = _elevenlabs().speech_to_text.convert(
        model_id=MODELLO_TRASCRIZIONE,
        file=("frase.pcm", pcm),
        file_format="pcm_s16le_16",
        language_code="it",
        tag_audio_events=False,
    )
    return (getattr(risposta, "text", "") or "").strip()


def parla(testo: str) -> None:
    """Legge il testo ad alta voce, iniziando a suonare mentre l'audio arriva."""
    _suona(_sintetizza(testo))


def _sintetizza(testo: str):
    if not VOCE_ID:
        raise RuntimeError("Manca NINA_VOCE_ID nel file .env (l'ID della voce scelta su ElevenLabs)")
    extra = {} if "multilingual_v2" in MODELLO_VOCE else {"language_code": "it"}
    audio = _elevenlabs().text_to_speech.stream(
        voice_id=VOCE_ID,
        text=testo,
        model_id=MODELLO_VOCE,
        output_format=f"pcm_{FREQUENZA_VOCE}",
        voice_settings=VoiceSettings(stability=0.6, similarity_boost=0.75, speed=VELOCITA_VOCE),
        **extra,
    )
    return audio


def _suona(pezzi) -> None:
    lettore = subprocess.Popen(
        ["aplay", "-q", "-D", ALTOPARLANTE, "-f", "S16_LE", "-r", str(FREQUENZA_VOCE), "-c", "1", "-t", "raw"],
        stdin=subprocess.PIPE,
    )
    try:
        for pezzo in pezzi:
            if pezzo:
                lettore.stdin.write(pezzo)
    finally:
        lettore.stdin.close()
        lettore.wait()


# --- Frase di riserva, per quando manca internet -------------------------------------------
# Si prepara all'avvio, quando la rete c'è, e si suona in locale quando non c'è.

FRASE_DI_RISERVA = f"Sono Nina, sono qui con te, {NOME_NONNA}."
_RISERVA = DATI / f"frase_di_riserva_{NOME_NONNA.lower()}.pcm"


def prepara_riserva() -> None:
    if not _RISERVA.exists():
        DATI.mkdir(exist_ok=True)
        _RISERVA.write_bytes(b"".join(p for p in _sintetizza(FRASE_DI_RISERVA) if p))


def parla_di_riserva() -> bool:
    """Suona la frase di riserva senza rete. Restituisce False se non è mai stata preparata."""
    if not _RISERVA.exists():
        return False
    _suona([_RISERVA.read_bytes()])
    return True
