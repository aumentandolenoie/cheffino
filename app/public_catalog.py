"""Catalogo pubblico: registro completo per conteggi, snapshot per idoneita'.

Quando esiste lo snapshot verificato, SOLO le schede presenti in esso
sono visibili nei piani; le altre sono restituite come in revisione.
In assenza dello snapshot (migrazione iniziale) resta il comportamento
storico del backend, senza cancellare ricette preesistenti.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "catalogo.json"
PUBLISHED = ROOT / "data" / "catalogo_pubblicato.json"


def _read_list(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Catalogo non valido: {path}")
    return data


def public_catalog():
    records = _read_list(CATALOG)
    if PUBLISHED.exists():
        approved = _read_list(PUBLISHED)
        eligible = {}
        for rec in approved:
            if not isinstance(rec, dict) or rec.get("id") is None or not rec.get("url"):
                raise ValueError("Snapshot con ricetta incompleta")
            if rec["id"] in eligible:
                raise ValueError("ID duplicato nello snapshot pubblicato")
            eligible[rec["id"]] = rec
        merged = []
        for rec in records:
            published = eligible.get(rec.get("id"))
            if published is not None and published.get("url") == rec.get("url"):
                merged.append(published)
            else:
                pending = dict(rec)
                pending["needs_review"] = True
                merged.append(pending)
        records = merged
    return sorted(records, key=lambda r: (
        0 if "giallozafferano" in r.get("source", "").lower() else 1,
        r.get("name", ""),
    ))
