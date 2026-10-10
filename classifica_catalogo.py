"""Classificazione prudente del catalogo Cheffino, senza approvazioni automatiche.

Esecuzione: python classifica_catalogo.py
Non modifica mai i campi nutrition, ingredients, servings, needs_review.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

DEFAULT_PATH = Path('data/catalogo.json')

DESSERT = ('torta', 'tortine', 'tortino dolce', 'biscott', 'crostat', 'muffin',
           'cupcake', 'brownie', 'cheesecake', 'pancake dolc', 'ciambell',
           'budino', 'tiramis', 'gelato', 'semifredd', 'panna cotta',
           'crema pasticcera', 'crostata', 'dolcett', 'frollin', 'zucchette di halloween',
           'zucchette di pasta sfoglia', 'nutella', 'marmellata')
FIRST = ('pasta ', 'spaghetti', 'fusilli', 'penne ', 'rigatoni', 'risotto', 'riso alla',
         'gnocchi', 'lasagne', 'lasagna', 'ravioli', 'tortelli', 'tortellini',
         'tagliatelle', 'orecchiette', 'carbonara', 'amatriciana')
SECOND = ('frittata', 'pollo ', 'petto di pollo', 'tacchino ', 'merluzzo', 'salmone',
          'orata ', 'branzino', 'hamburger', 'polpette', 'scaloppine', 'arrosto',
          'bistecca', 'spezzatino', 'omelette', 'sgombro', 'pesce spada', 'tonno in padella')
ONE_DISH = ('zuppa', 'minestrone', 'vellutata', 'insalatona', 'bowl', 'cous cous',
            'couscous', 'poke', 'piatto unico', 'fagioli in umido', 'lenticchie in umido')
SIDE = ('contorno', 'patate al forno', 'verdure grigliate', 'insalata verde')


def classify(name):
    n = re.sub(r'\s+', ' ', str(name).casefold()).strip()
    if any(t in n for t in DESSERT):
        return 'Dolce', 'escluso', 'nome'
    if any(t in n for t in SIDE):
        return 'Contorno', 'escluso', 'nome'
    if any(t in n for t in ONE_DISH):
        return 'Piatto unico', 'candidato', 'nome'
    if any(t in n for t in FIRST):
        return 'Primo', 'candidato', 'nome'
    if any(t in n for t in SECOND):
        return 'Secondo', 'candidato', 'nome'
    return 'Da classificare', 'incerto', 'nessuna regola affidabile'


def assess(record):
    ings = record.get('ingredients')
    steps = record.get('steps')
    servings = record.get('servings')
    amounts = (isinstance(ings, list) and len(ings) >= 2 and
               all(isinstance(x, list) and len(x) >= 3 and isinstance(x[0], str)
                   and x[0].strip() and (isinstance(x[1], (int, float)) and x[1] > 0 or x[2] == 'q.b.')
                   for x in ings))
    portions = isinstance(servings, int) and servings > 0
    instructions = isinstance(steps, list) and len(steps) >= 1
    return {'porzioni_presenti': portions, 'ingredienti_quantificati': bool(amounts),
            'procedimento_presente': instructions,
            'dati_completi': portions and bool(amounts) and instructions}


def process(path, dry_run=False):
    recipes = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(recipes, list): raise ValueError('Il catalogo deve essere una lista JSON')
    stats = Counter()
    changed = 0
    for rec in recipes:
        if rec.get('needs_review') is not True:
            stats['preesistenti'] += 1
            continue
        typ, status, reason = classify(rec.get('name', ''))
        qa = assess(rec)
        classification = {'tipo_proposto':typ, 'esito':status, 'criterio':reason, **qa}
        if rec.get('classificazione_automatica') != classification:
            rec['classificazione_automatica'] = classification
            changed += 1
        # Invariante di sicurezza: resta in revisione fino a una validazione completa.
        rec['needs_review'] = True
        stats[status] += 1
        if not qa['dati_completi']: stats['dati_incompleti'] += 1
    if not dry_run and changed:
        path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Schede esistenti: {stats["preesistenti"]}; classificate: {changed}; '
          f'candidate={stats["candidato"]}; escluse={stats["escluso"]}; incerte={stats["incerto"]}; '
          f'con dati incompleti={stats["dati_incompleti"]}')
    print('Nessuna scheda in revisione viene abilitata automaticamente nel piano.')
    return stats


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--file', type=Path, default=DEFAULT_PATH)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    process(a.file, a.dry_run)
