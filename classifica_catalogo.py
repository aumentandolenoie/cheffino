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

# Regole basate sul titolo: servono per candidare/escludere, non per certificare
# allergeni, sicurezza delle ricette o completezza nutrizionale.
DESSERT = ('torta ', 'tortine', 'tortino dolce', 'biscott', 'crostat', 'muffin',
           'cupcake', 'brownie', 'cheesecake', 'pancake', 'ciambell', 'plumcake',
           'budino', 'tiramis', 'gelato', 'semifredd', 'panna cotta', 'strudel dolce',
           'crema pasticcera', 'dolce ', 'dolcett', 'frollin', 'nutella',
           'marmellata', 'granola', 'porridge', 'cicciopancake', 'cookies', 'waffle', 'crepes dolci',
           'rotolo al tè matcha', 'polvorones', 'zuppa inglese', 'zucchette di halloween',
           'zucchette di pasta sfoglia', 'tortine di zucca', 'cake', 'profiteroles',
           'pumpkin pie', 'popcorn al caramello', 'insalata di frutta')
DRINKS = ('latte ', 'matcha latte', 'golden milk', 'gingerbread latte',
          'pumpkin spice latte', 'cioccolatte', 'frullato', 'smoothie', 'bevanda ')
# Condimenti solo se il titolo INIZIA con il condimento: «Pasta con pesto di...»
# o «Burger ... con maionese» sono piatti, non salse.
CONDIMENTS = ('besciamella', 'salsa ', 'maionese', 'pesto ', 'crema pasticcera', 'ragù ', 'sugo ')
SIDE = ('contorno', 'patate al forno', 'verdure grigliate', 'insalata verde', 'carote arrosto',
        'cavolfiore arrosto', 'patate arrosto', 'zucca arrosto', 'finocchi arrosto', 'purè', 'pure di ')
FIRST = ('pasta ', 'spaghetti', 'fusilli', 'penne ', 'rigatoni', 'risotto',
         'riso alla', 'gnocchi', 'lasagne', 'lasagna', 'ravioli', 'tortelli',
         'tortellini', 'tagliatelle', 'orecchiette', 'carbonara', 'amatriciana',
         'malfatti ', 'casarecce', 'conchiglioni', 'paccheri', 'mezze maniche', 'linguine', 'bucatini', 'trofie', 'cavatelli',
         'busiate', 'cappellacci', 'plin ', 'pizzoccheri', 'agnolotti', 'fettuccine', 'pappardelle',
         'tagliolini', 'strozzapreti', 'cannelloni', 'orzotto', 'farrotto', 'bavette')
SECOND = ('frittata', 'pollo ', 'petto di pollo', 'tacchino ', 'merluzzo',
          'salmone', 'orata ', 'branzino', 'hamburger', 'polpette',
          'scaloppine', 'arrosto', 'bistecca', 'spezzatino', 'omelette',
          'sgombro', 'baccalà', 'pesce spada', 'tonno in padella', 'filetti di ', 'cosce di pollo', 'carrè di maiale', 'arrosto di ', 'polpo ', 'orata al ', 'seppie ', 'calamari ',
          'braciole', 'bocconcini di vitello', 'bocconcini di manzo', 'bocconcini di maiale', 'pulled pork',
          'pulled chicken', 'straccetti di', 'polipetti', 'pomodori ripieni di carne')
ONE_DISH = ('zuppa', 'minestra', 'minestrone', 'vellutata', 'insalatona', 'insalata di riso', 'insalata di pasta', 'insalata d’orzo', "insalata d'orzo", 'insalata di farro',
            'bowl', 'cous cous', 'couscous', 'poke', 'piatto unico',
            'fagioli in umido', 'lenticchie in umido', 'pizza ', 'panino ',
            'quiche', 'torta salata', 'pie salate', 'club sandwich', 'wrap ', 'focaccia farcita')


def classify(name):
    n = re.sub(r'\s+', ' ', str(name).casefold()).strip()
    # Eccezioni salate PRIMA di cercare "torta" nel titolo.
    if any(t in n for t in ('torta salata', 'pie salate', 'quiche')):
        return 'Piatto unico', 'candidato', 'nome: preparazione salata'
    if any(t in n for t in DRINKS):
        return 'Bevanda', 'escluso', 'nome'
    if any(t in n for t in DESSERT):
        return 'Dolce o colazione', 'escluso', 'nome'
    if any(n.startswith(t) or n == t.strip() for t in CONDIMENTS):
        return 'Condimento', 'escluso', 'nome'
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
    inspected = 0
    complete_candidates = []
    incomplete_candidates = []
    for rec in recipes:
        if rec.get('needs_review') is not True:
            stats['preesistenti'] += 1
            continue
        inspected += 1
        typ, status, reason = classify(rec.get('name', ''))
        qa = assess(rec)
        classification = {'tipo_proposto':typ, 'esito':status, 'criterio':reason, **qa}
        if rec.get('classificazione_automatica') != classification:
            rec['classificazione_automatica'] = classification
            changed += 1
        # Invariante di sicurezza: resta in revisione fino a una validazione completa.
        rec['needs_review'] = True
        stats[status] += 1
        if status == 'candidato':
            (complete_candidates if qa['dati_completi'] else incomplete_candidates).append(rec.get('name', ''))
        if not qa['dati_completi']: stats['dati_incompleti'] += 1
    if not dry_run and changed:
        path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Schede esistenti: {stats["preesistenti"]}; esaminate: {inspected}; modificate: {changed}; '
          f'candidate={stats["candidato"]}; escluse={stats["escluso"]}; incerte={stats["incerto"]}; '
          f'con dati incompleti={stats["dati_incompleti"]}')
    print(f'Candidati con dati strutturali completi={len(complete_candidates)}; candidati incompleti={len(incomplete_candidates)}')
    if complete_candidates:
        print('Esempi candidati completi: ' + '; '.join(complete_candidates[:12]))
    if incomplete_candidates:
        print('Esempi candidati da completare: ' + '; '.join(incomplete_candidates[:12]))
    print('ATTENZIONE: dati strutturali completi non equivale a validazione delle restrizioni alimentari.')
    print('Nessuna scheda in revisione viene abilitata automaticamente nel piano.')
    return stats


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--file', type=Path, default=DEFAULT_PATH)
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    process(a.file, a.dry_run)
