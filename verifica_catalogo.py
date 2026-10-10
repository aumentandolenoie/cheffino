"""Controllo di qualità non distruttivo del catalogo Cheffino.
Non approva né modifica ricette. Usa soltanto la libreria standard.
"""
import csv
import json
from collections import Counter
from pathlib import Path

CATALOG = Path('data/catalogo.json')
REPORT = Path('data/report_qualita_catalogo.csv')


def valid_quantity(ingredient):
    if not isinstance(ingredient, (list, tuple)) or len(ingredient) < 3:
        return False
    name, qty, unit = ingredient[:3]
    if not isinstance(name, str) or not name.strip() or not isinstance(unit, str):
        return False
    unit = unit.strip().lower()
    return (isinstance(qty, (int, float)) and not isinstance(qty, bool) and qty > 0 and unit not in ('da fonte', 'da verificare', '')) or (qty is None and unit == 'q.b.')


def examine(recipe):
    problems = []
    name = recipe.get('name', '(senza nome)')
    classification = recipe.get('classificazione_automatica') or {}
    state = classification.get('esito', 'non classificata')
    if state == 'candidato':
        if not (isinstance(recipe.get('servings'), int) and recipe['servings'] > 0):
            problems.append('porzioni')
        if not (isinstance(recipe.get('time'), (int, float)) and recipe['time'] > 0):
            problems.append('tempo')
        ings = recipe.get('ingredients')
        if not isinstance(ings, list) or len(ings) < 2:
            problems.append('ingredienti_assenti')
        elif any(not valid_quantity(i) for i in ings):
            problems.append('quantita_ambigue')
        if not (isinstance(recipe.get('steps'), list) and any(isinstance(step, str) and step.strip() for step in recipe['steps'])):
            problems.append('procedimento')
        if not recipe.get('image_url'):
            problems.append('immagine')
        # Dati nutrizionali e prezzi non sono requisiti per leggere una ricetta,
        # ma vanno segnalati esplicitamente e mai inventati.
        for fld in ('kcal', 'protein', 'carbs', 'fats'):
            if not isinstance(recipe.get(fld), (int, float)):
                problems.append(fld)
        if recipe.get('cost') is None:
            problems.append('costo')
    return name, state, problems


def main():
    recipes = json.loads(CATALOG.read_text(encoding='utf-8'))
    if not isinstance(recipes, list):
        raise SystemExit('Errore: catalogo.json non contiene un elenco di ricette')
    rows = []
    statuses = Counter()
    issues = Counter()
    structurally_ready = []
    for recipe in recipes:
        name, status, problems = examine(recipe)
        statuses[status] += 1
        if status == 'candidato':
            issues.update(problems)
            blocking = {'porzioni', 'tempo', 'ingredienti_assenti', 'quantita_ambigue', 'procedimento'}
            if not (blocking & set(problems)):
                structurally_ready.append(name)
        rows.append((name, status, ', '.join(problems), 'SI' if recipe.get('needs_review') else 'NO', recipe.get('url', '')))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with REPORT.open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(('ricetta', 'classificazione', 'dati_mancanti_o_ambigui', 'in_revisione', 'url'))
        writer.writerows(rows)
    print(f'Totale ricette: {len(recipes)}')
    print('Classificazioni: ' + ', '.join(f'{k}={v}' for k, v in sorted(statuses.items())))
    print(f'Candidate con porzioni, tempo, quantità e procedimento verificabili automaticamente: {len(structurally_ready)}')
    print('Problemi nelle candidate: ' + (', '.join(f'{k}={v}' for k, v in sorted(issues.items())) or 'nessuno'))
    print('Esempi di candidate ancora problematiche:')
    shown = 0
    for name, status, problems, *_ in rows:
        if status == 'candidato' and problems and shown < 12:
            print(f' - {name}: {problems}')
            shown += 1
    print(f'Report CSV: {REPORT}')
    print('ATTENZIONE: nessuna ricetta è stata approvata. Quantità leggibili non certificano allergeni, dieta, attrezzatura o valori nutrizionali.')


if __name__ == '__main__':
    main()
