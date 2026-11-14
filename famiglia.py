"""Bot Telegram della famiglia (@nonneCareBot): un agente Claude con gli strumenti per la radio.

    python famiglia.py

Comandi: /resoconto (com'è andata la notte), /verifica (integrità del registro).
Ogni mattina alle 7 manda il resoconto della notte a tutta la famiglia.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta

import anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import avvisi
import bacheca
import registro
from config import CARTELLA, DATI, MODELLO, NOME_NONNA, TELEGRAM_TOKEN

ORA_RESOCONTO = 7
PAUSA_NUOVA_CONVERSAZIONE_S = 30 * 60
MESSAGGI_MATTINO = DATI / "messaggi_per_il_mattino.jsonl"
RICHIESTA_RESOCONTO = ("[resoconto automatico] Scrivi il resoconto per la famiglia delle ultime 12 ore della radio: "
                       "risvegli con orari, cosa chiedeva, come si è calmata, avvisi e chi li ha gestiti, "
                       "messaggi che ha lasciato per i figli. Massimo 12 righe.")

DEFINIZIONI = [
    {
        "name": "di_alla_nonna",
        "description": "La radio legge alla nonna un messaggio della famiglia appena lei non sta parlando.",
        "input_schema": {
            "type": "object",
            "properties": {
                "messaggio": {"type": "string", "description": "Il messaggio in parole semplici, in terza persona."},
                "da_parte_di": {"type": "string", "description": "Il nome di chi manda il messaggio."},
            },
            "required": ["messaggio", "da_parte_di"],
            "additionalProperties": False,
        },
    },
    {
        "name": "aggiungi_ricordo",
        "description": "Salva un ricordo della nonna che Nina userà dalla prossima conversazione.",
        "input_schema": {
            "type": "object",
            "properties": {"ricordo": {"type": "string", "description": "Il ricordo in una o due frasi."}},
            "required": ["ricordo"],
            "additionalProperties": False,
        },
    },
    {
        "name": "leggi_registro",
        "description": "Legge gli eventi della radio delle ultime ore e i messaggi lasciati per il mattino.",
        "input_schema": {
            "type": "object",
            "properties": {"ore": {"type": "integer", "description": "Quante ore indietro, da 1 a 48."}},
            "required": ["ore"],
            "additionalProperties": False,
        },
    },
    {
        "name": "verifica_registro",
        "description": "Controlla che nessuno abbia modificato o cancellato righe del registro.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "segna_avviso_gestito",
        "description": "Annota che un familiare si sta occupando di un avviso e lo comunica agli altri familiari.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chi": {"type": "string", "description": "Chi se ne occupa."},
                "nota": {"type": "string", "description": "Cosa farà, in breve."},
            },
            "required": ["chi", "nota"],
            "additionalProperties": False,
        },
    },
    {
        "name": "pausa_ascolto",
        "description": "Mette in pausa l'ascolto della radio per alcuni minuti (0 la riattiva).",
        "input_schema": {
            "type": "object",
            "properties": {"minuti": {"type": "integer", "description": "Durata della pausa, da 0 a 240."}},
            "required": ["minuti"],
            "additionalProperties": False,
        },
    },
]


# --- Strumenti -------------------------------------------------------------------------------

def di_alla_nonna(messaggio: str, da_parte_di: str) -> str:
    bacheca.aggiungi_annuncio(messaggio, da_parte_di)
    registro.annota("messaggio_famiglia", da=da_parte_di, testo=messaggio)
    return "Messaggio in coda: la radio lo leggerà appena lei non sta parlando."


def aggiungi_ricordo(ricordo: str) -> str:
    DATI.mkdir(exist_ok=True)
    with (DATI / "ricordi.md").open("a", encoding="utf-8") as f:
        f.write(f"- {ricordo.strip()}\n")
    registro.annota("ricordo_aggiunto", testo=ricordo.strip())
    return "Ricordo salvato: Nina lo userà dalla prossima conversazione."


def leggi_registro(ore: int) -> str:
    ore = max(1, min(48, ore))
    da = datetime.now() - timedelta(hours=ore)
    righe = []
    if registro.FILE.exists():
        for riga in registro.FILE.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            voce = json.loads(riga)
            if datetime.fromisoformat(voce["ora"]) < da:
                continue
            dati = {k: v for k, v in voce.items() if k not in ("ora", "tipo", "hash", "precedente", "modello")}
            righe.append(f"{voce['ora'][11:16]} {voce['tipo']}: {json.dumps(dati, ensure_ascii=False)}")
    if MESSAGGI_MATTINO.exists():
        for riga in MESSAGGI_MATTINO.read_text(encoding="utf-8").splitlines():
            if riga.strip():
                m = json.loads(riga)
                righe.append(f"{m['ora'][11:16]} messaggio per i figli: {m['messaggio']}")
    if not righe:
        return f"Nessun evento nelle ultime {ore} ore."
    return "\n".join(righe[-300:])


def verifica_registro() -> str:
    return registro.verifica()[1]


def segna_avviso_gestito(chi: str, nota: str) -> str:
    registro.annota("avviso_gestito", chi=chi, nota=nota)
    partiti = avvisi.invia(f"✅ {chi} si occupa dell'avviso: {nota}")
    return f"Annotato nel registro e comunicato a {partiti} familiari."


def pausa_ascolto(minuti: int) -> str:
    minuti = max(0, min(240, minuti))
    bacheca.metti_in_pausa(minuti)
    if minuti == 0:
        return "Ascolto riattivato."
    return f"Ascolto in pausa fino alle {(datetime.now() + timedelta(minutes=minuti)):%H:%M}."


_FUNZIONI = {f.__name__: f for f in (di_alla_nonna, aggiungi_ricordo, leggi_registro, verifica_registro,
                                     segna_avviso_gestito, pausa_ascolto)}


# --- Agente ----------------------------------------------------------------------------------

_client = anthropic.AsyncAnthropic(timeout=60.0)
_storie: dict[str, tuple[list, float]] = {}


def _sistema() -> str:
    return (CARTELLA / "prompt_famiglia.md").read_text(encoding="utf-8").replace("{nome}", NOME_NONNA)


async def chiedi_all_agente(messaggi: list) -> str:
    risposta = None
    for _ in range(6):
        risposta = await _client.messages.create(
            model=MODELLO,
            max_tokens=4000,
            system=_sistema(),
            messages=messaggi,
            tools=DEFINIZIONI,
            output_config={"effort": "low"},
            cache_control={"type": "ephemeral"},
        )
        if risposta.stop_reason == "refusal":
            return "Non posso aiutarti con questa richiesta."
        messaggi.append({"role": "assistant", "content": risposta.content})
        if risposta.stop_reason != "tool_use":
            break
        risultati = []
        for blocco in risposta.content:
            if blocco.type == "tool_use":
                try:
                    testo, errore = _FUNZIONI[blocco.name](**blocco.input), False
                except Exception as e:
                    testo, errore = f"Errore: {e}", True
                risultati.append({"type": "tool_result", "tool_use_id": blocco.id, "content": testo, "is_error": errore})
        messaggi.append({"role": "user", "content": risultati})
    testo = "\n".join(b.text for b in risposta.content if b.type == "text").strip() if risposta else ""
    return testo or "Fatto."


def _storia(chat: str) -> list:
    storia, ultimo = _storie.get(chat, ([], 0.0))
    if time.monotonic() - ultimo > PAUSA_NUOVA_CONVERSAZIONE_S:
        storia = []
    _storie[chat] = (storia, time.monotonic())
    return storia


# --- Telegram --------------------------------------------------------------------------------

async def _solo_famiglia(update: Update) -> bool:
    chat = str(update.effective_chat.id)
    if chat in avvisi.chat_famiglia():
        return True
    await update.message.reply_text(
        f"Questo bot è riservato alla famiglia. Il tuo ID è {chat}: va aggiunto a FAMIGLIA_CHAT_ID sulla radio.")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _solo_famiglia(update):
        await update.message.reply_text(
            f"Ciao! Sono il collegamento con la radio di {NOME_NONNA}. Scrivimi un messaggio da farle sentire, "
            "un ricordo da insegnare a Nina, o chiedimi com'è andata la notte.\n"
            "/resoconto: com'è andata la notte\n/verifica: controlla che il registro sia integro")


async def messaggio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _solo_famiglia(update):
        return
    chat = str(update.effective_chat.id)
    nome = update.effective_user.first_name if update.effective_user else "un familiare"
    storia = _storia(chat)
    storia.append({"role": "user", "content": f"[{datetime.now():%H:%M}, scrive {nome}] {update.message.text}"})
    await update.effective_chat.send_action("typing")
    try:
        testo = await chiedi_all_agente(storia)
    except Exception as errore:
        _storie.pop(chat, None)
        testo = f"Non sono riuscito a rispondere ({type(errore).__name__}). Riprova tra poco."
    await update.message.reply_text(testo)


async def resoconto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _solo_famiglia(update):
        await update.effective_chat.send_action("typing")
        await update.message.reply_text(await chiedi_all_agente([{"role": "user", "content": RICHIESTA_RESOCONTO}]))


async def verifica(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await _solo_famiglia(update):
        integro, spiegazione = registro.verifica()
        await update.message.reply_text(("✅ " if integro else "❌ ") + spiegazione)


async def _resoconto_del_mattino(app: Application) -> None:
    while True:
        adesso = datetime.now()
        prossimo = adesso.replace(hour=ORA_RESOCONTO, minute=0, second=0, microsecond=0)
        if prossimo <= adesso:
            prossimo += timedelta(days=1)
        await asyncio.sleep((prossimo - adesso).total_seconds())
        try:
            testo = await chiedi_all_agente([{"role": "user", "content": RICHIESTA_RESOCONTO}])
            for chat in avvisi.chat_famiglia():
                await app.bot.send_message(chat, f"☀️ Buongiorno. La notte di {NOME_NONNA}:\n\n{testo}")
            if MESSAGGI_MATTINO.exists():  # consegnati: li archivio
                MESSAGGI_MATTINO.rename(DATI / f"messaggi_consegnati_{adesso:%Y%m%d}.jsonl")
            registro.annota("resoconto", testo=testo)
        except Exception as errore:
            print(f"Resoconto del mattino non riuscito: {errore}")


async def _all_avvio(app: Application) -> None:
    app.create_task(_resoconto_del_mattino(app))


def main() -> None:
    if not TELEGRAM_TOKEN:
        raise SystemExit("Manca TELEGRAM_TOKEN nel file .env")
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(_all_avvio).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("resoconto", resoconto))
    app.add_handler(CommandHandler("verifica", verifica))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, messaggio))
    print("Bot della famiglia attivo (Ctrl+C per uscire)")
    app.run_polling()


if __name__ == "__main__":
    main()
