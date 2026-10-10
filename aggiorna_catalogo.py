"""Aggiornamento settimanale, limitato e idempotente, del catalogo Cheffino.

Legge le sitemap dichiarate in robots.txt di GialloZafferano; non tenta di
aggirare blocchi HTTP o restrizioni del sito. Le schede importate sono
contrassegnate needs_review: non entrano nel piano fino a validazione.
"""
import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from urllib.robotparser import RobotFileParser

from app.catalog import fetch_recipe
from app.public_catalog import CATALOG

BASE = 'https://ricette.giallozafferano.it'
SITEMAPS = (BASE + '/sitemap/ricette-new.xml', BASE + '/sitemap/updated.xml')
ROBOT_URL = BASE + '/robots.txt'
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
MAX_XML_BYTES = 12_000_000
MAX_DISCOVERED_URLS = 6000


def fetch_xml(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/xml,text/xml'})
    with urlopen(req, timeout=25) as resp:
        final = resp.geturl()
        if urlparse(final).hostname != 'ricette.giallozafferano.it':
            raise ValueError('Sitemap reindirizzata fuori dal dominio consentito')
        data = resp.read(MAX_XML_BYTES + 1)
    if len(data) > MAX_XML_BYTES:
        raise ValueError('Sitemap troppo grande: arresto prudenziale')
    return ET.fromstring(data)


def xml_items(root, tag):
    # Namespace-independent; works with both sitemapindex and urlset.
    return [el for el in root.iter() if el.tag.rsplit('}', 1)[-1] == tag]


def text_field(el, name):
    for child in el:
        if child.tag.rsplit('}', 1)[-1] == name:
            return (child.text or '').strip()
    return ''


def discover_urls(fetcher=fetch_xml, max_sitemaps=12):
    queue = list(SITEMAPS)
    visited = set()
    found = {}  # url -> lastmod (if available)
    while queue and len(visited) < max_sitemaps and len(found) < MAX_DISCOVERED_URLS:
        url = queue.pop(0)
        if url in visited: continue
        visited.add(url)
        try:
            root = fetcher(url)
        except Exception as exc:
            print(f'Sitemap non disponibile {url}: {exc}')
            continue
        if root.tag.rsplit('}', 1)[-1] == 'sitemapindex':
            for e in xml_items(root, 'sitemap'):
                loc = text_field(e, 'loc')
                if loc.startswith(BASE + '/sitemap/') and loc not in visited:
                    queue.append(loc)
        else:
            for e in xml_items(root, 'url'):
                loc = text_field(e, 'loc').split('#')[0]
                if (loc.startswith(BASE + '/') and
                        urlparse(loc).path.endswith('.html') and '?' not in loc):
                    found[loc] = max(found.get(loc, ''), text_field(e, 'lastmod'))
                    if len(found) >= MAX_DISCOVERED_URLS: break
    # Prefer latest published or modified recipes.
    return [x[0] for x in sorted(found.items(), key=lambda x: (x[1], x[0]), reverse=True)]


def val(v):
    if not isinstance(v, str): return None
    m = re.search(r'(\d+(?:[.,]\d+)?)', v)
    return float(m.group(1).replace(',', '.')) if m else None


def convert(raw):
    url = raw['url']
    return {
        'id': int(hashlib.sha256(url.encode()).hexdigest()[:12], 16) + 10000,
        'name': raw['name'], 'emoji': '🍽️', 'style': 'Da classificare',
        'type': 'Da classificare', 'time': None,
        'ingredients_display': raw['ingredients'],
        'source': 'GialloZafferano', 'url': url,
        'image_url': raw.get('image_url'), 'servings': None,
        'kcal': val(raw.get('nutrition', {}).get('calories')),
        'protein': val(raw.get('nutrition', {}).get('proteinContent')),
        'carbs': val(raw.get('nutrition', {}).get('carbohydrateContent')),
        'fats': val(raw.get('nutrition', {}).get('fatContent')),
        'cost': None,
        'ingredients': [[x, None, 'da fonte'] for x in raw['ingredients']],
        'steps': raw['steps'], 'needs_review': True,
        'imported_at': datetime.now(timezone.utc).isoformat(),
    }


def run(limit=20, delay=2.5, discoverer=discover_urls, fetcher=fetch_recipe,
        catalog_path=CATALOG, robots=None):
    if robots is None:
        robots = RobotFileParser()
        robots.set_url(ROBOT_URL)
        robots.read()
        if not robots.allow_all and not robots.disallow_all and not robots.can_fetch(UA, BASE + '/sitemap/updated.xml'):
            print('Sitemap non consentita dal robots.txt. Nessuna importazione.')
            return 0
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    if not isinstance(catalog, list): raise ValueError('Catalogo JSON non valido')
    known = {r['url'] for r in catalog if r.get('url')}
    candidates = discoverer()
    imported = 0
    failed = 0
    for url in candidates:
        if imported >= limit or failed >= 12: break
        if url in known or not robots.can_fetch(UA, url): continue
        try:
            raw = fetcher(url)
            if len(raw.get('ingredients', [])) < 2 or not raw.get('steps') or not raw.get('name'):
                print(f'Scheda incompleta, saltata: {url}')
                failed += 1
                continue
            catalog.append(convert(raw))
            known.add(url)
            imported += 1
            print(f'Importata (in revisione): {raw["name"]}')
            # Commit state even if a later request fails.
            Path(catalog_path).write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        except Exception as exc:
            failed += 1
            print(f'Importazione non riuscita {url}: {exc}')
        if delay and imported < limit: time.sleep(delay)
    print(f'Nuove ricette: {imported}; fallite/incomplete: {failed}; totale catalogo: {len(catalog)}')
    return imported


class AllowAll:
    def can_fetch(self, _ua, _url): return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--delay', type=float, default=2.5)
    args = p.parse_args()
    if not (1 <= args.limit <= 50): p.error('--limit deve essere tra 1 e 50')
    if args.delay < 2: p.error('--delay deve essere almeno 2 secondi')
    run(args.limit, args.delay)


if __name__ == '__main__':
    main()
