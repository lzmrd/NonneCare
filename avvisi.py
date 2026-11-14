"""Messaggi alla famiglia su Telegram, chiamando direttamente le API del bot.

Gli ID delle chat della famiglia vanno nel .env, separati da virgola:
    FAMIGLIA_CHAT_ID=123456789,987654321

Per scoprire il tuo: scrivi un messaggio qualsiasi al bot, poi lancia
    python avvisi.py
"""
import json
import os
import urllib.parse
import urllib.request

from config import TELEGRAM_TOKEN

API = "https://api.telegram.org/bot{token}/{metodo}"


def _chiama(metodo: str, **parametri) -> dict:
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Manca TELEGRAM_TOKEN nel file .env")
    dati = urllib.parse.urlencode(parametri).encode()
    with urllib.request.urlopen(API.format(token=TELEGRAM_TOKEN, metodo=metodo), data=dati, timeout=15) as r:
        return json.load(r)


def chat_famiglia() -> list[str]:
    return [c.strip() for c in os.environ.get("FAMIGLIA_CHAT_ID", "").split(",") if c.strip()]


def invia(testo: str) -> int:
    """Manda il testo a tutta la famiglia. Restituisce quanti messaggi sono partiti."""
    partiti = 0
    for chat in chat_famiglia():
        try:
            if _chiama("sendMessage", chat_id=chat, text=testo).get("ok"):
                partiti += 1
        except Exception as errore:  # un telefono irraggiungibile non deve fermare gli altri
            print(f"Telegram: invio a {chat} fallito: {errore}")
    return partiti


if __name__ == "__main__":
    aggiornamenti = _chiama("getUpdates").get("result", [])
    viste = {}
    for a in aggiornamenti:
        chat = (a.get("message") or {}).get("chat")
        if chat:
            viste[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not viste:
        print("Nessun messaggio: scrivi qualcosa al bot su Telegram e riprova.")
    for chat_id, nome in viste.items():
        print(f"{chat_id}  {nome}")
