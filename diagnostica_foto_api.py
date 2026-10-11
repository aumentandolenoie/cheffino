"""Diagnostica foto viste realmente dalla API, non solo nel catalogo sorgente."""
import argparse
from collections import Counter
from app.public_catalog import public_catalog
from audit_immagini import probe, safe_image_url


def report(limit=12, online=False):
    rows = public_catalog()
    visible = [r for r in rows if not r.get("needs_review") and
               r.get("validazione_automatica", {}).get("approved") is not False and
               isinstance(r.get("ingredients"), list) and r.get("ingredients")]
    no_url = [r for r in visible if not r.get("image_url")]
    wrong_url = [r for r in visible if r.get("image_url") and not safe_image_url(r.get("image_url"))]
    print(f"API: totali={len(rows)}; disponibili={len(visible)}; senza_URL={len(no_url)}; URL_fuori_dominio={len(wrong_url)}")
    for rec in no_url:
        print(f"SENZA COPERTINA: {rec.get('name')} | id={rec.get('id')} | fonte={rec.get('url')}")
    for rec in wrong_url:
        print(f"URL SOSPETTO: {rec.get('name')} | foto={rec.get('image_url')}")
    results = Counter()
    if online:
        eligible = [r for r in visible if safe_image_url(r.get("image_url"))]
        for rec in eligible[:limit]:
            verdict = probe(rec["image_url"])
            results[verdict] += 1
            if verdict != "ok":
                print(f"FOTO NON CONFERMATA: {rec.get('name')} | stato={verdict} | URL={rec.get('image_url')}")
        print(f"Verifica HTTP: testate={min(len(eligible),limit)}; esiti={dict(results)}")
    return len(no_url), len(wrong_url)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--limit", type=int, default=12)
    opts=parser.parse_args()
    report(opts.limit, opts.online)
