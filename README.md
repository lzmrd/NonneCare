# NonneCare: La Radio di Nina

Una radio sul comodino per chi vive con l'Alzheimer. Si accorge da sola quando la persona parla, le fa compagnia di notte con ricordi e canzoni, e avvisa subito la famiglia su Telegram se c'è un rischio.

Progetto in costruzione all'Agentic Hack Rome, 13-14 novembre 2026.

## Come funziona

1. **Ascolto** (`ascolto.py`): il rilevamento della voce gira sul Raspberry; in cloud va solo la frase già ritagliata.
2. **Trascrizione e voce** (`voce.py`): ElevenLabs.
3. **Cervello** (`nina.py`, `prompt_nina.md`): Claude, con regole precise: accoglie e reindirizza, non mente, non dice mai che una persona cara è morta, non finge di essere qualcun altro.
4. **Strumenti** (`strumenti.py`): avvisare la famiglia, lasciare un messaggio per il mattino, mettere la sua canzone.
5. **Registro** (`registro.py`): ogni evento è legato al precedente con un hash.
6. **Scatola nera** (`sigillo.py`): ogni mattina l'hash dell'ultima riga, che impegna tutto il registro, va in una transazione su Avalanche (rete di prova Fuji). Sulla blockchain va solo l'hash: i dati restano sul Raspberry. Nina può sbagliare; con il sigillo nessuno, nemmeno chi l'ha programmata, può riscrivere dopo quello che ha detto e fatto.
7. **Bot della famiglia** (`famiglia.py`): un agente Claude su Telegram. La famiglia manda messaggi che la radio legge alla nonna, insegna ricordi, chiede com'è andata la notte, segna chi si occupa di un avviso, verifica il sigillo (`/verifica`).

## Sul Raspberry

```bash
sudo apt install -y git mpg123
python -m venv ~/nina-env && ~/nina-env/bin/pip install anthropic elevenlabs webrtcvad python-telegram-bot web3 "setuptools<80"
cd ~/nina && ~/nina-env/bin/python main.py --eco     # prova dell'audio
~/nina-env/bin/python main.py --testo                # prova del cervello, scrivendo
~/nina-env/bin/python main.py                        # la radio
~/nina-env/bin/python -u famiglia.py                 # il bot della famiglia
~/nina-env/bin/python sigillo.py portafoglio         # una volta: crea il portafoglio della radio
```

Il file `.env` (mai nel repository):

```
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
TELEGRAM_TOKEN=...
NINA_VOCE_ID=...            # ID della voce scelta su ElevenLabs
FAMIGLIA_CHAT_ID=...        # chat dei familiari, separate da virgola (python avvisi.py per trovarle)
NINA_NOME_NONNA=...
# solo con una cassa Bluetooth (dispositivo "cassa" definito in ~/.asoundrc con bluez-alsa):
# NINA_ALTOPARLANTE=cassa
# NINA_OPZIONI_APLAY=-B 2000000 -R 500000
```

I ricordi veri vanno in `dati/ricordi.md` e le canzoni in `dati/musica/`: restano sul Raspberry. `ricordi.esempio.md` mostra il formato con nomi inventati.
