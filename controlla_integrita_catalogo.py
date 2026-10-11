"""Cheffino: controllo prudente delle immagini dei passaggi (nessuna richiesta web).

Rimuove SOLO link a fotografie attribuibili con certezza a una ricetta diversa,
confrontando il codice ID GialloZafferano nella foto principale e nelle immagini
dei passaggi. Non cancella ricette, non approva schede, non inventa dati.
Usare dopo importa_foto_passaggi.py e prima del commit del catalogo.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

CATALOG = Path('data/catalogo.json')


def image_id(url):
    if not isinstance(url, str):
        return None
    path = urlparse(url).path
    # /images/236-23641/Foo_650x433.jpg (main photo)
    m = re.search(r'/images/(\d+)-(\d+)/', path, re.I)
    if m and int(m.group(1)) == int(m.group(2)) // 100:
        return m.group(2)
    # /images/ricette/236/23641/foo_1.jpg (step images)
    m = re.search(r'/images/ricette/(\d+)/(\d+)(?:/|$)', path, re.I)
    if m and int(m.group(1)) == int(m.group(2)) // 100:
        return m.group(2)
    return None


def scan(catalog):
    issues = []
    for rec in catalog:
        if not isinstance(rec, dict):
            continue
        main_id = image_id(rec.get('image_url'))
        groups = rec.get('step_images')
        if not main_id or not isinstance(groups, list):
            continue
        ids = {image_id(url) for group in groups if isinstance(group, list) for url in group}
        other = sorted(x for x in ids if x and x != main_id)
        if other:
            issues.append((rec, main_id, other))
    return issues


def run(path=CATALOG, apply=False):
    path = Path(path)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(catalog, list):
        raise ValueError('catalogo.json deve contenere una lista')
    issues = scan(catalog)
    for rec, main_id, other in issues:
        print(f"INTEGRITA FOTO: {rec.get('name')} | id_principale={main_id} | id_passaggi_errati={','.join(other)}")
        if apply:
            old = rec.get('step_images') or []
            fixed = []
            for group in old:
                if not isinstance(group, list):
                    fixed.append([])
                    continue
                fixed.append([u for u in group if image_id(u) in (None, main_id)])
            rec['step_images'] = fixed if any(fixed) else []
            # If old raw steps are from another recipe, don't keep them as authoritative.
            rec.pop('steps_raw', None)
            rec.pop('steps_clean', None)
            rec['images_import_version'] = 0  # give importer a chance to recheck
            print(f"  CORRETTA: immagini incompatibili rimosse per '{rec.get('name')}'")
    if apply and issues:
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Integrita catalogo: controllate={len(catalog)}; foto_incongruenti={len(issues)}; corrette={len(issues) if apply else 0}; modalita={"correzione" if apply else "diagnostica"}')
    return len(issues)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--catalog', default=str(CATALOG))
    cli.add_argument('--apply', action='store_true', help='Rimuove soltanto le foto con ID diverso dalla principale')
    args = cli.parse_args()
    run(args.catalog, args.apply)
