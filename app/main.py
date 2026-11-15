from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .public_catalog import public_catalog

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
    rows=public_catalog()
    return {"count":len(rows),"recipes":rows}
