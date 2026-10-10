"""Versioned catalog bundled in GitHub (survives Render Free restarts)."""
import json
from pathlib import Path

CATALOG=Path(__file__).resolve().parent.parent / "data" / "catalogo.json"

def public_catalog():
    data=json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data,list):
        raise ValueError("Catalogo non valido")
    return sorted(data,key=lambda r:(0 if 'giallozafferano' in r.get('source','').lower() else 1,r.get('name','')))
