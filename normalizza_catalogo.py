"""Normalizzazione offline e idempotente delle schede (nessuna richiesta di rete).

Corregge solo difetti di forma ricavabili dai dati della fonte già salvati:
  1. entità HTML e spazi anomali in titolo, ingredienti e passaggi
     («Cipolle &frac12;» -> «Cipolle ½»);
  2. riferimenti numerici alle foto rimasti nel testo dei passaggi
     («versate l'acqua 12 .»), con la pulizia v2 di pulisci_procedimenti;
  3. ingredienti ancora «da fonte»/«da verificare» interpretati con il parser
     unico app/ingredienti.py, a partire dal testo originale della fonte;
  4. schede storiche con ingredients_display non allineato agli ingredienti
     strutturati: il testo visualizzato viene ricostruito da quelli strutturati.

Non cambia approvazioni, foto, porzioni, tempi o valori nutrizionali.
Applica la stessa trasformazione al catalogo di lavoro e allo snapshot, così
che i passaggi restino identici nei due file (requisito di public_catalog).

Uso:  python normalizza_catalogo.py            # salva
      python normalizza_catalogo.py --dry-run  # solo riepilogo
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from app.ingredienti import clean_text, format_ingredient, is_resolved, parse_ingredient
from pulisci_procedimenti import clean_steps

CATALOG = Path('data/catalogo.json')
PUBLISHED = Path('data/catalogo_pubblicato.json')


def normalize_record(rec, stats=None):
    """Restituisce una copia normalizzata del record e l'elenco delle modifiche."""
    stats = stats if stats is not None else Counter()
    out = dict(rec)
    changes = []

    name = clean_text(rec.get('name'))
    if name and name != rec.get('name'):
        out['name'] = name
        changes.append('titolo')

    display = rec.get('ingredients_display')
    if isinstance(display, list):
        cleaned = [clean_text(x) for x in display]
        if cleaned != display:
            out['ingredients_display'] = cleaned
            stats['ingredienti_testo_ripulito'] += sum(a != b for a, b in zip(cleaned, display))
            changes.append('testo_ingredienti')
        display = cleaned

    ingredients = rec.get('ingredients')
    if isinstance(ingredients, list):
        fixed = []
        for i, item in enumerate(ingredients):
            item = list(item) if isinstance(item, (list, tuple)) else item
            if isinstance(item, list) and len(item) >= 3 and isinstance(item[0], str):
                item[0] = clean_text(item[0])
            source_text = display[i] if isinstance(display, list) and len(display) == len(ingredients) else None
            if not is_resolved(item) and source_text:
                parsed = parse_ingredient(source_text)
                if is_resolved(parsed):
                    item = parsed
                    stats['quantita_interpretate'] += 1
            fixed.append(item)
        if fixed != ingredients:
            out['ingredients'] = fixed
            changes.append('ingredienti')
        ingredients = fixed

    # Schede storiche: elenco visualizzato diverso da quello strutturato.
    if (isinstance(display, list) and isinstance(ingredients, list) and ingredients
            and len(display) != len(ingredients)
            and all(isinstance(x, list) and len(x) >= 3 for x in ingredients)):
        out['ingredients_display'] = [format_ingredient(x) for x in ingredients]
        stats['elenchi_ingredienti_riallineati'] += 1
        changes.append('elenco_ingredienti_riallineato')

    steps = rec.get('steps')
    if isinstance(steps, list):
        text_steps = [clean_text(s) if isinstance(s, str) else s for s in steps]
        text_steps, removed = clean_steps(text_steps, rec.get('step_images'))
        if text_steps != steps:
            out['steps'] = text_steps
            stats['riferimenti_foto_rimossi'] += removed
            changes.append('passaggi')
    if changes:
        stats['schede_modificate'] += 1
    return out, changes


def _write(path, data):
    temporary = path.with_suffix('.norm-tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def run(catalog=CATALOG, published=PUBLISHED, dry_run=False, verbose=False):
    catalog, published = Path(catalog), Path(published)
    records = json.loads(catalog.read_text(encoding='utf-8'))
    if not isinstance(records, list):
        raise ValueError('Catalogo non valido')
    stats = Counter()
    updated = []
    for rec in records:
        new, changes = normalize_record(rec, stats)
        if changes and verbose:
            print(f"Normalizzata: {rec.get('name')} | {', '.join(changes)}")
        updated.append(new)
    snapshot = None
    snap_stats = Counter()
    if published.exists():
        snapshot = json.loads(published.read_text(encoding='utf-8'))
        if not isinstance(snapshot, list):
            raise ValueError('Snapshot non valido')
        snapshot = [normalize_record(rec, snap_stats)[0] for rec in snapshot]
        # I passaggi devono coincidere fra snapshot e catalogo se coincidevano prima.
        by_id = {old.get('id'): (old, new) for old, new in zip(records, updated)}
        original = json.loads(published.read_text(encoding='utf-8'))
        for old_pub, new_pub in zip(original, snapshot):
            pair = by_id.get(old_pub.get('id'))
            if pair and pair[0].get('steps') == old_pub.get('steps') and pair[1].get('steps') != new_pub.get('steps'):
                raise RuntimeError(f"Passaggi divergenti dopo la normalizzazione: {old_pub.get('id')}")
    print('Normalizzazione catalogo: ' + ', '.join(f'{k}={v}' for k, v in sorted(stats.items())) +
          f'; totale={len(records)}; modalita={"test" if dry_run else "salvataggio"}')
    if snapshot is not None:
        print('Normalizzazione snapshot: ' + ', '.join(f'{k}={v}' for k, v in sorted(snap_stats.items())))
    if not dry_run:
        if updated != records:
            _write(catalog, updated)
        if snapshot is not None and snap_stats['schede_modificate']:
            _write(published, snapshot)
    return stats, snap_stats


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--catalog', type=Path, default=CATALOG)
    cli.add_argument('--published', type=Path, default=PUBLISHED)
    cli.add_argument('--dry-run', action='store_true')
    cli.add_argument('--verbose', action='store_true')
    args = cli.parse_args()
    run(args.catalog, args.published, args.dry_run, args.verbose)
