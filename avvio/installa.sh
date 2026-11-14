#!/bin/sh
# Installa e avvia i due servizi: la radio e il bot della famiglia partono da soli all'accensione.
set -e
pkill -f famiglia.py || true   # ferma eventuali copie lanciate a mano (due bot insieme litigano con Telegram)
pkill -f main.py || true
sudo cp "$(dirname "$0")"/nina-radio.service "$(dirname "$0")"/nina-famiglia.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nina-radio nina-famiglia
sleep 3
systemctl --no-pager --lines=0 status nina-radio nina-famiglia | grep -E "●|Active"
