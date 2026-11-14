"""Sincronizza le schede con la pagina originale di GialloZafferano.

Rilegge la fonte e aggiorna, sempre insieme e in modo coerente, i dati che
dipendono dalla fonte: titolo, ingredienti (testo e forma strutturata), porzioni,
tempo, valori nutrizionali, categoria della fonte («Primi piatti»...), costo
indicativo e cottura assente. I passaggi vengono aggiornati solo se non ci sono
foto abbinate o se il numero di passaggi coincide (le foto restano allineate).

Non approva e non pubblica nulla: approvazione e pubblicazione restano a
valida_catalogo.py e pubblica_catalogo.py (workflow 03).

Uso:
  python sincronizza_fonte.py --limit 60                 # schede mai sincronizzate, a lotti
  python sincronizza_fonte.py --ids 26,29 --force        # schede precise, anche se già sincronizzate
  python sincronizza_fonte.py --dry-run --limit 5
"""
import argparse
import copy
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from app.catalog import fetch_recipe, normalize_url
from app.ingredienti import clean_text, parse_ingredient
from classifica_catalogo import classify_record
from normalizza_catalogo import normalize_record
from pulisci_procedimenti import clean_steps
from ripara_catalogo import numeric_nutrition, parse_duration, parse_servings

CATALOG = Path('data/catalogo.json')
PUBLISHED = Path('data/catalogo_pubblicato.json')
SYNC_VERSION = 1
LEGACY_MAX_ID = 1000  # schede storiche dell'app (id 0-31)


def cook_minutes(value):
    """Minuti di cottura dichiarati; 0 se la fonte dichiara esplicitamente nessuna cottura."""
    s = str(value or '')
    if re.fullmatch(r'P(?:0D)?T(?:0H)?(?:0M)?(?:0S)?', s) and s not in ('P', 'PT'):
        return 0
    return parse_duration(s)


def _key(text):
    return re.sub(r'\W+', ' ', clean_text(text).casefold()).strip()


def same_recipe(stored_name, source_name):
    a, b = _key(stored_name), _key(source_name)
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.6 or a in b or b in a


def apply_source(rec, raw, published=False):
    """Restituisce (nuovo record, elenco campi cambiati). Non tocca approvazioni e foto."""
    out = copy.deepcopy(rec)
    changed = []

    def put(key, value):
        if value is not None and out.get(key) != value:
            out[key] = value
            changed.append(key)

    put('source_category', raw.get('category'))
    put('source_cost', raw.get('cost_text'))
    put('source_cook_minutes', cook_minutes(raw.get('cook_time')))

    ingredients = [clean_text(x) for x in raw.get('ingredients') or [] if clean_text(x)]
    servings = parse_servings(raw.get('yield_text'))
    if len(ingredients) >= 2:
        # Ingredienti e porzioni si aggiornano insieme: le dosi valgono per quelle porzioni.
        if ingredients != out.get('ingredients_display') or servings and servings != out.get('servings'):
            put('ingredients_display', ingredients)
            put('ingredients', [parse_ingredient(x) for x in ingredients])
            out.pop('quantita_dedotte', None)
            if servings:
                put('servings', servings)
    elif servings and not out.get('servings'):
        put('servings', servings)

    total = parse_duration(raw.get('total_time')) or (
        (parse_duration(raw.get('prep_time')) or 0) + (parse_duration(raw.get('cook_time')) or 0)) or None
    if total:
        put('time', total)
    nut = raw.get('nutrition') or {}
    for field, key in (('kcal', 'calories'), ('carbs', 'carbohydrateContent'), ('fats', 'fatContent'),
                       ('protein', 'proteinContent')):
        if nut.get(key):
            put(field, numeric_nutrition(nut[key]))

    name = clean_text(raw.get('name'))
    if name and name != out.get('name') and rec.get('id', 10 ** 9) < LEGACY_MAX_ID:
        # Le schede storiche usavano titoli abbreviati; le altre hanno già il titolo della fonte.
        put('name', name)
    if not out.get('image_url') and raw.get('image_url'):
        put('image_url', raw['image_url'])

    source_steps = [s for s in raw.get('steps') or [] if isinstance(s, str) and s.strip()]
    groups = out.get('step_images')
    if source_steps:
        cleaned, _ = clean_steps(list(source_steps), groups if isinstance(groups, list) and len(groups) == len(source_steps) else None)
        if not groups or len(groups) == len(source_steps):
            if cleaned != out.get('steps'):
                put('steps', cleaned)
                put('steps_raw', list(source_steps))
        elif len(source_steps) != len(out.get('steps') or []):
            out['sincronizzazione_note'] = (f'passaggi fonte={len(source_steps)} diversi da quelli con foto='
                                            f'{len(groups)}: testo non aggiornato')
    return out, changed


