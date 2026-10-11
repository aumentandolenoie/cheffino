"""Diagnosi fotografica delle sole ricette realmente pubblicate.

Sola lettura: non modifica approvazioni, ricette o immagini. Le informazioni
sulla fonte sono indicative; mai usare una somiglianza bassa per assegnare foto.
"""
from collections import Counter
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.public_catalog import public_catalog
from importa_foto_passaggi import (
    ImagesHTML, UA, associate_steps, fetch_html, robots_policy,
    normalize, steps_equivalent,
)
from app.catalog import parse_recipe
from pulisci_procedimenti import clean_steps


def missing_gallery(rec):
    return not any(isinstance(group, list) and group for group in (rec.get("step_images") or []))


def available(rec):
    return (not rec.get("needs_review") and
            (not isinstance(rec.get("validazione_automatica"), dict)
             or rec["validazione_automatica"].get("approved") is not False)
            and isinstance(rec.get("ingredients"), list) and bool(rec["ingredients"])
            and isinstance(rec.get("steps"), list) and bool(rec["steps"]))


def diagnose(online=False):
    listed = [r for r in public_catalog() if available(r) and missing_gallery(r)]
    print("SENZA_GALLERIA_PUBBLICATE:", len(listed), flush=True)
    policy = robots_policy() if online else None
    causes = Counter()
    for rec in listed:
        name, url, steps = rec.get("name"), rec.get("url"), rec["steps"]
        info = f"id={rec.get('id')} | {name} | blocchi={len(steps)} | {url}"
        if not online:
            print("SCHEDA:", info, flush=True)
            continue
        if urlparse(url).hostname != "ricette.giallozafferano.it":
            category = "fonte_non_supportata"
            print("DIAGNOSI:",category,"|",info,flush=True)
            causes[category] += 1
            continue
        if not policy.can_fetch(UA, url):
            category = "robots_vieta"
            print("DIAGNOSI:",category,"|",info,flush=True)
            causes[category] += 1
            continue
        try:
            html = fetch_html(url)
            parsed = parse_recipe(html, url)
            raw = parsed.get("steps", [])
            cleaned, _ = clean_steps(raw)
            parser = ImagesHTML(name, url)
            parser.feed(html)
            matches = [round(SequenceMatcher(None,normalize(a),normalize(b),autojunk=False).ratio(),2)
                       for a,b in zip(cleaned,steps)]
            equivalent = steps_equivalent(raw, steps)
            groups, method = associate_steps(parser,raw,len(steps)) if equivalent else ([],None)
            if not parser.photos and not parser.strips:
                category = "fonte_senza_foto_rilevate"
            elif not equivalent:
                category = "procedimento_diverso"
            elif not groups:
                category = "numerazione_non_abbinabile"
            else:
                category = "galleria_potenzialmente_recuperabile"
            causes[category] += 1
            print("DIAGNOSI:",category,"|",info,
                  f"| foto_numerate={len(parser.photos)} strip={len(parser.strips)}"
                  f" | passi_fonte={len(raw)} somiglianze={matches} metodo={method}",
                  flush=True)
        except Exception as exc:
            causes["errore_fonte"] += 1
            print("DIAGNOSI: errore_fonte |",info,"|",type(exc).__name__,str(exc)[:180],flush=True)
    print("RIEPILOGO:",dict(causes),flush=True)


if __name__ == "__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--online",action="store_true")
    a=p.parse_args()
    diagnose(a.online)
