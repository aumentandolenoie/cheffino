#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null; then echo 'Installa Python 3 prima di avviare.'; exit 1; fi
if [ ! -d .venv ]; then python3 -m venv .venv; fi
. .venv/bin/activate
python -m pip install -r requirements.txt
printf '\nApri nel browser: http://127.0.0.1:8000\nPer fermare premi Ctrl+C.\n\n'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
