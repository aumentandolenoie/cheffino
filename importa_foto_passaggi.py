"""Recupera le foto numerate dei passaggi di GialloZafferano.

Usa SOLO URL di foto che compaiono realmente nell'HTML, con alt che
corrisponde al titolo della ricetta seguito da un numero. Non indovina URL.
Associa tre immagini per blocco testuale SOLO quando il conteggio è esatto.
Non modifica steps, approvazioni o restrizioni alimentari.
"""
import argparse
import json
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

CATALOG = Path('data/catalogo.json')
BASE = 'https://ricette.giallozafferano.it'
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'


def normalize(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().casefold()


class PhotoParser(HTMLParser):
    def __init__(self, title, base_url):
        super().__init__(convert_charrefs=True)
        self.title = normalize(title)
        self.base_url = base_url
        self.found = {}

    def handle_starttag(self, tag, attrs):
        if tag != 'img':
            return
        props = dict(attrs)
        alt = normalize(props.get('alt', ''))
        # Per esempio: 'Sgombro in padella - 1'. Non includere immagini
        # principali, consigliate o gallerie prive di numerazione.
        match = re.fullmatch(r'(.+?)\s*[-–]\s*(\d{1,3})', alt)
        if not match or normalize(match.group(1)) != self.title:
            return
        number = int(match.group(2))
        if not 1 <= number <= 90:
            return
        url = None
        for key in ('data-src', 'data-lazy-src', 'data-original', 'src'):
            v = (props.get(key) or '').strip()
            if v and not v.startswith(('data:', 'blob:')):
                url = v
                break
        if not url:
            for key in ('data-srcset', 'srcset'):
                values = (props.get(key) or '').split(',')
                if values:
                    url = values[0].strip().split(' ')[0]
                    break
        if not url:
            return
        url = urljoin(self.base_url, url)
        parsed = urlparse(url)
        # GZ serve foto normalmente da www.giallozafferano.it.
        if parsed.scheme != 'https' or not (parsed.hostname == 'giallozafferano.it' or
            (parsed.hostname or '').endswith('.giallozafferano.it')):
            return
        self.found[number] = url


def get_photo_groups(html, name, url, step_count):
    if step_count < 1:
        return []
    parser = PhotoParser(name, url)
    parser.feed(html)
    numbers = sorted(parser.found)
    if not numbers or numbers != list(range(1, len(numbers) + 1)):
        return []
    # GZ mostra tipicamente 3 immagini numerate per blocco di istruzioni.
    # Se la relazione non è verificabile, non visualizziamo foto abbinate male.
    if len(numbers) == step_count * 3:
        size = 3
    elif len(numbers) == step_count:
        size = 1
    else:
        return []
    return [[parser.found[n] for n in range(i * size + 1, (i + 1) * size + 1)]
            for i in range(step_count)]


def robots_policy():
    req = Request(BASE + '/robots.txt', headers={'User-Agent': UA})
    with urlopen(req, timeout=25) as response:
        raw = response.read(512001)
    if len(raw) > 512000:
        raise ValueError('robots.txt troppo grande')
    policy = RobotFileParser()
    policy.parse(raw.decode('utf-8-sig', 'replace').splitlines())
    return policy


def fetch_html(url):
    req = Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    with urlopen(req, timeout=25) as response:
        final = response.geturl()
        if urlparse(final).hostname != 'ricette.giallozafferano.it':
            raise ValueError('Redirect fuori dal dominio previsto')
        page = response.read(4_000_001)
    if len(page) > 4_000_000:
        raise ValueError('Pagina troppo grande')
    return page.decode('utf-8', 'replace')


def run(catalog_path=CATALOG, limit=12, delay=2.5, fetcher=fetch_html, policy=None):
    data = json.loads(Path(catalog_path).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('Catalogo non valido')
    if policy is None:
        policy = robots_policy()
    checked = associated = no_match = blocked = errors = 0
    # Prima la ricetta di test e le schede gia approvate per il piano.
    ordered = sorted(data, key=lambda r: (
        0 if str(r.get('name', '')).casefold() == 'sgombro in padella' else
        1 if r.get('validazione_automatica', {}).get('approved') else 2))
    for recipe in ordered:
        if checked >= limit:
            break
        if recipe.get('source') != 'GialloZafferano' or not recipe.get('url') or not recipe.get('steps'):
            continue
        if recipe.get('step_images_checked_at'):
            continue
        url = recipe['url']
        if urlparse(url).hostname != 'ricette.giallozafferano.it':
            continue
        if not policy.can_fetch(UA, url):
            blocked += 1
            continue
        try:
            html = fetcher(url)
            groups = get_photo_groups(html, recipe.get('name', ''), url, len(recipe['steps']))
            if groups:
                recipe['step_images'] = groups
                associated += 1
                print(f"Foto associate: {recipe['name']} | {sum(map(len, groups))} immagini / {len(groups)} passaggi", flush=True)
            else:
                no_match += 1
                print(f"Foto non associabili con certezza: {recipe['name']}", flush=True)
            recipe['step_images_checked_at'] = datetime.now(timezone.utc).isoformat()
            checked += 1
            Path(catalog_path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            errors += 1
            checked += 1
            print(f'Errore immagini: {url}: {exc}', flush=True)
        if delay:
            time.sleep(delay)
    print(f'Foto passaggi: controllate={checked}; associate={associated}; non_associabili={no_match}; robots_bloccate={blocked}; errori={errors}; totale={len(data)}', flush=True)
    return associated


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--limit', type=int, default=12)
    cli.add_argument('--delay', type=float, default=2.5)
    opts = cli.parse_args()
    if not 1 <= opts.limit <= 40 or opts.delay < 2:
        cli.error('limit da 1 a 40; delay almeno 2 secondi')
    run(limit=opts.limit, delay=opts.delay)
