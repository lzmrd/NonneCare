"""La Radio di Nina: ascolta, capisce, risponde.

    python main.py            la radio vera: microfono, Claude, voce
    python main.py --eco      prova dell'audio: ripete quello che sente, senza Claude
    python main.py --testo    prova del cervello: scrivi e leggi, senza audio
"""
import argparse
import subprocess
import sys
import time

import registro
import strumenti
from config import ALTOPARLANTE, DATI


def suona_canzone() -> None:
    canzoni = sorted((DATI / "musica").glob("*.mp3"))
    if canzoni:
        canzone = canzoni[int(time.time()) % len(canzoni)]
        registro.annota("canzone", file=canzone.name)
        subprocess.run(["mpg123", "-q", "-o", "alsa", "-a", ALTOPARLANTE, str(canzone)])


def esegui_azioni() -> None:
    while strumenti.azioni_in_sospeso:
        if strumenti.azioni_in_sospeso.pop(0) == "canzone":
            suona_canzone()


def modo_testo() -> None:
    from nina import Nina
    nina = Nina()
    print("Scrivi come se fossi la nonna (Ctrl+D per uscire).")
    for riga in sys.stdin:
        if riga.strip():
            inizio = time.monotonic()
            print(f"📻 {nina.rispondi(riga.strip())}   ({time.monotonic() - inizio:.1f}s)")
            strumenti.azioni_in_sospeso.clear()


def modo_radio(eco: bool) -> None:
    from ascolto import ascolta_frase
    from voce import parla, trascrivi
    nina = None if eco else __import__("nina").Nina()
    print("Nina ascolta… (Ctrl+C per uscire)")
    while True:
        pcm = ascolta_frase()
        if pcm is None:
            continue
        inizio = time.monotonic()
        print(f"✂️  frase di {len(pcm) / 32000:.1f} s, trascrivo…")
        try:
            detto = trascrivi(pcm)
            if len(detto) < 2:
                continue
            print(f"🎙️  {detto}   (trascritto in {time.monotonic() - inizio:.1f}s)")
            risposta = detto if eco else nina.rispondi(detto)
            print(f"📻 {risposta}   ({time.monotonic() - inizio:.1f}s prima di parlare)")
            parla(risposta)
            esegui_azioni()
        except Exception as errore:  # di notte la radio non deve spegnersi per un errore di rete
            print(f"⚠️  {type(errore).__name__}: {errore}")
            registro.annota("errore", tipo=type(errore).__name__, dettaglio=str(errore)[:300])
            time.sleep(2)


def main() -> None:
    p = argparse.ArgumentParser(description="La Radio di Nina")
    p.add_argument("--eco", action="store_true", help="ripete quello che sente (prova microfono, trascrizione e voce)")
    p.add_argument("--testo", action="store_true", help="scrivi invece di parlare (prova di Claude senza audio)")
    args = p.parse_args()
    try:
        modo_testo() if args.testo else modo_radio(args.eco)
    except KeyboardInterrupt:
        print("\nCiao!")


if __name__ == "__main__":
    main()
