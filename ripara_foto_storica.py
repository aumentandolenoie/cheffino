"""Correzione controllata della copertina storica ID 5, dalla sua fonte originale.

Non inventa una foto: utilizza la fotografia dell'articolo sorgente.
Per sicurezza modifica i due cataloghi soltanto se la risorsa restituisce
un contenuto image/* e il redirect rimane sul sito della fonte.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ID = 5
PAGE = "https://blog.giallozafferano.it/allacciateilgrembiule/pasta-pomodoro-basilico/"
IMAGE = "https://blog.giallozafferano.it/allacciateilgrembiule/wp-content/uploads/2026/05/pasta-pomodoro-e-basilico3-720x480.jpg"


def image_available(url=IMAGE, opener=urlopen):
    p = urlparse(url)
    if (p.scheme != "https" or p.hostname != "blog.giallozafferano.it"
            or not p.path.startswith("/allacciateilgrembiule/wp-content/uploads/")
            or p.port not in (None, 443)):
        return False
    req = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; Cheffino/1.0)",
        "Referer": PAGE, "Accept": "image/avif,image/webp,image/jpeg,image/*",
        "Range": "bytes=0-127",
    })
    try:
        with opener(req, timeout=15) as response:
            target = urlparse(response.geturl())
            return (response.status in (200, 206)
                    and target.hostname == "blog.giallozafferano.it"
                    and response.headers.get("Content-Type", "").lower().startswith("image/"))
    except Exception as exc:
        print(f"Copertina non confermata: {type(exc).__name__}: {exc}")
        return False


def patch(path, dry_run=False):
    p = Path(path)
    records = json.loads(p.read_text(encoding="utf-8"))
    targets = [r for r in records if r.get("id") == ID and r.get("url") == PAGE]
    if len(targets) != 1:
        raise ValueError(f"Scheda ID 5 con URL esatto non trovata in {path}")
    rec = targets[0]
    if rec.get("image_url") == IMAGE:
        print(f"Copertina già corretta: {path}")
        return False
    if rec.get("image_url"):
        raise ValueError(f"La scheda {ID} ha già una copertina diversa: verifica manuale")
    if dry_run:
        print(f"Copertina candidata: {rec.get('name')} | {IMAGE} | catalogo={path}")
        return True
    rec["image_url"] = IMAGE
    p.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Copertina aggiornata: {rec.get('name')} | catalogo={path}")
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    opts = ap.parse_args()
    if not image_available():
        raise SystemExit("STOP: immagine originale non verificabile, cataloghi intatti")
    for f in ("data/catalogo.json", "data/catalogo_pubblicato.json"):
        patch(f, opts.dry_run)
