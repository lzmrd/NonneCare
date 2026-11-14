"""Gli strumenti che Nina può usare mentre parla con la nonna."""
import json
from datetime import datetime

import registro
import avvisi
from config import DATI, NOME_NONNA

# Azioni da fare dopo che Nina ha finito di parlare (per ora: la canzone)
azioni_in_sospeso: list[str] = []

DEFINIZIONI = [
    {
        "name": "avvisa_famiglia",
        "description": (
            "Avvisa subito i figli su Telegram. Usalo solo per un rischio reale: vuole uscire di casa, "
            "è caduta, sta male, ha molta paura e non si calma. Restituisce se l'avviso è partito."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "motivo": {"type": "string", "description": "Cosa sta succedendo, in una frase, per i figli."},
            },
            "required": ["motivo"],
            "additionalProperties": False,
        },
    },
    {
        "name": "messaggio_per_la_famiglia",
        "description": (
            "Lascia un messaggio della nonna per i figli, che lo leggeranno al risveglio nel resoconto del mattino. "
            "Usalo quando di notte vuole dire qualcosa al figlio o vuole chiamarlo e accetta di lasciare un messaggio."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "messaggio": {"type": "string", "description": "Il messaggio, con le parole di lei il più possibile."},
            },
            "required": ["messaggio"],
            "additionalProperties": False,
        },
    },
    {
        "name": "metti_canzone",
        "description": "Fa partire la sua canzone preferita appena hai finito di parlare. Usalo solo se lei è d'accordo.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def avvisa_famiglia(motivo: str) -> str:
    ora = datetime.now().strftime("%H:%M")
    partiti = avvisi.invia(f"⚠️ Nina, ore {ora}: {motivo}\nPassate da {NOME_NONNA} o chiamatela.")
    if partiti:
        return f"Avviso partito: lo hanno ricevuto {partiti} familiari."
    return "Avviso NON partito (Telegram non raggiungibile o nessun familiare configurato). Non dirle che hai avvisato."


def messaggio_per_la_famiglia(messaggio: str) -> str:
    DATI.mkdir(exist_ok=True)
    with (DATI / "messaggi_per_il_mattino.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ora": datetime.now().isoformat(timespec="seconds"), "messaggio": messaggio},
                           ensure_ascii=False) + "\n")
    return "Messaggio salvato: i figli lo leggeranno al risveglio."


def metti_canzone() -> str:
    canzoni = sorted((DATI / "musica").glob("*.mp3")) if (DATI / "musica").exists() else []
    if not canzoni:
        return "Nessuna canzone disponibile sulla radio. Non dirle che sta partendo."
    azioni_in_sospeso.append("canzone")
    return "La canzone partirà appena hai finito di parlare."


_FUNZIONI = {
    "avvisa_famiglia": avvisa_famiglia,
    "messaggio_per_la_famiglia": messaggio_per_la_famiglia,
    "metti_canzone": metti_canzone,
}


def esegui(nome: str, argomenti: dict) -> tuple[str, bool]:
    """Esegue lo strumento e annota tutto nel registro. Restituisce (risultato, errore)."""
    try:
        risultato, errore = _FUNZIONI[nome](**argomenti), False
    except Exception as e:
        risultato, errore = f"Errore: {e}", True
    registro.annota("strumento", nome=nome, argomenti=argomenti, risultato=risultato)
    return risultato, errore
