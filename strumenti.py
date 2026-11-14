"""Gli strumenti che Nina può usare mentre parla con la nonna."""
import json
from datetime import datetime, timedelta

import registro
import avvisi
import pillola
from config import DATI, NOME_NONNA

# Azioni da fare dopo che Nina ha finito di parlare (per ora: la canzone)
azioni_in_sospeso: list[str] = []

# Domande di controllo ai figli: mai di notte (dormono) e una sola per argomento ogni due ore,
# così se lei ripete la stessa cosa dieci volte i figli ricevono un messaggio solo.
CONFERME = DATI / "conferme_famiglia.json"
ARGOMENTI_CONFERMA = ("pasto", "visita", "appuntamento", "altro")
PAUSA_CONFERME = timedelta(hours=2)
NOTTE_DALLE, NOTTE_ALLE = 22, 7

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
        "name": "chiedi_conferma_famiglia",
        "description": (
            "Chiede ai figli su Telegram se è vero qualcosa che lei crede e tu non puoi sapere: deve preparare "
            "da mangiare per qualcuno, aspetta una visita, deve andare a un appuntamento. Non è urgente: per i "
            "rischi c'è avvisa_famiglia. Non usarlo per le persone care che non ci sono più. Di notte e se la "
            "stessa domanda è già partita da poco non manda niente, e te lo dice."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "argomento": {"type": "string", "enum": list(ARGOMENTI_CONFERMA),
                              "description": "pasto, visita, appuntamento oppure altro."},
                "domanda": {"type": "string",
                            "description": "Per i figli, in una frase: cosa dice lei e cosa vuoi sapere."},
            },
            "required": ["argomento", "domanda"],
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
        "name": "segna_pillola",
        "description": (
            "Dopo un promemoria della pillola, annota cosa ha risposto lei. È quello che ha DETTO: "
            "la radio non può vedere se l'ha presa davvero."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "esito": {"type": "string", "enum": list(pillola.ESITI),
                          "description": "ha_detto_di_averla_presa, rifiutata, oppure dice_di_averla_gia_presa."},
            },
            "required": ["esito"],
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


def chiedi_conferma_famiglia(argomento: str, domanda: str, adesso: datetime | None = None) -> str:
    adesso = adesso or datetime.now()
    if adesso.hour >= NOTTE_DALLE or adesso.hour < NOTTE_ALLE:
        return ("Domanda NON mandata: è notte e i figli dormono. Non dirle che l'hai chiesto: ricordale con "
                "dolcezza che è notte e che adesso si riposa.")
    try:
        fatte = json.loads(CONFERME.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        fatte = {}
    ultima = fatte.get(argomento)
    if ultima and adesso - datetime.fromisoformat(ultima) < PAUSA_CONFERME:
        return (f"Domanda già fatta ai figli alle {ultima[11:16]}: non rimandarla. Puoi dirle che l'hai già "
                "chiesto ai suoi figli e che le farai sapere.")
    partiti = avvisi.invia(f"❓ Nina, ore {adesso:%H:%M}: {domanda}\n"
                           f"Rispondete qui: Nina dirà a {NOME_NONNA} quello che scrivete.")
    if not partiti:
        return "Domanda NON partita (Telegram non raggiungibile). Non dirle che l'hai chiesto ai figli."
    fatte[argomento] = adesso.isoformat(timespec="seconds")
    DATI.mkdir(exist_ok=True)
    CONFERME.write_text(json.dumps(fatte), encoding="utf-8")
    return ("Domanda mandata ai figli: quando rispondono, la radio le porterà la risposta. Dille con parole "
            "semplici che lo chiedi ai suoi figli. Non dire che qualcuno viene o non viene.")


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


def segna_pillola(esito: str) -> str:
    return pillola.segna(esito)


_FUNZIONI = {
    "segna_pillola": segna_pillola,
    "avvisa_famiglia": avvisa_famiglia,
    "chiedi_conferma_famiglia": chiedi_conferma_famiglia,
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
