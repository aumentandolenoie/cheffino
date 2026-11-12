"""Importa una singola ricetta nel catalogo versionato data/catalogo.json.

Usa lo stesso costruttore dell'importazione automatica (app.catalog.build_record):
porzioni, tempi e quantità sono interpretati subito, la scheda resta in revisione.
Eseguire sul PC e fare commit di data/catalogo.json.
"""
import json
import sys

from app.catalog import build_record, fetch_recipe, normalize_url
from app.public_catalog import CATALOG
from aggiorna_catalogo import save_catalog


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("Uso: python importa_ricetta.py https://ricette.giallozafferano.it/...")
        return 2
    try:
        raw = fetch_recipe(argv[0])
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        url = normalize_url(raw['url'])
        current = next((r for r in catalog if normalize_url(r.get('url')) == url), None)
        out = build_record(raw, current)
        if current:
            # Conserva foto e verifiche già acquisite per la stessa scheda.
            for key in ('step_images', 'images_import_version', 'media_extraction',
                        'media_extraction_version', 'step_images_checked_at', 'step_media_blocks',
                        'step_photo_source_evidence'):
                if key in current:
                    out[key] = current[key]
            catalog = [out if normalize_url(r.get('url')) == url else r for r in catalog]
        else:
            catalog.append(out)
        save_catalog(CATALOG, catalog)
        print(f"Importata: {out['name']} — da revisionare prima dell'uso automatico")
        print('File aggiornato: data/catalogo.json (da pubblicare su GitHub).')
        return 0
    except Exception as exc:
        print('Importazione fallita:', exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
