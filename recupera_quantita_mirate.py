"""Cheffino: recupero conservativo di quantita' esplicite da ingredienti pubblicati.

Gestisce frazioni HTML (½, &frac12;), unita' contabili (coste, filetti,
cucchiaini...), e un elenco ristretto di ortaggi singoli privi di unita'.
NON attribuisce grammi a numeri senza unita' e NON interpreta derivati
come succo o scorza come frutti interi. La validazione resta separata.
"""
import argparse
import html
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT = Path('data/catalogo.json')
NUMBER = r'(?:\d+(?:[.,]\d+)?|[¼½¾⅓⅔⅛])'
FRACTIONS = {'¼': .25, '½': .5, '¾': .75, '⅓': 1/3, '⅔': 2/3, '⅛': .125}
UNITS = {
    'costa': 'coste', 'coste': 'coste',
    'filetto': 'filetti', 'filetti': 'filetti',
    'rametto': 'rametti', 'rametti': 'rametti',
    'ciuffo': 'ciuffi', 'ciuffi': 'ciuffi',
    'spicchio': 'spicchi', 'spicchi': 'spicchi',
    'foglia': 'foglie', 'foglie': 'foglie',
    'cucchiaio': 'cucchiai', 'cucchiai': 'cucchiai',
    'cucchiaino': 'cucchiaini', 'cucchiaini': 'cucchiaini',
    'bicchiere': 'bicchieri', 'bicchieri': 'bicchieri',
    'pizzico': 'pizzichi', 'pizzichi': 'pizzichi',
    'fetta': 'fette', 'fette': 'fette',
    'pezzo': 'pezzi', 'pezzi': 'pezzi',
}
UNIT_RE = re.compile(rf'^(.+?)\s+({NUMBER})\s+({"|".join(sorted(UNITS, key=len, reverse=True))})$', re.I)
COUNT_RE = re.compile(rf'^(.+?)\s+({NUMBER})$', re.I)
# Solo nomi inequivocabili: lascia "pinoli 15" e "pepe 0,3" da verificare.
COUNTABLE = re.compile(r'^(?:scalogn[oi]|porr[oi]|ravanelli?(?:\s+gross[oi])?|peperoncini?(?:\s+fresc[oi])?(?:\s+ross[oi])?|cipoll[ae](?:\s+\w+)?|carot[ae]|patat[ae]|limon[ei]|uov[ao]|avocado(?:\s+maturo)?|pomodor[io](?:\s+\w+)?|zucchin[ae])$', re.I)
# Il numero senza unita' NON si applica ai derivati. Niente "succo di limone 1 pezzo".
DERIVED = re.compile(r'\b(?:succo|scorza|concentrato|polpa|estratto|crema|passata|spremuta|salsa|purea|purè)\b', re.I)


def parse_amount(raw):
    raw = html.unescape(raw)
    if raw in FRACTIONS:
        return FRACTIONS[raw]
    try:
        val = float(raw.replace(',', '.'))
        return val if 0 < val <= 10000 else None
    except ValueError:
        return None


def targeted(display, existing):
    if not isinstance(display, str) or not isinstance(existing, list) or len(existing) != 3:
        return None
    if existing[1] is not None or existing[2] != 'da verificare' or existing[0].strip() != display.strip():
        return None
    text = ' '.join(html.unescape(display).split())
    match = UNIT_RE.fullmatch(text)
    if match:
        name, raw, unit = match.groups()
        if not name.strip() or re.search(r'\d', name):
            return None
        qty = parse_amount(raw)
        if qty is None:
            return None
        return [name.strip(), int(qty) if qty.is_integer() else qty, UNITS[unit.lower()]]
    match = COUNT_RE.fullmatch(text)
    if match:
        name, raw = match.groups()
        if not COUNTABLE.fullmatch(name.strip()) or DERIVED.search(name):
            return None
        qty = parse_amount(raw)
        if qty is None:
            return None
        return [name.strip(), int(qty) if qty.is_integer() else qty, 'pezzi']
    return None


def process(path=DEFAULT, dry_run=False):
    path = Path(path)
    recipes = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(recipes, list):
        raise ValueError('Catalogo JSON non valido')
    stats = Counter()
    for recipe in recipes:
        if recipe.get('source') != 'GialloZafferano':
            continue
        display = recipe.get('ingredients_display')
        ingredients = recipe.get('ingredients')
        if not isinstance(display, list) or not isinstance(ingredients, list) or len(display) != len(ingredients):
            continue
        changed = 0
        for i, original in enumerate(display):
            new = targeted(original, ingredients[i])
            if new is not None:
                ingredients[i] = new
                changed += 1
                stats['ingredients'] += 1
                print(f"Quantita mirata: {recipe.get('name')} | {original} -> {new[1]} {new[2]}")
        if changed:
            stats['recipes'] += 1
    if stats['ingredients'] and not dry_run:
        path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Quantita mirate: ricette={stats['recipes']}; ingredienti={stats['ingredients']}; modalita={'test' if dry_run else 'salvataggio'}")
    return stats

if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--file', type=Path, default=DEFAULT)
    cli.add_argument('--dry-run', action='store_true')
    opts = cli.parse_args()
    process(opts.file, opts.dry_run)
