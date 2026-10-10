"""Diagnostica sola lettura delle quantita ambigue in ricette candidate.
Non modifica data/catalogo.json, non scarica contenuti, non valida ricette.
"""
import argparse
import json
from pathlib import Path


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('--file', type=Path, default=Path('data/catalogo.json'))
    cli.add_argument('--limit', type=int, default=20)
    args = cli.parse_args()
    catalog = json.loads(args.file.read_text(encoding='utf-8'))
    if not isinstance(catalog, list):
        raise ValueError('Catalogo: previsto elenco JSON')
    results = []
    for recipe in catalog:
        if (recipe.get('classificazione_automatica') or {}).get('esito') != 'candidato':
            continue
        ingredients = recipe.get('ingredients') or []
        displayed = recipe.get('ingredients_display') or []
        ambiguous = []
        for i, ing in enumerate(ingredients):
            if not isinstance(ing, (list, tuple)) or len(ing) < 3:
                ambiguous.append((i, '(struttura non valida)', ing))
                continue
            qty, unit = ing[1], str(ing[2] or '').strip().lower()
            if (qty is None and unit != 'q.b.') or (qty is not None and unit in ('', 'da fonte', 'da verificare')):
                text = displayed[i] if i < len(displayed) else str(ing[0])
                ambiguous.append((i, text, ing))
        if ambiguous:
            results.append((len(ambiguous), recipe.get('name', 'Senza nome'), ambiguous))
    results.sort(key=lambda r: (r[0], r[1].casefold()))
    print(f'Diagnostica quantita: candidate_con_problemi={len(results)}; priorita_mostrate={min(max(0,args.limit),len(results))}')
    for number, name, items in results[:max(0,args.limit)]:
        print(f'RICETTA: {name} | ingredienti_ambigui={number}')
        for index, original, value in items:
            print(f'  INGREDIENTE [{index+1}]: testo_fonte={original!r} | dato_salvato={value!r}')


if __name__ == '__main__':
    main()
