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
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from urllib.robotparser import RobotFileParser

from app.catalog import fetch_recipe, build_record, normalize_url
from app.rete import FetchError
from app.public_catalog import CATALOG

BASE = 'https://ricette.giallozafferano.it'
SITEMAPS = (BASE + '/sitemap/ricette-new.xml', BASE + '/sitemap/updated.xml', BASE + '/sitemap/ricette.xml')
ROBOT_URL = BASE + '/robots.txt'
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
MAX_XML_BYTES = 12_000_000
MAX_DISCOVERED_URLS = 6000


def fetch_xml(url, attempts=3):
    """Sitemap XML con nuovi tentativi sugli errori temporanei (429/5xx/rete)."""
    for attempt in range(1, attempts + 1):
        try:
            req = Request(url, headers={'User-Agent': UA, 'Accept': 'application/xml,text/xml'})
            with urlopen(req, timeout=25) as resp:
                final = resp.geturl()
                if urlparse(final).hostname != 'ricette.giallozafferano.it':
                    raise ValueError('Sitemap reindirizzata fuori dal dominio consentito')
                data = resp.read(MAX_XML_BYTES + 1)
            break
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts:
                raise
        except (URLError, TimeoutError, ConnectionError):
            if attempt == attempts:
                raise
        time.sleep(4 * attempt)
    if len(data) > MAX_XML_BYTES:
        raise ValueError('Sitemap troppo grande: arresto prudenziale')
    if data[:2] == b'\x1f\x8b':
        import gzip
        data = gzip.decompress(data)
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
    xml_success = 0
    url_entries = 0
    rejected = 0
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
        xml_success += 1
        root_type = root.tag.rsplit('}', 1)[-1]
        print(f'Sitemap letta: {url} (tipo: {root_type})', flush=True)
        if root_type == 'sitemapindex':
            submaps = [text_field(e, 'loc') for e in xml_items(root, 'sitemap')]
            submaps = [loc for loc in submaps if loc.startswith(BASE + '/sitemap/')]
            # Per sitemap grandi, cicla tra gruppi diversi ogni settimana.
            # Non scarica tutto il sito in una singola esecuzione.
            if len(submaps) > 9:
                from datetime import date
                slots = max(1, len(submaps) - 8)
                offset = ((date.today().isocalendar().week - 1) * 8) % slots
                selected = submaps[offset:offset + 8]
                print(f'Sitemap indice: {len(submaps)} sotto-sitemap; gruppo settimanale {offset + 1}-{offset + len(selected)}', flush=True)
                submaps = selected
            for loc in submaps:
                if loc not in visited and loc not in queue: queue.append(loc)
        else:
            for e in xml_items(root, 'url'):
                url_entries += 1
                loc = text_field(e, 'loc').split('#')[0]
                if (loc.startswith(BASE + '/') and
                        urlparse(loc).path.endswith('.html') and '?' not in loc):
                    found[loc] = max(found.get(loc, ''), text_field(e, 'lastmod'))
                    if len(found) >= MAX_DISCOVERED_URLS: break
                else:
                    rejected += 1
    print(f'Diagnostica sitemap: lette={xml_success}, voci_url={url_entries}, ricette_valide={len(found)}, scartate_per_formato={rejected}', flush=True)
    if not found:
        raise RuntimeError('Nessun URL di ricetta trovato nelle sitemap. Verificare righe Sitemap non disponibile, XML e filtri URL. Nessuna modifica al catalogo.')
    # Prefer latest published or modified recipes.
    return [x[0] for x in sorted(found.items(), key=lambda x: (x[1], x[0]), reverse=True)]


# Diversifica la scoperta fra famiglie di piatti, senza scartare le altre
# ricette (che saranno verificate dal classificatore dopo l'importazione).
DESSERT_SLUG = re.compile(
    r'(torta(?!-salata)|biscott|crostat|muffin|plumcake|gelato|'
    r'frullato|latte-matcha|matcha-latte|cheesecake|pancake|cocktail|'
    r'cioccolata-calda|tiramis|brownie|budino|zuppa-inglese|'
    r'rotolo-al-te|dolce-|granola|gingerbread-latte)', re.I
)


def recipe_family(url):
    slug = urlparse(url).path.rsplit('/', 1)[-1].lower()
    if re.search(r'(pasta-|risotto-|riso-|gnocch|tortell|raviol|lasagn|'
                 r'cannellon|spaghett|penne-|orecchiett|tagliatell)', slug):
        return 'primi'
    if re.search(r'(pollo|tacchin|manzo|vitell|maiale|salmone|sgombro|'
                 r'baccala|merluzzo|orata|branzino|pesce|gamber|tonno|'
                 r'polpett|frittata|omelette|uova-|arrosto)', slug):
        return 'secondi'
    if re.search(r'(zuppa|zuppetta|minestra|vellutata|insalata|bowl|'
                 r'cous-cous|pizza|piadina|panino|quiche|torta-salata|'
                 r'burger|focaccia)', slug):
        return 'unici'
    return 'altri'


