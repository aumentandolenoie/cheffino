"""Rimuove i riferimenti numerici alle foto GialloZafferano dai passaggi.

Non modifica ingredienti, dosi, tempi o valori nutrizionali. Funziona su tutte
le schede esistenti in data/catalogo.json e sulle future ricette quando eseguito
nel workflow settimanale. Nessuna richiesta di rete.
"""
import argparse
import json
import re
from pathlib import Path

CATALOG = Path('data/catalogo.json')
# Non confondere le foto con dosi, temperature e tempi di preparazione.
MEASURES = re.compile(
    r'^(?:g|gr|grammi?|kg|mg|ml|cl|dl|l|litri?|minuti?|min|secondi?|sec|ore?|h|'
    r'°c|gradi|spicchi?|cucchiai?|cucchiaini?|fette?|pezzi?|persone|porzioni|'
    r'giorni?|settimane?|cm|mm|%)\b', re.I)
PHOTO = re.compile(r'(?<=\S)\s+([1-9]|[1-3]\d|40)(?=\s*(?:[.,;:!?]|\b))')


def candidates(steps):
    hits = []
    for step_index, step in enumerate(steps):
        if not isinstance(step, str):
            continue
        for m in PHOTO.finditer(step):
            # Non modificare '10 minuti', '4 g', ecc.
            following = step[m.end():].lstrip()
            if MEASURES.match(following):
                continue
            # Evita intervalli tipo 'a 2-3' e numeri decimali.
            preceding = step[:m.start()].rstrip()
            if preceding and preceding[-1] in '-/,.0123456789':
                continue
            if following.startswith(('-', '/', '–')):
                continue
            hits.append((step_index, m.start(), m.end(), int(m.group(1))))
    return hits


def clean_steps(steps):
    if not isinstance(steps, list):
        return steps, 0
    found = candidates(steps)
    # Una sequenza progressiva di almeno tre foto è un segnale affidabile.
    # Non togliere numeri isolati: potrebbero essere istruzioni reali.
    selected = []
    expected = 1
    for hit in found:
        if hit[3] == expected:
            selected.append(hit)
            expected += 1
    if len(selected) < 3:
        return steps, 0
    by_step = {}
    for i, a, b, _ in selected:
        by_step.setdefault(i, []).append((a, b))
    updated = list(steps)
    for i, spans in by_step.items():
        text = updated[i]
        for a, b in reversed(spans):
            text = text[:a] + text[b:]
        # Ripristina la punteggiatura normale lasciando intatti i numeri veri.
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        text = re.sub(r' {2,}', ' ', text)
        updated[i] = text.strip()
    return updated, len(selected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    args = parser.parse_args()
    data = json.loads(args.catalog.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Il catalogo deve essere una lista JSON')
    recipes_changed = references_removed = 0
    for recipe in data:
        if recipe.get('source') != 'GialloZafferano':
            continue
        steps, removed = clean_steps(recipe.get('steps'))
        if removed:
            recipe['steps'] = steps
            recipes_changed += 1
            references_removed += removed
            print(f"Pulita: {recipe.get('name', 'Senza nome')} | riferimenti foto rimossi={removed}")
    if recipes_changed:
        args.catalog.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Pulizia procedimenti: ricette aggiornate={recipes_changed}; riferimenti fotografici rimossi={references_removed}; totale={len(data)}', flush=True)


if __name__ == '__main__':
    main()
