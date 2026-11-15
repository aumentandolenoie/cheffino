"""Copertine segnaposto: riconoscimento e sostituzione con la foto del piatto.

Alcune schede GialloZafferano usano come copertina «foto_hd/hd650x433_wm.jpg»,
che per le ricette più vecchie è un'immagine generica con il logo del sito e
non la foto del piatto. Lo script:
  1. scarica la copertina attuale (dimensioni, impronta SHA-256);
  2. la considera segnaposto se la stessa immagine compare come copertina di
     ricette diverse, oppure se coincide con un segnaposto già noto;
  3. legge la pagina della ricetta e raccoglie le alternative dichiarate dalla
     fonte (og:image, JSON-LD image, immagine principale nella pagina);
  4. sceglie la candidata più grande che NON sia un segnaposto e appartenga
     alla stessa ricetta (stesso identificativo nell'URL, se presente).

Sola lettura salvo --apply. Nessuna immagine viene inventata: se la fonte non
offre una foto valida, la copertina viene marcata e l'app mostra la prima foto
dei passaggi al suo posto.

  python controlla_copertine.py --report /tmp/copertine.json
  python controlla_copertine.py --apply
"""
import argparse
import hashlib
import json
import re
import struct
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from app.photo_policy import safe_photo
from app.rete import UA, fetch_text
from controlla_integrita_catalogo import image_id

CATALOG = Path('data/catalogo.json')
PUBLISHED = Path('data/catalogo_pubblicato.json')
KNOWN_PLACEHOLDERS = Path('data/copertine_segnaposto.json')
MAX_IMAGE = 4_000_000


def image_size(data):
    """(larghezza, altezza) per JPEG/PNG/WEBP, None se non riconosciuto."""
    if data[:8] == b'\x89PNG\r\n\x1a\n' and len(data) >= 24:
        return struct.unpack('>II', data[16:24])
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        chunk = data[12:16]
        if chunk == b'VP8X' and len(data) >= 30:
            return 1 + int.from_bytes(data[24:27], 'little'), 1 + int.from_bytes(data[27:30], 'little')
        if chunk == b'VP8 ' and len(data) >= 30:
            w, h = struct.unpack('<HH', data[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if chunk == b'VP8L' and len(data) >= 25:
            b = data[21:25]
            return 1 + (((b[1] & 0x3F) << 8) | b[0]), 1 + (((b[3] & 0xF) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
    if data[:2] == b'\xff\xd8':
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack('>HH', data[i + 5:i + 9])
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack('>H', data[i + 2:i + 4])[0]
            i += 2 + length
    return None


def fetch_image(url, opener=urlopen):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'image/*'})
    with opener(req, timeout=20) as resp:
        if not safe_photo(resp.geturl()):
            raise ValueError('redirect non ammesso')
        data = resp.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise ValueError('immagine troppo grande')
    size = image_size(data)
    if not size:
        raise ValueError('formato immagine non riconosciuto')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'width': size[0], 'height': size[1], 'bytes': len(data)}


def page_candidates(html, page_url):
    """URL di immagini principali dichiarate dalla pagina, in ordine di affidabilità."""
    found = []
    for pattern in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                    r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)',
                    r'"image"\s*:\s*\[?\s*(?:\{[^}]*?"url"\s*:\s*)?"([^"]+\.(?:jpe?g|png|webp)[^"]*)"',
                    r'<img[^>]+class=["\'][^"\']*(?:gz-featured-image|gz-recipe-image|featured)[^"\']*["\'][^>]+(?:data-src|src)=["\']([^"\']+)',
                    r'<picture[^>]*>.*?<img[^>]+(?:data-src|src)=["\']([^"\']+)'):
        for m in re.finditer(pattern, html, re.I | re.S):
            url = urljoin(page_url, m.group(1).replace('\\/', '/').strip())
            if safe_photo(url) and url not in found:
                found.append(url)
    return found


