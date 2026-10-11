"""Arricchisce il catalogo Cheffino con immagini ORIGINALI indicate dalle pagine GialloZafferano.

Versione 5:
- recupera l'immagine principale da JSON-LD Recipe e, se assente, da og:image.
- continua a supportare foto numerate classiche (alt 'Titolo ricetta - N').
- aggiunge il supporto ai file 'strip_1-3.jpg' / 'strip_4-6.jpg' ecc.,
  frequenti su GialloZafferano, associando la stessa striscia ai passaggi coperti.
  Il frontend evita di mostrarla in duplicato sui passaggi consecutivi.
- ritenta schede precedentemente controllate senza immagini o con versioni precedenti.
- non cambia ingredienti, procedimenti, classificazioni o approvazioni.
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

from app.catalog import parse_recipe
from pulisci_procedimenti import clean_steps, candidates

CATALOG = Path('data/catalogo.json')
BASE = 'https://ricette.giallozafferano.it'
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
IMAGE_VERSION = 7


def normalize(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().casefold()


def valid_image(value, base_url):
    if not isinstance(value, str) or not value.strip() or value.startswith(('data:', 'blob:')):
        return None
    value = urljoin(base_url, value.strip())
    p = urlparse(value)
    host = (p.hostname or '').lower()
    if p.scheme != 'https' or not (host == 'giallozafferano.it' or host.endswith('.giallozafferano.it')):
        return None
    if not re.search(r'\.(?:jpe?g|png|webp)(?:$|\?)', p.path + ('?' + p.query if p.query else ''), re.I):
        return None
    return value


def image_from_attrs(attrs, base_url):
    url = None
    for field in ('data-src', 'data-lazy-src', 'data-original', 'src'):
        url = valid_image(attrs.get(field), base_url)
        if url:
            return url
    for field in ('data-srcset', 'srcset'):
        srcset = attrs.get(field, '') or ''
        for part in srcset.split(','):
            url = valid_image(part.strip().split()[0] if part.strip() else None, base_url)
            if url:
                return url
    return None


class ImagesHTML(HTMLParser):
    def __init__(self, name, base_url):
        super().__init__(convert_charrefs=True)
        self.name = normalize(name)
        self.base_url = base_url
        self.photos = {}          # classic numbered photos: {1:url, 2:url, ...}
        self.strips = []          # grouped strip images: [(start,end,url), ...]
        self.og_image = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and (a.get('property') == 'og:image' or a.get('name') == 'twitter:image'):
            self.og_image = self.og_image or valid_image(a.get('content'), self.base_url)
        if tag != 'img':
            return
        url = image_from_attrs(a, self.base_url)
        if not url:
            return
        alt = normalize(a.get('alt'))
        filename = urlparse(url).path.rsplit('/', 1)[-1]

        # Standard numbered photos, eg alt "Ricetta - 3"
        match = re.fullmatch(r'(.+?)\s*[-–]\s*(\d{1,3})', alt)
        if match and normalize(match.group(1)) == self.name:
            n = int(match.group(2))
            if 1 <= n <= 120:
                self.photos[n] = url
                return

        # Support GialloZafferano strip images, eg "..._strip_1-3.jpg"
        # They usually keep alt equal to the recipe title, without the number.
        if alt == self.name:
            m = re.search(r'(?:^|[_-])strip[_-]?(\d{1,3})-(\d{1,3})(?:\.[a-z0-9]+)?$', filename, re.I)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                if 1 <= start <= end <= 120:
                    self.strips.append((start, end, url))
                    return



def original_steps(html, url, stored):
    try:
        source = parse_recipe(html, url)['steps']
    except (ValueError, TypeError, KeyError):
        return None
    cleaned, _ = clean_steps(source)
    if len(cleaned) != len(stored):
        return None
    if all(normalize(a) == normalize(b) for a, b in zip(cleaned, stored)):
        return source
    return None



def associate_numbered(parser, source_steps, count):
    photo = parser.photos
    if not photo or count < 1:
        return []
    keys = sorted(photo)
    if source_steps:
        hits = candidates(source_steps)
        if hits and [h[3] for h in hits] == list(range(1, len(hits) + 1)):
            blocks = [[] for _ in range(count)]
            for idx, _a, _b, num in hits:
                if num in photo:
                    blocks[idx].append(photo[num])
            if any(blocks):
                return blocks
    if keys == list(range(1, len(keys) + 1)):
        if len(keys) == count:
            return [[photo[i + 1]] for i in range(count)]
        if len(keys) == count * 3:
            return [[photo[j] for j in range(i * 3 + 1, i * 3 + 4)] for i in range(count)]
    return []



def associate_strips(parser, source_steps, count):
    """Ogni strip 1-3 e' un'immagine composta che appartiene a UN blocco di testo.

    Se esistono numeri nel testo, accertiamo che i tre riferimenti appartengano
    tutti allo stesso blocco. In alternativa richiediamo che le strip siano
    complete e ordinate: una per blocco, senza buchi o sovrapposizioni.
    """
    strips = sorted(set(parser.strips), key=lambda x: (x[0], x[1], x[2]))
    if not strips or count < 1:
        return []
    ref_step = {}
    if source_steps:
        hits = candidates(source_steps)
        numbers = [h[3] for h in hits]
        if numbers == list(range(1, len(numbers) + 1)):
            ref_step = {number: step for step, _a, _b, number in hits}
    blocks = [[] for _ in range(count)]
    if ref_step:
        for start, end, url in strips:
            matched = {ref_step.get(n) for n in range(start, end + 1)}
            if None in matched or len(matched) != 1:
                return []
            idx = matched.pop()
            if not 0 <= idx < count or blocks[idx]:
                return []
            blocks[idx].append(url)
        return blocks if any(blocks) else []
    if len(strips) != count:
        return []
    next_no = 1
    for idx, (start, end, url) in enumerate(strips):
        if start != next_no or end < start or end - start > 2:
            return []
        blocks[idx].append(url)
        next_no = end + 1
    return blocks


def associate_steps(parser, source_steps, count):
    groups = associate_numbered(parser, source_steps, count)
    if groups:
        return groups, 'numbered'
    groups = associate_strips(parser, source_steps, count)
    if groups:
        return groups, 'strip'
    return [], None



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
        if urlparse(response.geturl()).hostname != 'ricette.giallozafferano.it':
            raise ValueError('Redirect fuori dal dominio previsto')
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise ValueError('Pagina troppo grande')
    return body.decode('utf-8', 'replace')



def run(catalog_path=CATALOG, limit=25, delay=2.5, fetcher=fetch_html, policy=None):
    path = Path(catalog_path)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(catalog, list):
        raise ValueError('Il catalogo deve essere una lista')
    if policy is None:
        policy = robots_policy()

    pending = [r for r in catalog if r.get('source') == 'GialloZafferano' and
               r.get('url') and r.get('steps') and
               (r.get('images_import_version', 0) < IMAGE_VERSION or
                (not r.get('step_images') and not r.get('image_url')))]
    pending.sort(key=lambda r: (not bool(r.get('validazione_automatica', {}).get('approved')),
                                not (not r.get('image_url') or not any(r.get('step_images') or [])),
                                str(r.get('name', ''))))

    checked = main_added = step_added = blocked = errors = no_match = 0
    strips_used = numbered_used = 0
    for rec in pending:
        if checked >= limit:
            break
        url = rec['url']
        if urlparse(url).hostname != 'ricette.giallozafferano.it':
            continue
        if not policy.can_fetch(UA, url):
            blocked += 1
            continue
        try:
            html = fetcher(url)
            parser = ImagesHTML(rec.get('name', ''), url)
            parser.feed(html)
            main = None
            try:
                main = valid_image(parse_recipe(html, url).get('image_url'), url)
            except ValueError:
                pass
            main = main or parser.og_image
            if main and not rec.get('image_url'):
                rec['image_url'] = main
                main_added += 1

            if not rec.get('step_images') or any(re.search(r'[_-]strip[_-]?\d{1,3}-\d{1,3}\.', u, re.I) for group in (rec.get('step_images') or []) if isinstance(group, list) for u in group if isinstance(u, str)):
                raw = original_steps(html, url, rec['steps'])
                groups, method = associate_steps(parser, raw, len(rec['steps']))
                if groups:
                    # Guard against cross-recipe association: a GZ recipe photo ID,
                    # when present, must equal the ID of the recipe's cover photo.
                    from controlla_integrita_catalogo import image_id
                    cover_id = image_id(rec.get('image_url') or main)
                    foreign_ids = {image_id(u) for group in groups for u in group}
                    foreign_ids.discard(None)
                    if cover_id and any(v != cover_id for v in foreign_ids):
                        print(f"Foto sospette scartate: {rec['name']} | id_copertina={cover_id} | id_passaggi={sorted(foreign_ids)}")
                        groups = []
                if groups:
                    rec['step_images'] = groups
                    if raw:
                        rec['steps_raw'] = raw
                        rec['steps_clean'] = list(rec['steps'])
                    step_added += 1
                    if method == 'strip':
                        strips_used += 1
                    elif method == 'numbered':
                        numbered_used += 1
                    print(f"Foto passaggi associate ({method}): {rec['name']} | {sum(map(len, groups))} immagini / {len(groups)} blocchi")
                else:
                    no_match += 1
                    reason = 'no_usable_step_photos'
                    numbered = len(parser.photos)
                    strips = len(parser.strips)
                    print(f"Foto non abbinabili: {rec['name']} | motivo={reason} | foto_numerate={numbered} | foto_strip={strips} | passaggi={len(rec['steps'])} | immagine_principale={'si' if rec.get('image_url') else 'no'}")

            rec['images_import_version'] = IMAGE_VERSION
            rec['step_images_checked_at'] = datetime.now(timezone.utc).isoformat()
            checked += 1
            path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            checked += 1
            errors += 1
            print(f'Errore recupero immagini: {rec.get("name")}: {exc}')
        if delay:
            time.sleep(delay)

    print(f'Immagini v5: controllate={checked}; foto_principali_aggiunte={main_added}; '
          f'ricette_con_foto_passaggi_aggiunte={step_added}; con_strip={strips_used}; '
          f'con_numerate={numbered_used}; senza_abbinamento={no_match}; '
          f'bloccate={blocked}; errori={errors}; rimanenti={max(0, len(pending) - checked)}', flush=True)
    return main_added, step_added


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--limit', type=int, default=25)
    cli.add_argument('--delay', type=float, default=2.5)
    args = cli.parse_args()
    run(limit=args.limit, delay=args.delay)
