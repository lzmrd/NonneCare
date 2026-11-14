"""Sigillo della scatola nera su Avalanche (rete di prova Fuji).

Ogni riga del registro contiene l'hash della precedente, quindi l'hash dell'ultima riga
impegna TUTTO il registro fino a lì. Ogni mattina quell'hash va in una transazione:
da quel momento nessuno, nemmeno chi ha programmato la radio, può riscrivere il passato
senza che la verifica se ne accorga. Sulla blockchain va solo l'hash: i dati della
nonna restano sul Raspberry.

    python sigillo.py portafoglio   crea il portafoglio della radio (una volta) e mostra l'indirizzo
    python sigillo.py saldo         AVAX di prova disponibili
    python sigillo.py sigilla       sigilla adesso
    python sigillo.py verifica      controlla il registro e l'ultimo sigillo
"""
import json
import os
import sys
from datetime import datetime

import registro
from config import CARTELLA, DATI, ESPLORATORE_TX, RPC_AVALANCHE

SIGILLI = DATI / "sigilli.jsonl"
PREFISSO = "NonneCare"


def _web3():
    from web3 import Web3  # import lento sul Pi: solo quando serve
    return Web3(Web3.HTTPProvider(RPC_AVALANCHE, request_kwargs={"timeout": 20}))


def _account():
    from eth_account import Account
    chiave = os.environ.get("SIGILLO_CHIAVE", "").strip()
    if not chiave:
        raise RuntimeError("Manca SIGILLO_CHIAVE nel .env: lancia prima 'python sigillo.py portafoglio'")
    return Account.from_key(chiave)


def crea_portafoglio() -> str:
    from eth_account import Account
    if os.environ.get("SIGILLO_CHIAVE", "").strip():
        return f"Il portafoglio esiste già: {_account().address}"
    nuovo = Account.create()
    with open(CARTELLA / ".env", "a", encoding="utf-8") as f:  # la chiave non viene mai stampata
        f.write(f"\nSIGILLO_CHIAVE={nuovo.key.hex()}\n")
    os.chmod(CARTELLA / ".env", 0o600)
    return (f"Portafoglio creato: {nuovo.address}\n"
            "Mandaci un po' di AVAX di prova (rete Fuji, C-Chain) dal faucet, poi: python sigillo.py saldo")


def saldo() -> str:
    w3 = _web3()
    wei = w3.eth.get_balance(_account().address)
    return f"{_account().address}: {wei / 10**18:.4f} AVAX di prova"


def _registro_attuale() -> tuple[int, str]:
    """Numero di righe e hash dell'ultima riga."""
    if not registro.FILE.exists():
        return 0, ""
    righe = [r for r in registro.FILE.read_text(encoding="utf-8").splitlines() if r.strip()]
    return len(righe), (json.loads(righe[-1])["hash"] if righe else "")


def _ultimo_sigillo() -> dict | None:
    if not SIGILLI.exists():
        return None
    righe = [r for r in SIGILLI.read_text(encoding="utf-8").splitlines() if r.strip()]
    return json.loads(righe[-1]) if righe else None


def link(tx: str) -> str:
    return f"{ESPLORATORE_TX}{tx}"


def sigilla() -> dict:
    """Mette l'hash attuale del registro in una transazione. Restituisce il sigillo salvato."""
    integro, spiegazione = registro.verifica()
    if not integro:
        raise RuntimeError(f"Non sigillo un registro manomesso: {spiegazione}")
    righe, ultimo_hash = _registro_attuale()
    if not righe:
        raise RuntimeError("Il registro è vuoto: niente da sigillare.")
    precedente = _ultimo_sigillo()
    if precedente and precedente["righe"] == righe:
        return precedente

    w3, account = _web3(), _account()
    dati = f"{PREFISSO}|{righe}|{ultimo_hash}".encode()
    transazione = {
        "to": account.address, "value": 0, "data": dati,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": max(w3.eth.gas_price * 2, 1), "chainId": w3.eth.chain_id,
    }
    transazione["gas"] = int(w3.eth.estimate_gas({**transazione, "from": account.address}) * 1.2)
    firmata = account.sign_transaction(transazione)
    tx = w3.eth.send_raw_transaction(firmata.raw_transaction)
    ricevuta = w3.eth.wait_for_transaction_receipt(tx, timeout=90)
    if ricevuta["status"] != 1:
        raise RuntimeError("La transazione è fallita.")

    sigillo = {"ora": datetime.now().isoformat(timespec="seconds"), "righe": righe, "hash": ultimo_hash,
               "tx": "0x" + bytes(tx).hex(), "blocco": ricevuta["blockNumber"]}
    DATI.mkdir(exist_ok=True)
    with SIGILLI.open("a", encoding="utf-8") as f:
        f.write(json.dumps(sigillo) + "\n")
    registro.annota("sigillo", righe=righe, hash_sigillato=ultimo_hash, tx=sigillo["tx"])
    return sigillo


def verifica_completa() -> tuple[bool, str]:
    """Catena degli hash + confronto con l'ultimo sigillo letto dalla blockchain."""
    integro, spiegazione = registro.verifica()
    if not integro:
        return False, spiegazione
    sigillo = _ultimo_sigillo()
    if not sigillo:
        return True, spiegazione + " Nessun sigillo ancora sulla blockchain."
    righe = [r for r in registro.FILE.read_text(encoding="utf-8").splitlines() if r.strip()]
    if len(righe) < sigillo["righe"] or json.loads(righe[sigillo["righe"] - 1])["hash"] != sigillo["hash"]:
        return False, "Il registro non corrisponde più al sigillo: è stato riscritto dopo la sigillatura."
    try:
        sulla_catena = bytes(_web3().eth.get_transaction(sigillo["tx"])["input"]).decode(errors="replace")
    except Exception as errore:
        return True, (f"{spiegazione} Ultimo sigillo ({sigillo['ora'][:16]}, {sigillo['righe']} righe) "
                      f"non controllabile ora sulla blockchain: {type(errore).__name__}. {link(sigillo['tx'])}")
    if sulla_catena != f"{PREFISSO}|{sigillo['righe']}|{sigillo['hash']}":
        return False, f"Il sigillo salvato non corrisponde alla transazione sulla blockchain. {link(sigillo['tx'])}"
    return True, (f"Registro integro e uguale al sigillo del {sigillo['ora'][8:10]}/{sigillo['ora'][5:7]} "
                  f"alle {sigillo['ora'][11:16]} ({sigillo['righe']} righe), confermato sulla blockchain: "
                  f"{link(sigillo['tx'])}")


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else ""
    if comando == "portafoglio":
        print(crea_portafoglio())
    elif comando == "saldo":
        print(saldo())
    elif comando == "sigilla":
        s = sigilla()
        print(f"Sigillate {s['righe']} righe: {link(s['tx'])}")
    elif comando == "verifica":
        integro, testo = verifica_completa()
        print(("✅ " if integro else "❌ ") + testo)
    else:
        print(__doc__)
