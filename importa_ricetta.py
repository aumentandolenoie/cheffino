"""Import one source recipe into versioned data/catalogo.json.
Run on your PC, commit catalogo.json to GitHub to deploy on Render.
"""
import json, sys, re, hashlib
from pathlib import Path
from app.catalog import fetch_recipe
from app.public_catalog import CATALOG

def scalar(v):
    if isinstance(v,str):
        x=re.search(r"(\d+(?:[.,]\d+)?)",v)
        return float(x.group(1).replace(',','.')) if x else None
    return None

def qty_part(text):
    # Preserve exact source wording: do not guess serving-normalized amounts.
    return [text,None,'da fonte']

def main():
    if len(sys.argv)!=2:
        print("Uso: python importa_ricetta.py https://ricette.giallozafferano.it/...")
        return 2
    try:
        raw=fetch_recipe(sys.argv[1])
        catalog=json.loads(CATALOG.read_text(encoding='utf-8'))
        current=next((r for r in catalog if r.get('url')==raw['url']),None)
        stable_id=int(hashlib.sha256(raw['url'].encode()).hexdigest()[:12],16)+10000
        out={'id':current['id'] if current else stable_id,'name':raw['name'],'emoji':'🍽️',
             'style':'Da classificare','type':'Piatto unico', 'time':None,
             'ingredients_display':raw['ingredients'], 'source':raw['source'],
             'url':raw['url'],'image_url':raw['image_url'],'servings':None,
             'kcal':scalar(raw['nutrition'].get('calories')),
             'protein':scalar(raw['nutrition'].get('proteinContent')),
             'carbs':scalar(raw['nutrition'].get('carbohydrateContent')),
             'fats':scalar(raw['nutrition'].get('fatContent')),
             'cost':None,'ingredients':[qty_part(s) for s in raw['ingredients']],
             'steps':raw['steps'], 'needs_review':True}
        if current: catalog=[out if r.get('url')==raw['url'] else r for r in catalog]
        else: catalog.append(out)
        CATALOG.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f"Importata: {out['name']} — da revisionare prima dell'uso automatico")
        print('File aggiornato: data/catalogo.json (da pubblicare su GitHub).')
        return 0
    except Exception as exc:
        print('Importazione fallita:',exc)
        return 1
if __name__=='__main__': sys.exit(main())
