"""Audit completo delle ricette: completezza, coerenza e (opzionale) confronto con la fonte.

Sola lettura: non modifica mai i cataloghi.

  python audit_ricette.py                      # tutte le schede, controlli offline
  python audit_ricette.py --strict             # exit 1 se una ricetta PUBBLICATA ha errori
  python audit_ricette.py --report audit.json  # report dettagliato
  python audit_ricette.py --online --limit 40  # confronto con la pagina originale
                                               # (rispetta robots.txt, pausa tra richieste)

Gli «errori» rendono una scheda non adatta al piano; gli «avvisi» segnalano
dati mancanti o da controllare a mano (es. valori nutrizionali assenti nella fonte).
"""
import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from app.ingredienti import clean_text, is_resolved
from app.photo_policy import safe_photo
from classifica_catalogo import classify
from controlla_integrita_catalogo import image_id
from pulisci_procedimenti import find_photo_refs

CATALOG = Path('data/catalogo.json')
PUBLISHED = Path('data/catalogo_pubblicato.json')
ENTITY = re.compile(r'&#?\w+;|<\s*/?\s*[a-z][^>]*>', re.I)
PLAN_TYPES = {'Primo', 'Secondo', 'Piatto unico'}


def _number_matches(display, qty, unit):
    numbers = [float(x.replace(',', '.')) for x in re.findall(r'\d+(?:[.,]\d+)?', display)]
    fractions = {'¼': .25, '½': .5, '¾': .75, '⅓': 1 / 3, '⅔': 2 / 3, '⅛': .125}
    numbers += [v for k, v in fractions.items() if k in display]
    numbers += [a + fractions[f] for a, f in re.findall(r'(\d+)\s*([¼½¾⅓⅔⅛])', display)
                for a in [int(a)]]
    factors = (1, 10, 100, 1000)
    return any(abs(n * f - qty) < 1e-6 for n in numbers for f in factors)


