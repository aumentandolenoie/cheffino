"""Catalogo pubblico: registro completo per conteggi, snapshot per idoneita'.

Quando esiste lo snapshot verificato, SOLO le schede presenti in esso
sono visibili nei piani; le altre sono restituite come in revisione.
In assenza dello snapshot (migrazione iniziale) resta il comportamento
storico del backend, senza cancellare ricette preesistenti.
"""
import json
from pathlib import Path
from urllib.parse import urlparse

from controlla_integrita_catalogo import image_id
from app.photo_policy import publishable_step_photos, certified_source_absence

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "catalogo.json"
PUBLISHED = ROOT / "data" / "catalogo_pubblicato.json"


def _read_list(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Catalogo non valido: {path}")
    return data


def _trusted_photo(url):
    if not isinstance(url, str):
        return False
    try:
        p = urlparse(url)
        host = (p.hostname or "").lower()
        return (p.scheme == "https" and
                (host == "giallozafferano.it" or host.endswith(".giallozafferano.it"))
                and p.port in (None, 443) and not p.username and not p.password)
    except ValueError:
        return False


def _refresh_photo_fields(approved, latest):
    """Copia SOLO le immagini della stessa ricetta dalla versione aggiornata.

    Lo snapshot resta autoritativo per idoneita', ingredienti e procedimento.
    Le immagini del catalogo di lavoro possono essere piu' recenti dello
    snapshot: non serve attendere la successiva pubblicazione bisettimanale.
    """
    result = dict(approved)
    main = latest.get("image_url")
    if _trusted_photo(main):
        result["image_url"] = main
    groups = latest.get("step_images")
    if (latest.get("steps") == approved.get("steps") and
            isinstance(groups, list) and groups and
            len(groups) == len(approved.get("steps") or []) and
            all(isinstance(g, list) and all(_trusted_photo(u) for u in g)
                for g in groups)):
        cover_id = image_id(result.get("image_url"))
        photo_ids = {image_id(u) for group in groups for u in group}
        photo_ids.discard(None)
        if cover_id is None or all(step_id == cover_id for step_id in photo_ids):
            result["step_images"] = groups
            result["images_import_version"] = latest.get("images_import_version", 0)
    proof = latest.get("step_photo_source_evidence")
    if isinstance(proof,dict):
        candidate = dict(result,step_photo_source_evidence=proof)
        if certified_source_absence(candidate):
            result["step_photo_source_evidence"] = proof
    return result


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
                effective = _refresh_photo_fields(published, rec)
                if not publishable_step_photos(effective):
                    # Il record resta nel catalogo totale: soltanto il piano
                    # richiede foto reali o prova di assenza della fonte.
                    effective["needs_review"] = True
                    effective["photo_review_reason"] = "foto_passaggi_non_verificate"
                merged.append(effective)
            else:
                pending = dict(rec)
                pending["needs_review"] = True
                merged.append(pending)
        records = merged
    from app.recipe_media import display_groups
    from app.diete import assess_recipe
    records = [dict(r, step_images_display=display_groups(r), diete=assess_recipe(r)) for r in records]
    return sorted(records, key=lambda r: (
        0 if "giallozafferano" in r.get("source", "").lower() else 1,
        r.get("name", ""),
    ))

