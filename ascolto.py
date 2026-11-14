"""Ascolto: la radio si accorge da sola quando qualcuno parla.

Il rilevamento della voce (webrtcvad) gira tutto sul Raspberry: in cloud va solo
la frase già ritagliata. Il microfono resta chiuso mentre Nina parla o suona
(half-duplex), così Nina non risponde a se stessa.
"""
import collections
import subprocess
import time
from typing import BinaryIO, Optional

import webrtcvad

from config import MICROFONO, VAD_AGGRESSIVITA

FREQUENZA = 16000
MS_FRAME = 30
BYTE_FRAME = FREQUENZA * MS_FRAME // 1000 * 2  # 960 byte: 16 bit, mono

FRAME_INIZIO = 10        # finestra di 300 ms per capire che è iniziata una frase
SOGLIA_INIZIO = 0.7      # ...se almeno il 70% è voce
FRAME_FINE = 30          # 900 ms...
SOGLIA_FINE = 0.9        # ...quasi tutti di silenzio chiudono la frase
DURATA_MASSIMA_S = 20
VOCE_MINIMA_S = 0.4      # sotto questa soglia è un rumore, non una frase


def ritaglia_frase(flusso: BinaryIO, vad: webrtcvad.Vad, timeout: Optional[float] = None) -> Optional[bytes]:
    """Legge audio PCM 16 kHz mono dal flusso e restituisce la prima frase completa.

    Restituisce None se il flusso finisce o se nessuno parla entro `timeout` secondi.
    """
    finestra: collections.deque = collections.deque(maxlen=FRAME_INIZIO)
    coda: collections.deque = collections.deque(maxlen=FRAME_FINE)
    frase: Optional[bytearray] = None
    frame_voce = 0
    inizio_attesa = time.monotonic()

    while True:
        frame = flusso.read(BYTE_FRAME)
        if len(frame) < BYTE_FRAME:
            # flusso finito (succede con i file di prova): tengo la frase se è abbastanza lunga
            if frase is not None and frame_voce * MS_FRAME / 1000 >= VOCE_MINIMA_S:
                return bytes(frase)
            return None
        voce = vad.is_speech(frame, FREQUENZA)

        if frase is None:
            finestra.append((frame, voce))
            voci = sum(v for _, v in finestra)
            if len(finestra) == FRAME_INIZIO and voci >= SOGLIA_INIZIO * FRAME_INIZIO:
                # inizia la frase, compresi i 300 ms appena prima
                frase = bytearray(b"".join(f for f, _ in finestra))
                frame_voce = voci
                coda.clear()
            elif timeout is not None and time.monotonic() - inizio_attesa > timeout:
                return None
            continue

        frase.extend(frame)
        frame_voce += voce
        coda.append(voce)
        durata = len(frase) / (FREQUENZA * 2)
        silenzio = len(coda) == FRAME_FINE and coda.count(False) >= SOGLIA_FINE * FRAME_FINE
        if silenzio or durata >= DURATA_MASSIMA_S:
            if frame_voce * MS_FRAME / 1000 >= VOCE_MINIMA_S:
                return bytes(frase)
            # era solo un rumore: ricomincio ad aspettare
            frase = None
            finestra.clear()


def ascolta_frase(timeout: Optional[float] = None) -> Optional[bytes]:
    """Apre il microfono, aspetta una frase, chiude il microfono e la restituisce."""
    proc = subprocess.Popen(
        ["arecord", "-q", "-D", MICROFONO, "-f", "S16_LE", "-r", str(FREQUENZA), "-c", "1", "-t", "raw"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        frase = ritaglia_frase(proc.stdout, webrtcvad.Vad(VAD_AGGRESSIVITA), timeout)
        if frase is None and proc.poll() is not None:
            errore = proc.stderr.read().decode(errors="replace").strip()
            raise RuntimeError(f"Il microfono {MICROFONO} non risponde: {errore or 'arecord si è chiuso'}")
        return frase
    finally:
        proc.terminate()
        proc.wait()
