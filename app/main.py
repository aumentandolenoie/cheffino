from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from .catalog import list_recipes

ROOT=Path(__file__).resolve().parent.parent
app=FastAPI(title='Cheffino - catalogo locale',version='0.1.0')

@app.get('/')
def index(): return FileResponse(ROOT/'frontend'/'index.html')

@app.get('/api/health')
def health(): return {'status':'ok','message':'Server Cheffino attivo'}

@app.get('/api/recipes')
def recipes(): return {'count':len(data:=list_recipes()),'recipes':data}
