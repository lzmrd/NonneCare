"""La Radio di Nina: ascolta, capisce, risponde.

    python main.py            la radio vera: microfono, Claude, voce
    python main.py --eco      prova dell'audio: ripete quello che sente, senza Claude
    python main.py --testo    prova del cervello: scrivi e leggi, senza audio
"""
import argparse
import os
import subprocess
import sys
import time

import bacheca
import pillola
import registro
import strumenti
from config import DATI, NOME_NONNA


def suona_canzone() -> None:
    from voce import suona
    canzoni = sorted((DATI / "musica").glob("*.mp3"))
    if canzoni:
        canzone = canzoni[int(time.time()) % len(canzoni)]
        registro.annota("canzone", file=canzone.name)
        # mpg123 decodifica in mono a 44100 Hz, poi suona come la voce (stesse opzioni e conversione)
        decodifica = subprocess.Popen(["mpg123", "-q", "-s", "-m", "-r", "44100", "-e", "s16", str(canzone)],
                                      stdout=subprocess.PIPE)
        try:
            suona(iter(lambda: decodifica.stdout.read(8192), b""), 44100)
        finally:
            decodifica.stdout.close()  # se aplay si chiude, mpg123 si ferma invece di restare appeso
            decodifica.wait()


def esegui_azioni() -> None:
    while strumenti.azioni_in_sospeso:
        if strumenti.azioni_in_sospeso.pop(0) == "canzone":
            suona_canzone()


def leggi_annunci(nina, parla) -> None:
    for annuncio in bacheca.prendi_annunci():
        testo = f"{NOME_NONNA}, sono Nina. Ti porto un messaggio di {annuncio['da']}: {annuncio['testo']}"
        print(f"📨 {testo}")
        try:
            parla(testo)
            registro.annota("annuncio", da=annuncio["da"], testo=annuncio["testo"])
            nina.ricorda_annuncio(annuncio["testo"])
        except Exception as errore:
            print(f"⚠️  annuncio non letto: {errore}")
            bacheca.aggiungi_annuncio(annuncio["testo"], annuncio["da"])  # riprovo al giro dopo
            time.sleep(5)


def modo_testo() -> None:
    from nina import Nina
    nina = Nina()
    print("Scrivi come se fossi la nonna (/pillola per il promemoria, Ctrl+D per uscire).")
    for riga in sys.stdin:
        if riga.strip() == "/pillola":
            pillola.SUBITO.parent.mkdir(exist_ok=True)
            pillola.SUBITO.touch()
            print(f"💊 {nina.parla_per_prima(pillola.direttiva(pillola.da_fare()))}")
        elif riga.strip():
            inizio = time.monotonic()
            print(f"📻 {nina.rispondi(riga.strip())}   ({time.monotonic() - inizio:.1f}s)")
            strumenti.azioni_in_sospeso.clear()


def modo_radio(eco: bool) -> None:
    from ascolto import ascolta_frase
    from voce import parla, parla_di_riserva, prepara_riserva, trascrivi
    nina = None if eco else __import__("nina").Nina()
    ultima_canzone_di_riserva = 0.0
    try:
        prepara_riserva()
    except Exception as errore:
        print(f"⚠️  frase di riserva non preparata: {errore}")
    print("Nina ascolta… (Ctrl+C per uscire)")
    if os.environ.get("NINA_ANNUNCIA_AVVIO") == "1":  # utile senza schermo: si sente quando è pronta
        try:
            parla("Sono Nina, sono accesa.")
        except Exception as errore:
            print(f"⚠️  saluto di avvio non riuscito: {errore}")
    while True:
        if bacheca.in_pausa():
            time.sleep(5)
            continue
        if not eco:
            leggi_annunci(nina, parla)
            promemoria = pillola.da_fare()
            if promemoria:
                try:
                    testo = nina.parla_per_prima(pillola.direttiva(promemoria))
                    print(f"💊 {testo}")
                    parla(testo)
                    esegui_azioni()
                except Exception as errore:
                    print(f"⚠️  promemoria non letto: {errore}")
        pcm = ascolta_frase(timeout=5)  # ogni 5 secondi di silenzio controlla gli annunci
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
            # senza rete: frase preparata in anticipo e, al massimo ogni 10 minuti, la sua canzone
            try:
                if parla_di_riserva() and time.monotonic() - ultima_canzone_di_riserva > 600:
                    ultima_canzone_di_riserva = time.monotonic()
                    suona_canzone()
            except Exception as altro:
                print(f"⚠️  anche la riserva non è riuscita: {altro}")
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
