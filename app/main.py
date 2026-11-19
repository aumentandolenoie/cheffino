import json
from datetime import date
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .public_catalog import public_catalog
from .volantini import CATENE, link_da_aprire

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title="Pepito — catalogo ricette",version="0.3.0")

@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")

ICONS={"apple-touch-icon.png","icon-192.png","icon-512.png","favicon-64.png","pepito.svg"}


@app.get("/icons/{name}")
def icon(name: str):
    # Solo i file dell'icona, nessun accesso ad altri percorsi.
    if name not in ICONS:
        raise HTTPException(status_code=404)
    return FileResponse(ROOT / "icons" / name, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(ROOT / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/api/health")
def health():
    return {"status":"ok","catalog_count":len(public_catalog())}

@app.get("/api/recipes")
def recipes():
    # Le ricette escluse per scelta dell'app (dolci, lievitati, antipasti leggeri…)
    # non sono «in revisione»: non diventeranno mai piatti del piano, quindi non
    # si inviano all'app e non entrano nei conteggi.
    rows=[r for r in public_catalog() if not r.get("esclusa_dal_piano")]
    return {"count":len(rows),"recipes":rows}


@app.get("/api/volantini")
def volantini():
    """Volantini in corso (data/volantini.json, aggiornato ogni giorno dal workflow 06)."""
    path = ROOT / "data" / "volantini.json"
    try:
        dati = json.loads(path.read_text())
    except (OSError, ValueError):
        dati = {"aggiornato_il": None, "catene": {}}
    oggi = date.today()
    catene = dati.setdefault("catene", {})
    for nome, info in CATENE.items():
        voce = catene.setdefault(nome, {"pagina_ufficiale": info["pagina"], "sito": info["sito"],
                                        "tipo": info["tipo"], "volantino": None, "prossimo": None,
                                        "metodo": "pagina_ufficiale"})
        voce["da_aprire_oggi"] = link_da_aprire(nome, dati, oggi)
    return dati
