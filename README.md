# NonneCare: La Radio di Nina

Una radio sul comodino per chi vive con l'Alzheimer. Si accorge da sola quando la persona parla, le fa compagnia di notte con ricordi e canzoni, e avvisa subito la famiglia su Telegram se c'è un rischio.

Progetto in costruzione all'Agentic Hack Rome, 13-14 novembre 2026.

## Come funziona

1. **Ascolto** (`ascolto.py`): il rilevamento della voce gira sul Raspberry; in cloud va solo la frase già ritagliata.
2. **Trascrizione e voce** (`voce.py`): ElevenLabs.
3. **Cervello** (`nina.py`, `prompt_nina.md`): Claude, con regole precise: accoglie e reindirizza, non mente, non dice mai che una persona cara è morta, non finge di essere qualcun altro.
4. **Strumenti** (`strumenti.py`): avvisare la famiglia, lasciare un messaggio per il mattino, mettere la sua canzone.
5. **Registro** (`registro.py`): ogni evento è legato al precedente con un hash, così nessuno può ritoccarlo dopo.

## Sul Raspberry

```bash
sudo apt install -y git mpg123
python -m venv ~/nina-env && ~/nina-env/bin/pip install anthropic elevenlabs webrtcvad "setuptools<80"
cd ~/nina && ~/nina-env/bin/python main.py --eco     # prova dell'audio
~/nina-env/bin/python main.py --testo                # prova del cervello, scrivendo
~/nina-env/bin/python main.py                        # la radio
```

Il file `.env` (mai nel repository):

```
ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
TELEGRAM_TOKEN=...
NINA_VOCE_ID=...            # ID della voce scelta su ElevenLabs
FAMIGLIA_CHAT_ID=...        # chat dei familiari, separate da virgola (python avvisi.py per trovarle)
NINA_NOME_NONNA=...
```

I ricordi veri vanno in `dati/ricordi.md` e le canzoni in `dati/musica/`: restano sul Raspberry. `ricordi.esempio.md` mostra il formato con nomi inventati.