def select(records, ids=None, force=False, limit=60):
    if ids:
        chosen = [r for r in records if r.get('id') in ids]
        return chosen if force else [r for r in chosen if r.get('source_sync_version') != SYNC_VERSION]

    def priority(r):
        status = classify_record(r)[1]
        legacy = r.get('id', 10 ** 9) < LEGACY_MAX_ID
        in_review = r.get('needs_review') is not False
        return (0 if legacy else 1 if in_review and status != 'escluso' else 2 if not in_review else 3, r.get('id'))
    todo = [r for r in records if r.get('source_sync_version') != SYNC_VERSION
            and str(r.get('url', '')).startswith(('https://ricette.giallozafferano.it/', 'https://blog.giallozafferano.it/'))]
    return sorted(todo, key=priority)[:limit]


def run(catalog_path=CATALOG, limit=60, delay=2.5, ids=None, force=False, dry_run=False,
        fetcher=fetch_recipe, policy=None):
    from importa_foto_passaggi import SourcePolicies, UA
    catalog_path = Path(catalog_path)
    records = json.loads(catalog_path.read_text(encoding='utf-8'))
    policy = policy or SourcePolicies()
    stats = Counter()
    consecutive_transient = 0
    targets = select(records, ids, force, limit)
    by_id = {r['id']: i for i, r in enumerate(records)}
    for rec in targets:
        url = normalize_url(rec['url'])
        if not policy.can_fetch(UA, url):
            stats['robots'] += 1
            continue
        try:
            raw = fetcher(url)
        except Exception as exc:
            stats['errori'] += 1
            transient = bool(getattr(exc, 'transient', False))
            consecutive_transient = consecutive_transient + 1 if transient else 0
            print(f'Fonte non letta: {rec.get("name")}: {exc}')
            if consecutive_transient >= 4:
                print('Errori temporanei ripetuti: arresto prudenziale.')
                break
            continue
        consecutive_transient = 0
        if not same_recipe(rec.get('name'), raw.get('name')):
            stats['titolo_diverso_saltata'] += 1
            print(f'Titolo molto diverso, scheda non toccata: {rec.get("name")} -> {raw.get("name")}')
            continue
        updated, changed = apply_source(rec, raw)
        updated, _ = normalize_record(updated)
        updated['source_sync_version'] = SYNC_VERSION
        updated['source_synced_at'] = datetime.now(timezone.utc).isoformat()
        records[by_id[rec['id']]] = updated
        stats['sincronizzate'] += 1
        if changed:
            stats['modificate'] += 1
            print(f'Aggiornata: {updated.get("name")} | {", ".join(changed)}')
        if not dry_run:
            temporary = catalog_path.with_suffix('.sync-tmp')
            temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            temporary.replace(catalog_path)
        if delay:
            time.sleep(delay)
    remaining = sum(1 for r in records if r.get('source_sync_version') != SYNC_VERSION)
    print('Sincronizzazione fonte: ' + ', '.join(f'{k}={v}' for k, v in sorted(stats.items())) +
          f'; da_sincronizzare={remaining}; modalita={"test" if dry_run else "salvataggio"}')
    return stats


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--catalog', type=Path, default=CATALOG)
    cli.add_argument('--limit', type=int, default=60)
    cli.add_argument('--delay', type=float, default=2.5)
    cli.add_argument('--ids', type=lambda s: {int(x) for x in s.split(',') if x.strip()})
    cli.add_argument('--force', action='store_true')
    cli.add_argument('--dry-run', action='store_true')
    a = cli.parse_args()
    if not 1 <= a.limit <= 450 or a.delay < 1.5:
        cli.error('--limit 1..450 e --delay >= 1.5')
    run(a.catalog, a.limit, a.delay, a.ids, a.force, a.dry_run)
