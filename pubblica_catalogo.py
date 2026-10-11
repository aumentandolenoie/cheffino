"""Produce uno snapshot pubblicabile senza modificare i record in lavorazione.

Conserva le 11 schede preesistenti, ma impone alle importazioni un controllo
supplementare sugli URL e sull'identità delle immagini riconoscibile.
La disponibilità HTTP delle immagini richiede un audit di rete separato.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from controlla_integrita_catalogo import image_id
from app.photo_policy import publishable_step_photos

SOURCE = Path("data/catalogo.json")
TARGET = Path("data/catalogo_pubblicato.json")


def eligible(rec):
    if not isinstance(rec, dict) or not rec.get("name") or not rec.get("url"):
        return False, "scheda_base_incompleta"
    if rec.get("needs_review") is True:
        return False, "in_revisione"
    verdict = rec.get("validazione_automatica")
    if isinstance(verdict, dict) and verdict.get("approved") is not True:
        return False, "validazione_non_approvata"
    image = rec.get("image_url")
    has_cover = isinstance(image, str) and urlparse(image).scheme == "https" and bool(urlparse(image).hostname)
    # Anche le schede storiche richiedono una copertina: le vecchie
    # eccezioni erano temporanee e sono state riparate.
    if not has_cover:
        return False, "copertina_assente"
    if isinstance(verdict, dict):
        if not isinstance(rec.get("steps"), list) or not rec["steps"]:
            return False, "procedimento_assente"
        # La foto principale può avere un formato privo di ID: non inventiamo corrispondenze.
        cover_id = image_id(image)
        if cover_id:
            for group in rec.get("step_images") or []:
                if not isinstance(group, list):
                    return False, "formato_foto_non_valido"
                for url in group:
                    step_id = image_id(url)
                    if step_id and step_id != cover_id:
                        return False, "foto_di_altra_ricetta"
    if not publishable_step_photos(rec):
        return False, "foto_passaggi_non_verificate"
    return True, "ok"


def publish(source=SOURCE, target=TARGET):
    records = json.loads(Path(source).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Il catalogo sorgente deve essere una lista")
    accepted, rejected, urls, ids = [], Counter(), set(), set()
    for rec in records:
        ok, reason = eligible(rec)
        if not ok:
            rejected[reason] += 1
            continue
        if rec["url"] in urls or rec.get("id") in ids:
            raise ValueError("Duplicato nel catalogo approvato: " + rec["name"])
        urls.add(rec["url"])
        ids.add(rec.get("id"))
        accepted.append(rec)
    if not accepted:
        raise ValueError("Nessuna ricetta idonea: snapshot precedente non sovrascritto")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(accepted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(target)
    print(f"Pubblicazione: approvate={len(accepted)}; escluse={sum(rejected.values())}; motivi={dict(rejected)}")
    return accepted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--target", type=Path, default=TARGET)
    args = parser.parse_args()
    publish(args.source, args.target)