def load_known():
    try:
        return set(json.loads(KNOWN_PLACEHOLDERS.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return set()


def scan(records, limit=400, delay=1.0, fetch_page=fetch_text, fetch_img=fetch_image, sleep=time.sleep):
    covers = {}
    for rec in records[:limit]:
        url = rec.get('image_url')
        if not url:
            continue
        try:
            covers[rec['id']] = dict(fetch_img(url), url=url)
        except Exception as exc:
            covers[rec['id']] = {'url': url, 'error': str(exc)}
        if delay:
            sleep(delay / 3)
    by_hash = defaultdict(set)
    for rid, info in covers.items():
        if info.get('sha256'):
            by_hash[info['sha256']].add(rid)
    known = load_known()
    placeholders = {h for h, ids in by_hash.items() if len(ids) >= 2} | known
    results = []
    for rec in records[:limit]:
        info = covers.get(rec['id'])
        if not info:
            continue
        row = {'id': rec['id'], 'name': rec.get('name'), 'url': rec.get('url'), 'copertina': info}
        if info.get('sha256') not in placeholders:
            row['esito'] = 'ok'
            results.append(row)
            continue
        row['esito'] = 'segnaposto'
        try:
            html = fetch_page(rec['url'])
            candidates = [u for u in page_candidates(html, rec['url']) if u != info['url']]
        except Exception as exc:
            row['errore_pagina'] = str(exc)
            candidates = []
        rid = image_id(info['url'])
        best = None
        tried = []
        for cand in candidates[:6]:
            try:
                meta = fetch_img(cand)
            except Exception as exc:
                tried.append({'url': cand, 'errore': str(exc)})
                continue
            meta['url'] = cand
            tried.append(meta)
            if meta['sha256'] in placeholders or meta['width'] < 300:
                continue
            if rid and image_id(cand) not in (None, rid):
                continue  # foto di un'altra ricetta
            if not best or meta['width'] * meta['height'] > best['width'] * best['height']:
                best = meta
        row['candidate'] = tried
        if best:
            row['esito'] = 'sostituibile'
            row['nuova_copertina'] = best
        results.append(row)
        if delay:
            sleep(delay)
    return results, placeholders


def apply(results, placeholders, paths=(CATALOG, PUBLISHED)):
    replace = {r['id']: r for r in results if r['esito'] == 'sostituibile'}
    unresolved = {r['id'] for r in results if r['esito'] == 'segnaposto'}
    now = datetime.now(timezone.utc).isoformat()
    changed = 0
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        for rec in data:
            row = replace.get(rec.get('id'))
            if row and rec.get('image_url') == row['copertina']['url']:
                rec['image_url'] = row['nuova_copertina']['url']
                rec['copertina_verifica'] = {'esito': 'sostituita', 'precedente': row['copertina']['url'],
                                             'motivo': 'segnaposto_con_logo', 'verificata_il': now}
                changed += 1
            elif rec.get('id') in unresolved:
                rec['copertina_verifica'] = {'esito': 'segnaposto_senza_alternativa', 'verificata_il': now}
                changed += 1
        temporary = path.with_suffix('.cover-tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(path)
    KNOWN_PLACEHOLDERS.write_text(json.dumps(sorted(placeholders), indent=2) + '\n', encoding='utf-8')
    return changed


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--catalog', type=Path, default=CATALOG)
    cli.add_argument('--limit', type=int, default=400)
    cli.add_argument('--delay', type=float, default=1.5)
    cli.add_argument('--report', type=Path)
    cli.add_argument('--apply', action='store_true')
    a = cli.parse_args()
    records = [r for r in json.loads(a.catalog.read_text(encoding='utf-8'))
               if not r.get('esclusa_dal_piano') and r.get('image_url')]
    results, placeholders = scan(records, a.limit, a.delay)
    counts = defaultdict(int)
    for r in results:
        counts[r['esito']] += 1
    print('Copertine: ' + ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) +
          f'; impronte_segnaposto={len(placeholders)}')
    for r in results:
        if r['esito'] != 'ok':
            c = r['copertina']
            print(f"{r['esito'].upper()}: {r['name']} | {c.get('width')}x{c.get('height')} {c['url']}"
                  + (f" -> {r['nuova_copertina']['width']}x{r['nuova_copertina']['height']} {r['nuova_copertina']['url']}"
                     if r.get('nuova_copertina') else '')
                  + (f" | candidate: {[x.get('url') for x in r.get('candidate', [])]}" if r['esito'] == 'segnaposto' else ''))
    if a.report:
        a.report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if a.apply:
        print(f'Schede aggiornate: {apply(results, placeholders)}')