def check_record(rec, published=False):
    errors, warnings = [], []
    name = rec.get('name')
    url = rec.get('url') or ''
    if not isinstance(rec.get('id'), int) or not name or not url.startswith('https://'):
        errors.append('dati_base_mancanti')
    if name and ENTITY.search(name):
        errors.append('titolo_con_html')

    display = rec.get('ingredients_display') or []
    ingredients = rec.get('ingredients') or []
    if len(ingredients) < 2:
        errors.append('ingredienti_assenti')
    if len(display) != len(ingredients):
        errors.append(f'ingredienti_disallineati({len(display)}/{len(ingredients)})')
    unresolved = [d for d, i in zip(display, ingredients) if not is_resolved(i)]
    if unresolved:
        errors.append(f'quantita_da_verificare({len(unresolved)})')
    for d, i in zip(display, ingredients):
        if ENTITY.search(str(d)) or (isinstance(i, list) and i and ENTITY.search(str(i[0]))):
            errors.append('ingrediente_con_html')
            break
    for d, i in zip(display, ingredients):
        if is_resolved(i) and i[2] != 'q.b.' and not _number_matches(str(d), i[1], i[2]):
            errors.append('quantita_diversa_dal_testo_fonte')
            break

    steps = rec.get('steps') or []
    if not steps or not all(isinstance(s, str) and s.strip() for s in steps):
        errors.append('procedimento_assente_o_vuoto')
    else:
        if any(ENTITY.search(s) for s in steps):
            errors.append('procedimento_con_html')
        refs = find_photo_refs(steps, rec.get('step_images'))
        if refs:
            errors.append(f'riferimenti_foto_nel_testo({len(refs)})')
        if any(len(s.strip()) < 15 for s in steps):
            warnings.append('passaggio_molto_breve')
        if len(set(steps)) != len(steps):
            warnings.append('passaggi_duplicati')
        last = steps[-1].strip()
        if last and last[-1] not in '.!?…)»”"':
            warnings.append('ultimo_passaggio_senza_punteggiatura')

    servings = rec.get('servings')
    if not isinstance(servings, int) or not 1 <= servings <= 24:
        errors.append('porzioni_mancanti')
    minutes = rec.get('time')
    if not isinstance(minutes, (int, float)) or not 3 <= minutes <= 2880:
        errors.append('tempo_mancante')

    cover = rec.get('image_url')
    if not cover:
        errors.append('copertina_mancante')
    elif not safe_photo(cover):
        warnings.append('copertina_fuori_dominio')
    groups = rec.get('step_images')
    if isinstance(groups, list) and groups:
        if len(groups) != len(steps):
            errors.append('foto_passaggi_non_allineate')
        flat = [u for g in groups if isinstance(g, list) for u in g]
        if len(flat) != len(set(flat)):
            warnings.append('foto_passaggi_duplicate')
        cid = image_id(cover)
        if cid and any(image_id(u) not in (None, cid) for u in flat):
            errors.append('foto_di_altra_ricetta')
        empty = sum(1 for g in groups if not g)
        if empty:
            warnings.append(f'galleria_parziale({empty}/{len(groups)})')

    kcal = rec.get('kcal')
    if kcal is None:
        warnings.append('kcal_assenti')
    elif not 30 <= kcal <= 2500:
        warnings.append(f'kcal_anomale({kcal})')
    for field in ('protein', 'carbs', 'fats'):
        if rec.get(field) is None:
            warnings.append(f'{field}_assenti')
    if all(isinstance(rec.get(f), (int, float)) for f in ('protein', 'carbs', 'fats')) and kcal:
        estimate = 4 * rec['protein'] + 4 * rec['carbs'] + 9 * rec['fats']
        if abs(estimate - kcal) / kcal > 0.35:
            warnings.append('macro_incoerenti_con_kcal')

    if published:
        typ, status, _ = classify(name or '')
        if status == 'escluso' or rec.get('type') not in PLAN_TYPES:
            errors.append(f'tipo_non_adatto_al_piano({rec.get("type")}/{typ})')
    return errors, warnings


def compare_with_source(rec, raw):
    """Differenze tra scheda salvata e pagina originale (raw = app.catalog.parse_recipe)."""
    from importa_foto_passaggi import steps_equivalent
    from ripara_catalogo import parse_servings
    diffs = []
    key = lambda s: re.sub(r'\s+', ' ', clean_text(s)).casefold()
    if key(raw.get('name')) != key(rec.get('name')):
        diffs.append('titolo_diverso')
    source_ing = [key(x) for x in raw.get('ingredients') or []]
    stored_ing = [key(x) for x in rec.get('ingredients_display') or []]
    if source_ing != stored_ing:
        missing = [x for x in source_ing if x not in stored_ing]
        extra = [x for x in stored_ing if x not in source_ing]
        diffs.append({'ingredienti_diversi': {'nella_fonte': missing[:10], 'solo_in_catalogo': extra[:10]}})
    if raw.get('steps') and not steps_equivalent(raw['steps'], rec.get('steps') or []):
        diffs.append(f'procedimento_diverso(fonte={len(raw["steps"])} passaggi, catalogo={len(rec.get("steps") or [])})')
    servings = parse_servings(raw.get('yield_text'))
    if servings and servings != rec.get('servings'):
        diffs.append(f'porzioni_diverse(fonte={servings}, catalogo={rec.get("servings")})')
    if image_id(raw.get('image_url')) and image_id(raw.get('image_url')) != image_id(rec.get('image_url')):
        diffs.append('copertina_diversa')
    return diffs