def diversify_urls(urls, week=None):
    """Intercala i gruppi: evita l'importazione di sole ricette 'Zuppa'.

    Rota l'ordine settimanalmente, in modo deterministico. I contenuti
    estratti restano soggetti a controlli robots e validazione ordinari.
    """
    from collections import deque
    from datetime import date
    if week is None:
        week = date.today().isocalendar().week
    groups = {k: [] for k in ('primi', 'secondi', 'unici', 'altri')}
    for url in urls:
        slug = urlparse(url).path.rsplit('/', 1)[-1].lower()
        if DESSERT_SLUG.search(slug):
            continue
        groups[recipe_family(url)].append(url)
    # Rotazione serve a non campionare sempre l'inizio di ogni gruppo.
    queues = {}
    for kind, items in groups.items():
        if items:
            shift = (week * 17) % len(items)
            queues[kind] = deque(items[shift:] + items[:shift])
    result = []
    order = ('primi', 'secondi', 'unici', 'altri')
    while any(queues.values()):
        for kind in order:
            if kind in queues and queues[kind]:
                result.append(queues[kind].popleft())
    print('Candidati diversificati: ' + ', '.join(f'{k}={len(v)}' for k,v in groups.items()), flush=True)
    return result


def convert(raw, existing=None):
    """Scheda completa (porzioni, tempi, quantità interpretate) e sempre in revisione."""
    return build_record(raw, existing)


def save_catalog(path, catalog):
    """Scrittura atomica: un'interruzione non lascia mai un JSON troncato."""
    path = Path(path)
    temporary = path.with_suffix('.import-tmp')
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def load_robots():
    """Fetch robots.txt explicitly with our declared user-agent.

    RobotFileParser.read() uses a different default User-Agent and may silently
    convert HTTP errors into a blanket disallow; never treat that as site policy.
    """
    req = Request(ROBOT_URL, headers={
        'User-Agent': UA,
        'Accept': 'text/plain',
    })
    try:
        with urlopen(req, timeout=25) as resp:
            if urlparse(resp.geturl()).hostname != urlparse(ROBOT_URL).hostname:
                raise RuntimeError('robots.txt reindirizzato fuori dal dominio previsto')
            raw = resp.read(512_001)
            if len(raw) > 512_000:
                raise RuntimeError('robots.txt supera il limite di dimensione')
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(
            f'Impossibile verificare robots.txt ({exc}). '
            'Importazione interrotta senza effettuare richieste alle ricette.'
        ) from exc
    parser = RobotFileParser()
    parser.set_url(ROBOT_URL)
    parser.parse(raw.decode('utf-8-sig', errors='replace').splitlines())
    print('robots.txt letto correttamente; controllo delle regole attivo.', flush=True)
    return parser


def run(limit=20, delay=2.5, discoverer=discover_urls, fetcher=fetch_recipe,
        catalog_path=CATALOG, robots=None):
    if robots is None:
        robots = load_robots()
    if not robots.can_fetch(UA, BASE + '/sitemap/updated.xml'):
        raise RuntimeError('La sitemap non è consentita dalle regole robots.txt rilevate. Importazione interrotta.')
    catalog = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    if not isinstance(catalog, list): raise ValueError('Catalogo JSON non valido')
    known = {normalize_url(r['url']) for r in catalog if r.get('url')}
    known_names = {str(r.get('name', '')).casefold().strip() for r in catalog}
    candidates = list(dict.fromkeys(normalize_url(u) for u in diversify_urls(discoverer())))
    print(f'URL candidati: {len(candidates)}; gia presenti nel catalogo: {len(known)}', flush=True)
    imported = 0
    failed = 0
    already = 0
    robots_blocked = 0
    transient = 0
    duplicates = 0
    for url in candidates:
        if imported >= limit or failed >= 12 or transient >= 5:
            break
        if url in known:
            already += 1
            continue
        if not robots.can_fetch(UA, url):
            robots_blocked += 1
            continue
        try:
            raw = fetcher(url)
            raw = dict(raw, url=normalize_url(raw.get('url') or url))
            if len(raw.get('ingredients', [])) < 2 or not raw.get('steps') or not raw.get('name'):
                print(f'Scheda incompleta, saltata: {url}')
                failed += 1
                continue
            if raw['url'] in known or raw['name'].casefold().strip() in known_names:
                # Stessa ricetta raggiunta da un URL diverso (redirect o alias).
                duplicates += 1
                known.add(url)
                continue
            catalog.append(convert(raw))
            known.update({url, raw['url']})
            known_names.add(raw['name'].casefold().strip())
            imported += 1
            print(f'Importata (in revisione): {raw["name"]}')
            # Salvataggio atomico dopo ogni scheda: un errore successivo non perde il lavoro.
            save_catalog(catalog_path, catalog)
        except FetchError as exc:
            if exc.transient:
                transient += 1
                print(f'Errore temporaneo {url}: {exc} (ritentata alla prossima esecuzione)')
            else:
                failed += 1
                print(f'Importazione non riuscita {url}: {exc}')
        except Exception as exc:
            failed += 1
            print(f'Importazione non riuscita {url}: {exc}')
        if delay and imported < limit:
            time.sleep(delay)
    if transient >= 5:
        print('Troppi errori temporanei consecutivi: sito lento o limitazione in corso, arresto prudenziale.', flush=True)
    print(f'Riepilogo filtri: gia_presenti={already}, duplicati={duplicates}, robots_bloccati={robots_blocked}, '
          f'fallite_incomplete={failed}, errori_temporanei={transient}', flush=True)
    print(f'Nuove ricette: {imported}; fallite/incomplete: {failed}; totale catalogo: {len(catalog)}', flush=True)
    if imported == 0 and robots_blocked > 0 and already == 0 and failed == 0:
        raise RuntimeError('Tutte le ricette candidate sono vietate dal robots.txt verificato; nessuna importazione effettuata.')
    if imported == 0 and failed > 0 and transient == 0:
        raise RuntimeError('Nessuna ricetta importata: tutte le estrazioni tentate sono fallite o incomplete. Consultare i log sopra.')
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
