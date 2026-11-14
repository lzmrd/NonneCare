"""Il cervello di Nina: Claude, con le regole di prompt_nina.md e i ricordi scritti dalla famiglia."""
import time
from datetime import datetime

import anthropic

import registro
import strumenti
from config import CARTELLA, DATI, MODELLO, NOME_NONNA

PAUSA_NUOVA_CONVERSAZIONE_S = 15 * 60  # dopo 15 minuti di silenzio si ricomincia (e Nina si ripresenta)
GIRI_MASSIMI = 4                        # risposte con strumenti in fila, al massimo
RISPOSTA_DI_RISERVA = "Sono Nina, sono qui con te, {nome}."


def _ricordi() -> str:
    for percorso in (DATI / "ricordi.md", CARTELLA / "ricordi.esempio.md"):
        if percorso.exists():
            return percorso.read_text(encoding="utf-8").strip()
    return "(nessun ricordo ancora)"


def _prompt() -> str:
    modello = (CARTELLA / "prompt_nina.md").read_text(encoding="utf-8")
    return modello.replace("{nome}", NOME_NONNA).replace("{ricordi}", _ricordi())


def _momento() -> str:
    adesso = datetime.now()
    parte = ("notte" if adesso.hour < 6 else "mattina" if adesso.hour < 12
             else "pomeriggio" if adesso.hour < 18 else "sera" if adesso.hour < 23 else "notte")
    return f"{adesso:%H:%M}, {parte}"


class Nina:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(timeout=30.0)
        self.messaggi: list = []
        self.sistema = _prompt()
        self.ultimo_scambio = 0.0
        self.annunci_recenti: list[tuple[float, str]] = []  # messaggi della famiglia appena letti alla nonna

    def ricorda_annuncio(self, testo: str) -> None:
        self.annunci_recenti.append((time.monotonic(), testo))

    def _nuova_conversazione(self) -> None:
        # Si riparte da zero invece di accorciare la storia: niente modifiche ai turni già inviati
        self.messaggi = []
        self.sistema = _prompt()  # rilegge i ricordi, se la famiglia ne ha aggiunti

    def rispondi(self, detto: str) -> str:
        """Risponde a quello che ha detto la nonna."""
        registro.annota("nonna", testo=detto)
        contesto = "".join(f"(Poco fa la radio le ha letto questo messaggio della famiglia: \"{t}\") "
                           for quando, t in self.annunci_recenti if time.monotonic() - quando < 30 * 60)
        self.annunci_recenti.clear()
        return self._turno(f"[{_momento()}] {contesto}{detto}")

    def parla_per_prima(self, indicazione: str) -> str:
        """Nina inizia a parlare (per esempio per la pillola): l'indicazione non sono parole della nonna."""
        registro.annota("indicazione", testo=indicazione)
        return self._turno(f"[{_momento()}] (Indicazione per Nina, lei non ha parlato: {indicazione})")

    def _turno(self, contenuto: str) -> str:
        if time.monotonic() - self.ultimo_scambio > PAUSA_NUOVA_CONVERSAZIONE_S:
            self._nuova_conversazione()
        self.ultimo_scambio = time.monotonic()
        self.messaggi.append({"role": "user", "content": contenuto})

        risposta = None
        for _ in range(GIRI_MASSIMI):
            risposta = self.client.messages.create(
                model=MODELLO,
                max_tokens=2000,
                system=self.sistema,
                messages=self.messaggi,
                tools=strumenti.DEFINIZIONI,
                output_config={"effort": "low"},
                cache_control={"type": "ephemeral"},
            )
            if risposta.stop_reason == "refusal":
                break
            self.messaggi.append({"role": "assistant", "content": risposta.content})
            if risposta.stop_reason != "tool_use":
                break
            risultati = []
            for blocco in risposta.content:
                if blocco.type == "tool_use":
                    testo, errore = strumenti.esegui(blocco.name, blocco.input)
                    risultati.append({"type": "tool_result", "tool_use_id": blocco.id,
                                      "content": testo, "is_error": errore})
            self.messaggi.append({"role": "user", "content": risultati})

        testo = " ".join(b.text for b in risposta.content if b.type == "text").strip() if risposta else ""
        if not testo or risposta.stop_reason in ("refusal", "tool_use"):
            # niente testo utilizzabile: frase sicura e conversazione da capo
            testo = RISPOSTA_DI_RISERVA.format(nome=NOME_NONNA)
            self._nuova_conversazione()
        registro.annota("nina", testo=testo, modello=MODELLO)
        return testo
