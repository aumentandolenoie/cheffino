"""Le due copie dell'app devono restare identiche.

Vercel (preset FastAPI) e Render servono frontend/index.html dalla route «/»
di app/main.py; index.html nella radice resta come copia di sicurezza per
hosting statici. Per aggiornarla: python sincronizza_index.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_index_radice_uguale_al_frontend():
    assert (ROOT / 'index.html').read_bytes() == (ROOT / 'frontend' / 'index.html').read_bytes(), \
        "index.html diverso da frontend/index.html: esegui python sincronizza_index.py"
