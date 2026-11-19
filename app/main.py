import json
from datetime import date
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from .public_catalog import public_catalog
from .volantini import CATENE, link_da_aprire

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title="Pepito — catalogo ricette",version="0.4.0")
# Il catalogo è circa 1,2 MB di JSON: compresso ne viaggiano ~200 KB.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Cache sulla CDN di Vercel: i dati cambiano solo con un nuovo deploy (ogni
# commit dei workflow ne crea uno) e Vercel svuota la cache a ogni deploy.
# Così l'app non aspetta l'avvio della funzione Python a ogni apertura.
CACHE_CDN = {
    "/": "public, max-age=0, s-maxage=86400, stale-while-revalidate=604800",
    "/api/recipes": "public, max-age=0, s-maxage=86400, stale-while-revalidate=604800",
    # contiene il link «da aprire oggi»: si ricalcola almeno ogni ora
    "/api/volantini": "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400",
    "/sw.js": "public, max-age=0, must-revalidate",
}


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    rule = CACHE_CDN.get(request.url.path)
    if rule and request.method == "GET" and response.status_code == 200:
        response.headers["Cache-Control"] = rule
    return response


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


@app.get("/sw.js")
def service_worker():
    # Dalla radice, così il service worker controlla tutta l'app.
    return FileResponse(ROOT / "frontend" / "sw.js", media_type="application/javascript",
                        headers={"Service-Worker-Allowed": "/"})


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
    rows=[per_app(r) for r in public_catalog() if not r.get("esclusa_dal_piano")]
    return {"count":len(rows),"recipes":rows}


# Solo i campi che l'app usa: i dati di lavoro della pipeline (testi grezzi,
# versioni precedenti, diagnostica) restano nel repository.
CAMPI_APP = ("id", "name", "emoji", "time", "kcal", "protein", "carbs", "fats", "cost", "servings",
             "type", "stili", "ingredients", "steps", "image_url", "source", "url", "needs_review",
             "quantita_dedotte")


def per_app(r):
    out = {k: r[k] for k in CAMPI_APP if r.get(k) is not None}
    if not out.get("cost") and r.get("source_cost"):
        out["cost"] = r["source_cost"]  # costo indicato da GialloZafferano
    out["step_images_display"] = r.get("step_images_display") or r.get("step_images") or []
    va = r.get("validazione_automatica")
    if isinstance(va, dict):
        out["validazione_automatica"] = {k: va[k] for k in ("approved", "tools") if k in va}
    cop = r.get("copertina_verifica")
    if isinstance(cop, dict) and cop.get("esito"):
        out["copertina_verifica"] = {"esito": cop["esito"]}
    prova = r.get("step_photo_source_evidence")
    if isinstance(prova, dict) and prova.get("status"):
        out["step_photo_source_evidence"] = {"status": prova["status"]}
    diete = r.get("diete")
    if isinstance(diete, dict):
        out["diete"] = {k: diete[k] for k in ("compatibilita", "motivi") if k in diete}
    return out


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
