"""Cheffino: ripara quantità/unità esplicite già presenti nel catalogo.

Non interroga la rete, non altera foto/passaggi, non approva ricette.
Lavora solo su righe originali degli ingredienti con quantità ancora da verificare.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

CATALOG = Path('data/catalogo.json')
PATTERNS = [
    # 'Pomodori 250 gr', 'Acqua 1 litro', 'Farina 2 etti'
    re.compile(r'^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(grammi?|gr\.?|chilogrammi?|chili|litri?|millilitri?|etti|etto|centilitri?|kg|g|mg|ml|cl|l)\.?$', re.I),
    # 'Uova 2 unità', 'Pane 3 fette', 'Aglio 2 spicchi'
    re.compile(r'^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(unità|pezzi?|fette?|spicchi?|rametti?|foglie?|cucchiai?|cucchiaini?)\.?$', re.I),
]
UNIT = {
    'grammo':('g',1),'grammi':('g',1),'gr':('g',1),'gr.':('g',1),
    'chilogrammo':('g',1000),'chilogrammi':('g',1000),'chilo':('g',1000),'chili':('g',1000),'kg':('g',1000),
    'litro':('ml',1000),'litri':('ml',1000),'l':('ml',1000),
    'millilitro':('ml',1),'millilitri':('ml',1),'ml':('ml',1),
    'centilitro':('ml',10),'centilitri':('ml',10),'cl':('ml',10),
    'etto':('g',100),'etti':('g',100),'g':('g',1),'mg':('mg',1),
    'unità':('pezzi',1),'pezzo':('pezzi',1),'pezzi':('pezzi',1),
    'fetta':('fette',1),'fette':('fette',1),'spicchio':('spicchi',1),'spicchi':('spicchi',1),
    'rametto':('rametti',1),'rametti':('rametti',1),'foglia':('foglie',1),'foglie':('foglie',1),
    'cucchiaio':('cucchiai',1),'cucchiai':('cucchiai',1),
    'cucchiaino':('cucchiaini',1),'cucchiaini':('cucchiaini',1),
}

def explicit_amount(display, existing):
    if not isinstance(display, str) or not isinstance(existing, list) or len(existing) < 3:
        return None
    if existing[1] is not None or existing[2] != 'da verificare':
        return None
    if existing[0].strip() != display.strip():
        return None
    text = ' '.join(display.split())
    for regex in PATTERNS:
        match = regex.fullmatch(text)
        if not match:
            continue
        name, qty_text, raw_unit = match.groups()
        if not name.strip() or re.search(r'\d', name):
            return None
        try:
            quantity = float(qty_text.replace(',', '.'))
        except ValueError:
            return None
        if not 0 < quantity <= 100000:
            return None
        key = raw_unit.lower().rstrip('.')
        if key not in UNIT:
            return None
        unit, scale = UNIT[key]
        quantity *= scale
        return [name.strip(), int(quantity) if quantity.is_integer() else quantity, unit]
    return None

def process(path=CATALOG, dry_run=False):
    path = Path(path)
    recipes = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(recipes, list):
        raise ValueError('Il catalogo deve essere una lista JSON')
    stats = Counter()
    missing = []
    for rec in recipes:
        if rec.get('source') != 'GialloZafferano':
            continue
        displayed, ingredients = rec.get('ingredients_display'), rec.get('ingredients')
        if not isinstance(displayed, list) or not isinstance(ingredients, list) or len(displayed) != len(ingredients):
            continue
        recovered = 0
        for i, (original, old) in enumerate(zip(displayed, ingredients)):
            new = explicit_amount(original, old)
            if new:
                ingredients[i] = new
                recovered += 1
                stats['ingredients'] += 1
                print(f"Unità esplicita recuperata: {rec.get('name')} | {original} -> {new[1]} {new[2]}")
        if recovered:
            stats['recipes'] += 1
        unresolved = sum(isinstance(x,list) and len(x)>=3 and x[2]=='da verificare' for x in ingredients)
        if unresolved and rec.get('classificazione_automatica',{}).get('esito') == 'candidato':
            missing.append((unresolved,rec.get('name','')))
    if stats['ingredients'] and not dry_run:
        path.write_text(json.dumps(recipes,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    missing.sort(key=lambda x: (x[0],x[1]))
    print(f"Unità esplicite: ricette={stats['recipes']}; ingredienti={stats['ingredients']}; candidate_con_quantita_ambigue={len(missing)}; modalita={'test' if dry_run else 'salvataggio'}")
    if missing:
        print('Priorità controllo ingredienti: '+'; '.join(f'{n} ({cnt} quantità)' for cnt,n in missing[:12]))
    return stats

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--file', type=Path, default=CATALOG)
    ap.add_argument('--dry-run', action='store_true')
    opts=ap.parse_args()
    process(opts.file,opts.dry_run)
