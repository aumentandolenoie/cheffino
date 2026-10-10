"""Recupera quantità esplicite in numero di pezzi senza inventarle.

Converte soltanto ingredienti pubblicati nel formato 'Cipolle dorate 1',
'Limoni 2' ecc. quando il parser precedente ha conservato l'intera stringa
come 'da verificare'. Non certifica allergeni o valori nutrizionali.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT = Path('data/catalogo.json')
# Solo prodotti singoli inequivocabilmente contabili. Evitiamo ingredienti complessi.
COUNTABLE = re.compile(
    r'\b(?:cipoll[ae]|aglio|spicchi? di aglio|carot[ae]|patat[ae]|limon[ei]|'
    r'aranc[ei]|mele?|pere?|zucchin[ae]|melanzan[ae]|peperon[ei]|'
    r'pomodor[io]|uov[ao]|banan[ae]|lime|avocado|cetriol[io])\b', re.I)
EXPLICIT = re.compile(r'^(.+?)\s+([1-9]\d?)$')


def normalize_one(display, existing):
    if not isinstance(display, str) or not isinstance(existing, list) or len(existing) != 3:
        return None
    if existing[1] is not None or existing[2] != 'da verificare':
        return None
    match = EXPLICIT.fullmatch(display.strip())
    if not match:
        return None
    name, raw_count = match.groups()
    if not COUNTABLE.search(name) or re.search(r'\d', name):
        return None
    # Non dedurre unità da altre parti del nome: è una quantità in pezzi non in grammi.
    if existing[0].strip() != display.strip():
        return None
    return [name.strip(), int(raw_count), 'pezzi']


def process(path=DEFAULT, dry_run=False):
    path = Path(path)
    records = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(records, list):
        raise ValueError('Catalogo non valido: attesa lista')
    stats = Counter()
    for rec in records:
        source = rec.get('source', '')
        if source != 'GialloZafferano' or not str(rec.get('url', '')).startswith('https://ricette.giallozafferano.it/'):
            continue
        displayed = rec.get('ingredients_display') or []
        ingredients = rec.get('ingredients') or []
        if not isinstance(displayed, list) or not isinstance(ingredients, list) or len(displayed) != len(ingredients):
            continue
        modified = 0
        for idx, (display, old) in enumerate(zip(displayed, ingredients)):
            new = normalize_one(display, old)
            if new is not None:
                ingredients[idx] = new
                modified += 1
                print(f"Quantità esplicita recuperata: {rec.get('name')} | {display} -> {new[1]} pezzi")
        if modified:
            stats['recipes'] += 1
            stats['ingredients'] += modified
    if stats['ingredients'] and not dry_run:
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Quantità recuperate: ricette={stats['recipes']}; ingredienti={stats['ingredients']}; modalita={'test' if dry_run else 'salvataggio'}")
    return stats


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--file', type=Path, default=DEFAULT)
    cli.add_argument('--dry-run', action='store_true')
    opts = cli.parse_args()
    process(opts.file, opts.dry_run)