def audit(catalog=CATALOG, published=PUBLISHED, online=False, limit=30, delay=2.5,
          only_published=False, fetcher=None, policy=None):
    records = json.loads(Path(catalog).read_text(encoding='utf-8'))
    snapshot = json.loads(Path(published).read_text(encoding='utf-8')) if Path(published).exists() else []
    pub_ids = {r.get('id') for r in snapshot}
    targets = snapshot if only_published else records
    counts = Counter()
    rows = []
    ids = Counter(r.get('id') for r in targets)
    urls = Counter(r.get('url') for r in targets)
    for rec in targets:
        is_pub = rec.get('id') in pub_ids
        errors, warnings = check_record(rec, is_pub)
        if ids[rec.get('id')] > 1:
            errors.append('id_duplicato')
        if urls[rec.get('url')] > 1:
            errors.append('url_duplicato')
        for e in errors:
            counts[('errore', re.sub(r'\(.*', '', e), is_pub)] += 1
        for w in warnings:
            counts[('avviso', re.sub(r'\(.*', '', w), is_pub)] += 1
        rows.append({'id': rec.get('id'), 'name': rec.get('name'), 'url': rec.get('url'),
                     'pubblicata': is_pub, 'errori': errors, 'avvisi': warnings})

    if online:
        from app.catalog import fetch_recipe
        from importa_foto_passaggi import SourcePolicies, UA
        policy = policy or SourcePolicies()
        checked = 0
        by_id = {r['id']: r for r in targets}
        for row in sorted(rows, key=lambda r: (not r['pubblicata'], r['id'])):
            if checked >= limit:
                break
            rec = by_id[row['id']]
            if not policy.can_fetch(UA, rec['url']):
                row['fonte'] = 'robots_non_consente'
                continue
            try:
                raw = (fetcher or fetch_recipe)(rec['url'])
                row['fonte'] = compare_with_source(rec, raw) or 'coincide'
            except Exception as exc:
                row['fonte'] = f'non_verificabile: {exc}'
            counts[('fonte', 'coincide' if row['fonte'] == 'coincide' else 'differenze/non_verificabile', row['pubblicata'])] += 1
            checked += 1
            if delay:
                time.sleep(delay)

    pub_err = [r for r in rows if r['pubblicata'] and r['errori']]
    print(f'Audit ricette: schede={len(rows)}; pubblicate={sum(r["pubblicata"] for r in rows)}; '
          f'pubblicate_con_errori={len(pub_err)}; in_revisione_con_errori={sum(1 for r in rows if not r["pubblicata"] and r["errori"])}')
    grouped = defaultdict(dict)
    for (level, code, is_pub), n in sorted(counts.items()):
        grouped[f'{level}:{code}']['pubblicate' if is_pub else 'in_revisione'] = n
    for code, values in grouped.items():
        print(f'  {code}: ' + ', '.join(f'{k}={v}' for k, v in values.items()))
    for r in pub_err[:30]:
        print(f'ERRORE PUBBLICATA: {r["name"]} | id={r["id"]} | {", ".join(r["errori"])}')
    if online:
        for r in rows:
            if r.get('fonte') not in (None, 'coincide'):
                print(f'FONTE: {r["name"]} | id={r["id"]} | {r["fonte"]}')
    return rows


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--catalog', type=Path, default=CATALOG)
    cli.add_argument('--published', type=Path, default=PUBLISHED)
    cli.add_argument('--only-published', action='store_true')
    cli.add_argument('--online', action='store_true', help='Confronta con la pagina originale')
    cli.add_argument('--limit', type=int, default=30)
    cli.add_argument('--delay', type=float, default=2.5)
    cli.add_argument('--report', type=Path)
    cli.add_argument('--strict', action='store_true', help='Exit 1 se una ricetta pubblicata ha errori')
    args = cli.parse_args()
    if args.online and (not 1 <= args.limit <= 400 or args.delay < 1.5):
        cli.error('--limit 1..400 e --delay >= 1.5 in modalità online')
    result = audit(args.catalog, args.published, args.online, args.limit, args.delay, args.only_published)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if args.strict and any(r['pubblicata'] and r['errori'] for r in result):
        sys.exit(1)
