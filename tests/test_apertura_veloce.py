"""Apertura veloce: catalogo leggero, compresso, in cache sulla CDN e offline."""
import gzip
import json
from pathlib import Path

import app.main as m

ROOT = Path(__file__).resolve().parent.parent


def test_catalogo_per_app_leggero_e_completo():
    payload = m.recipes()
    rows = payload["recipes"]
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    # limite delle funzioni Vercel: 4,5 MB; teniamo ampio margine
    assert len(raw) < 2_500_000, len(raw)
    assert len(gzip.compress(raw)) < 500_000
    for r in rows:
        for vietato in ("steps_raw", "steps_clean", "steps_precedenti", "media_extraction",
                        "image_url_precedente", "source_synced_at"):
            assert vietato not in r
        assert r["id"] is not None and r["url"] and r["name"]
        assert "step_images_display" in r
    pubblicate = [r for r in rows if not r.get("needs_review")]
    assert pubblicate and all(r.get("steps") and r.get("ingredients") for r in pubblicate)
    assert all(set(r["diete"]) <= {"compatibilita", "motivi"} for r in rows if "diete" in r)


def test_frontend_usa_solo_campi_inviati():
    import re
    html = (ROOT / "frontend" / "index.html").read_text()
    seg = html[html.index("async function caricaCatalogoServer"):html.index("catalogBrowse.push(item)") + 2000]
    usati = set(re.findall(r"entry\.([a-zA-Z_]+)", seg))
    inviati = set(m.CAMPI_APP) | {"step_images_display", "validazione_automatica", "copertina_verifica",
                                  "step_photo_source_evidence", "diete", "step_images"}
    assert usati <= inviati, usati - inviati


def test_service_worker_e_cache():
    sw = (ROOT / "frontend" / "sw.js").read_text()
    assert "'/api/recipes'" in sw and "self.skipWaiting()" in sw
    for f in ("frontend/index.html", "index.html"):
        assert "navigator.serviceWorker?.register('/sw.js')" in (ROOT / f).read_text()
    assert "s-maxage" in m.CACHE_CDN["/api/recipes"]
    assert json.loads((ROOT / "vercel.json").read_text())["regions"] == ["fra1"]
