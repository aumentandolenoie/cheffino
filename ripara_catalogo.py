"""Ripara, con prudenza, le schede importate in Cheffino.

Rilegge soltanto gli URL GialloZafferano già presenti in data/catalogo.json;
non inventa porzioni, tempi, quantità o valori nutrizionali.
Non modifica needs_review e non approva ricette automaticamente.
"""
import argparse
import json
import re
import time
from pathlib import Path
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser
from urllib.request import Request, urlopen

from app.catalog import fetch_recipe

CATALOG = Path('data/catalogo.json')
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
ROBOTS = 'https://ricette.giallozafferano.it/robots.txt'


def number(s):
    try: return float(str(s).replace(',', '.'))
    except (ValueError, TypeError): return None


def parse_servings(value):
    if isinstance(value, list):
        for v in value:
            ans = parse_servings(v)
            if ans: return ans
        return None
    if isinstance(value, (int, float)) and value > 0 and int(value) == value:
        return int(value)
    s = str(value or '').strip().casefold()
    # '4 persone', '[\'4 persone\']', '4 porzioni'; non interpretare '400 g'
    m = re.search(r'\b(\d{1,2})\s*(?:persone|porzioni|personas|servings|people)\b', s)
    if m and int(m.group(1)) > 0: return int(m.group(1))
    if re.fullmatch(r'\d{1,2}', s) and int(s)>0: return int(s)
    return None


def parse_duration(value):
    # Durata ISO 8601, es. PT1H25M; durata totale con HH e MM.
    s = str(value or '')
    m = re.fullmatch(r'P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', s)
    if not m: return None
    h, minutes, sec = (int(x or 0) for x in m.groups())
    return h * 60 + minutes + (1 if sec else 0) or None


def parse_ingredient(text):
    """Restituisce [nome, quantità, unità] o None se ambiguo.
    Mantiene il testo originale in ingredients_display.
    """
    s = re.sub(r'\s+', ' ', str(text)).strip()
    if not s: return None
    qb = re.match(r'^(.*?)\s+q\.?\s*b\.?$', s, re.I)
    if qb and qb.group(1).strip(): return [qb.group(1).strip(), None, 'q.b.']
    # Formati pubblicati: 'Filetti di sgombro 600 g', 'Aglio 1 spicchio'.
    m = re.match(r'^(.*?)\s+(\d+(?:[.,]\d+)?)\s*(kg|g|mg|ml|l|cl|spicchio|spicchi|cucchiai?|cucchiaini?|pezzi?|fette?|rametti?|foglie?|uova?)\s*$', s, re.I)
    if m and m.group(1).strip():
        return [m.group(1).strip(), number(m.group(2)), m.group(3).lower()]
    # Se manca un'unità di misura inequivocabile, non indovinare.
    return [s, None, 'da verificare']


def numeric_nutrition(value):
    m = re.search(r'\d+(?:[.,]\d+)?', str(value or ''))
    return number(m.group(0)) if m else None


def enrich(rec, raw):
    revised = dict(rec)
    ingredients = raw.get('ingredients') or rec.get('ingredients_display') or []
    revised['ingredients_display'] = ingredients
    revised['ingredients'] = [parse_ingredient(x) for x in ingredients]
    revised['servings'] = parse_servings(raw.get('yield_text')) or rec.get('servings')
    revised['time'] = parse_duration(raw.get('total_time')) or (
        (parse_duration(raw.get('prep_time')) or 0) + (parse_duration(raw.get('cook_time')) or 0)
    ) or rec.get('time')
    nut = raw.get('nutrition') or {}
    for target, source in [('kcal','calories'), ('protein','proteinContent'),
                           ('carbs','carbohydrateContent'), ('fats','fatContent')]:
        revised[target] = numeric_nutrition(nut.get(source)) if nut.get(source) else rec.get(target)
    revised['steps'] = raw.get('steps') or rec.get('steps')
    revised['image_url'] = raw.get('image_url') or rec.get('image_url')
    revised['needs_review'] = True
    revised['repaired_at'] = datetime.now(timezone.utc).isoformat()
    revised.pop('classificazione_automatica', None) # il classificatore la ricrea
    return revised


def robots_policy():
    req = Request(ROBOTS, headers={'User-Agent': UA, 'Accept': 'text/plain'})
    with urlopen(req, timeout=25) as resp:
        text = resp.read(512001)
        if len(text)>512000: raise ValueError('robots.txt troppo grande')
    parser = RobotFileParser()
    parser.set_url(ROBOTS)
    parser.parse(text.decode('utf-8-sig', errors='replace').splitlines())
    return parser


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=20)
    ap.add_argument('--delay', type=float, default=2.5)
    opts = ap.parse_args()
    if not 1<=opts.limit<=50 or opts.delay<2: ap.error('limit 1..50 e delay >=2 richiesti')
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    robots = robots_policy()
    refreshed = incomplete = failed = blocked = 0
    for idx, rec in enumerate(catalog):
        if refreshed+failed>=opts.limit: break
        if not rec.get('needs_review') or rec.get('source')!='GialloZafferano' or rec.get('repaired_at'): continue
        url=rec.get('url','')
        if not url.startswith('https://ricette.giallozafferano.it/') or not robots.can_fetch(UA,url):
            blocked+=1; continue
        try:
            raw=fetch_recipe(url)
            revised=enrich(rec,raw)
            catalog[idx]=revised
            refreshed+=1
            if not revised['servings'] or any(x[2]=='da verificare' for x in revised['ingredients']): incomplete+=1
            print(f'Riletta: {rec["name"]} | porzioni={revised["servings"]} | tempo={revised["time"]} | ingredienti={len(revised["ingredients"])}', flush=True)
            CATALOG.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        except Exception as e:
            failed+=1
            print(f'Errore su {url}: {e}',flush=True)
        time.sleep(opts.delay)
    print(f'Riparate={refreshed}; ancora incomplete={incomplete}; errori={failed}; bloccate={blocked}; totale={len(catalog)}',flush=True)

if __name__=='__main__': main()
