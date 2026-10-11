"""Diagnostica foto viste realmente dalla API, non solo nel catalogo sorgente."""
import argparse
from collections import Counter
import time
from app.public_catalog import public_catalog
from audit_immagini import probe, safe_image_url


def report(limit=12, online=False, offset=0, delay=0):
    rows = public_catalog()
    visible = [r for r in rows if not r.get("needs_review") and
               r.get("validazione_automatica", {}).get("approved") is not False and
               isinstance(r.get("ingredients"), list) and r.get("ingredients")]
    no_url = [r for r in visible if not r.get("image_url")]
    without_steps = [r for r in visible if not any(isinstance(g,list) and g for g in (r.get("step_images") or []))]
    wrong_url = [r for r in visible if r.get("image_url") and not safe_image_url(r.get("image_url"))]
    print(f"API: totali={len(rows)}; disponibili={len(visible)}; senza_URL={len(no_url)}; URL_fuori_dominio={len(wrong_url)}; senza_foto_passaggi={len(without_steps)}")
    for rec in no_url:
        print(f"SENZA COPERTINA: {rec.get('name')} | id={rec.get('id')} | fonte={rec.get('url')}")
    for rec in wrong_url:
        print(f"URL SOSPETTO: {rec.get('name')} | foto={rec.get('image_url')}")
    results = Counter()
    if online:
        eligible = [r for r in visible if safe_image_url(r.get("image_url"))]
        batch = eligible[offset:offset+limit]
        for rec in batch:
            verdict = probe(rec["image_url"])
            results[verdict] += 1
            if delay:
                time.sleep(delay)
            if verdict != "ok":
                print(f"FOTO NON CONFERMATA: {rec.get('name')} | stato={verdict} | URL={rec.get('image_url')}")
        print(f"Verifica HTTP: offset={offset}; testate={len(batch)}; esiti={dict(results)}")
    return len(no_url), len(wrong_url)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--delay", type=float, default=0)
    opts=parser.parse_args()
    if not 1 <= opts.limit <= 35 or opts.offset < 0 or not 0 <= opts.delay <= 5:
        parser.error("limit 1..35, offset >= 0, delay 0..5")
    report(opts.limit, opts.online, opts.offset, opts.delay)
