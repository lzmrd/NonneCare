"""Promemoria della pillola, con le regole decise dalla famiglia.

- Orari e strategie li scrive la famiglia dal bot; Nina sceglie tra quelle, non ne inventa.
- Si annota quello che lei DICE ("ha detto di averla presa"), non quello che la radio non può vedere.
- Se rifiuta, Nina riprova dopo 15 minuti con un'altra strategia; dopo 3 tentativi avvisa la famiglia.
- Mai "prendine un'altra": se dice di averla già presa non si discute (rischio doppia dose).
"""
import json
from datetime import datetime, timedelta

import avvisi
import registro
from config import DATI, NOME_NONNA

CONFIG = DATI / "pillola.json"            # {"orari": ["09:00", "20:00"], "strategie": ["..."]}
STATO = DATI / "pillola_oggi.json"        # {"data": "...", "20:00": {"tentativi": 1, "ultimo": "...", "esito": null}}
SUBITO = DATI / "pillola_subito"          # creato dal bot per la demo: promemoria adesso
TENTATIVI_MASSIMI = 3
PAUSA_TRA_TENTATIVI = timedelta(minutes=15)
FINESTRA = timedelta(hours=2)  # oltre, il promemoria non si fa più: una dose tardiva la decide la famiglia
ESITI = ("ha_detto_di_averla_presa", "rifiutata", "dice_di_averla_gia_presa")


def _leggi(percorso, predefinito):
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return predefinito


def _scrivi(percorso, dati) -> None:
    DATI.mkdir(exist_ok=True)
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")


def configurazione() -> dict:
    return _leggi(CONFIG, {"orari": [], "strategie": []})


def imposta_orari(orari: list[str]) -> list[str]:
    validi = sorted({datetime.strptime(o.strip(), "%H:%M").strftime("%H:%M") for o in orari})
    _scrivi(CONFIG, {**configurazione(), "orari": validi})
    return validi


def aggiungi_strategia(strategia: str) -> None:
    c = configurazione()
    _scrivi(CONFIG, {**c, "strategie": c["strategie"] + [strategia.strip()]})


def _stato_di_oggi(adesso: datetime) -> dict:
    stato = _leggi(STATO, {})
    return stato if stato.get("data") == adesso.date().isoformat() else {"data": adesso.date().isoformat()}


def da_fare(adesso: datetime | None = None) -> dict | None:
    """Se è il momento di un promemoria restituisce {orario, tentativo, strategie}, altrimenti None.

    Registra il tentativo: chi la chiama deve poi far parlare Nina.
    """
    adesso = adesso or datetime.now()
    stato = _stato_di_oggi(adesso)
    if SUBITO.exists():  # promemoria chiesto dalla famiglia adesso
        SUBITO.unlink()
        orario = adesso.strftime("%H:%M")
        stato[orario] = {"tentativi": 0, "ultimo": None, "esito": None}
    for orario in sorted(set(configurazione()["orari"]) | {k for k in stato if k != "data"}):
        voce = stato.setdefault(orario, {"tentativi": 0, "ultimo": None, "esito": None})
        ora_prevista = datetime.combine(adesso.date(), datetime.strptime(orario, "%H:%M").time())
        if voce["esito"] or adesso < ora_prevista:
            continue
        if voce["tentativi"] == 0 and adesso > ora_prevista + FINESTRA:
            voce["esito"] = "promemoria_saltato_famiglia_avvisata"
            partiti = avvisi.invia(f"💊 Nina non ha potuto ricordare a {NOME_NONNA} la pillola delle {orario} "
                                   "(radio spenta o in pausa). Non gliela ricorda in ritardo: decidete voi.")
            registro.annota("pillola", orario=orario, esito=voce["esito"], familiari_avvisati=partiti)
            _scrivi(STATO, stato)
            continue
        if voce["tentativi"] >= TENTATIVI_MASSIMI:
            voce["esito"] = "non_presa_famiglia_avvisata"
            partiti = avvisi.invia(f"💊 {NOME_NONNA} non ha preso la pillola delle {orario} dopo "
                                   f"{TENTATIVI_MASSIMI} tentativi di Nina. Potete passare o chiamarla?")
            registro.annota("pillola", orario=orario, esito=voce["esito"], familiari_avvisati=partiti)
            _scrivi(STATO, stato)
            continue
        if voce["ultimo"] and adesso - datetime.fromisoformat(voce["ultimo"]) < PAUSA_TRA_TENTATIVI:
            continue
        voce["tentativi"] += 1
        voce["ultimo"] = adesso.isoformat(timespec="seconds")
        _scrivi(STATO, stato)
        registro.annota("pillola", orario=orario, tentativo=voce["tentativi"], esito="promemoria")
        return {"orario": orario, "tentativo": voce["tentativi"], "strategie": configurazione()["strategie"]}
    _scrivi(STATO, stato)
    return None


def segna(esito: str, adesso: datetime | None = None) -> str:
    """Annota la risposta di lei all'ultimo promemoria della giornata."""
    if esito not in ESITI:
        raise ValueError(f"esito deve essere uno di {ESITI}")
    adesso = adesso or datetime.now()
    stato = _stato_di_oggi(adesso)
    aperti = [o for o in sorted(k for k in stato if k != "data") if stato[o]["tentativi"] and not stato[o]["esito"]]
    if not aperti:
        return "Nessun promemoria della pillola in corso."
    orario = aperti[-1]
    if esito != "rifiutata":
        stato[orario]["esito"] = esito
    _scrivi(STATO, stato)
    registro.annota("pillola", orario=orario, tentativo=stato[orario]["tentativi"], esito=esito)
    if esito == "rifiutata":
        rimasti = TENTATIVI_MASSIMI - stato[orario]["tentativi"]
        return (f"Annotato. Non insistere adesso: cambia argomento. Riproverai tra 15 minuti ({rimasti} tentativi rimasti)."
                if rimasti else "Annotato. Non insistere: la famiglia verrà avvisata.")
    if esito == "dice_di_averla_gia_presa":
        return "Annotato. Non discutere e non dirle di prenderne un'altra: controllerà la famiglia."
    return "Annotato come detto da lei."


def direttiva(promemoria: dict) -> str:
    """Il testo che dice a Nina di ricordare la pillola (non sono parole della nonna)."""
    strategie = promemoria["strategie"]  # ruota a ogni tentativo, così Nina non ripete la stessa cosa
    strategia = (strategie[(promemoria["tentativo"] - 1) % len(strategie)] if strategie
                 else "ricordaglielo semplicemente, con dolcezza")
    return (f"È l'ora della pillola delle {promemoria['orario']} (tentativo {promemoria['tentativo']} "
            f"di {TENTATIVI_MASSIMI}). Ricordaglielo tu per prima, con dolcezza. Strategia scritta dalla "
            f"famiglia per questo tentativo: {strategia}. "
            "Quando lei risponde, usa segna_pillola con quello che ha detto.")
