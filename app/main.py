from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from .public_catalog import public_catalog

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title="Cheffino — catalogo ricette",version="0.2.0")

@app.get("/")
def index():
    return FileResponse(ROOT / "frontend" / "index.html")

@app.get("/api/health")
def health():
    return {"status":"ok","catalog_count":len(public_catalog())}

@app.get("/api/recipes")
def recipes():
    rows=public_catalog()
    return {"count":len(rows),"recipes":rows}
