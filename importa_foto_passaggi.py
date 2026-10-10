"""Arricchisce il catalogo Cheffino con immagini ORIGINALI indicate dalle pagine GialloZafferano.

- Recupera l'immagine principale da JSON-LD Recipe e, se assente, da og:image.
- Per i passaggi utilizza i riferimenti numerici del procedimento originale,
  associando SOLO foto con alt 'Titolo ricetta - N' e numeri corrispondenti.
- Per ricette senza riferimenti numerici accetta solo corrispondenza esatta 1:1 / 3:1.
- Ritenta schede precedentemente controllate senza immagini; non riscarica quelle complete.
- Non cambia ingredienti, procedimenti, classificazioni o approvazioni.
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
IMAGE_VERSION = 4


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


class ImagesHTML(HTMLParser):
    def __init__(self, name, base_url):
        super().__init__(convert_charrefs=True)
        self.name = normalize(name)
        self.base_url = base_url
        self.photos = {}
        self.og_image = None
        self.image_samples = []
        self.image_tag_count = 0
        self.source_tag_count = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and (a.get('property') == 'og:image' or a.get('name') == 'twitter:image'):
            self.og_image = self.og_image or valid_image(a.get('content'), self.base_url)
        if tag in ('img', 'source'):
            if tag == 'img':
                self.image_tag_count += 1
            else:
                self.source_tag_count += 1
            # A diagnostic sample of the public page, with no downloaded images.
            # Keep only useful strings, with a strict size limit in GitHub logs.
            if len(self.image_samples) < 35:
                src = next((a.get(k) for k in ('data-src', 'data-lazy-src', 'data-original', 'src', 'data-srcset', 'srcset') if a.get(k)), '')
                alt_text = re.sub(r'\s+', ' ', a.get('alt', '') or '').strip()[:110]
                url_hint = (src or '').split('?')[0].split('/')[-1][:105]
                cls = re.sub(r'\s+', ' ', a.get('class', '') or '').strip()[:75]
                if alt_text or url_hint:
                    self.image_samples.append((tag, alt_text, url_hint, cls))
        if tag != 'img':
            return
        alt = normalize(a.get('alt'))
        match = re.fullmatch(r'(.+?)\s*[-–]\s*(\d{1,3})', alt)
        if not match or normalize(match.group(1)) != self.name:
            return
        n = int(match.group(2))
        if not 1 <= n <= 120:
            return
        url = None
        for field in ('data-src', 'data-lazy-src', 'data-original', 'src'):
            url = valid_image(a.get(field), self.base_url)
            if url:
                break
        if not url:
            for field in ('data-srcset', 'srcset'):
                srcset = a.get(field, '') or ''
                for part in srcset.split(','):
                    url = valid_image(part.strip().split()[0] if part.strip() else None, self.base_url)
                    if url:
                        break
                if url:
                    break
        if url:
            self.photos[n] = url


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


def associate_steps(parser, source_steps, count):
    """Use source photo references when available, falling back to exact cardinality."""
    photo = parser.photos
    if not photo or count < 1:
        return []
    keys = sorted(photo)
    if source_steps:
        hits = candidates(source_steps)
        # Only accept an unambiguous sequence 1..N. No picture can be shifted
        # from one text block to another.
        if hits and [h[3] for h in hits] == list(range(1, len(hits)+1)):
            blocks = [[] for _ in range(count)]
            for idx, _a, _b, num in hits:
                if num in photo:
                    blocks[idx].append(photo[num])
            if any(blocks):
                return blocks
    if keys == list(range(1, len(keys)+1)):
        if len(keys) == count:
            return [[photo[i + 1]] for i in range(count)]
        if len(keys) == count * 3:
            return [[photo[j] for j in range(i*3 + 1, i*3 + 4)] for i in range(count)]
    return []


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


def run(catalog_path=CATALOG, limit=12, delay=2.5, fetcher=fetch_html, policy=None):
    path = Path(catalog_path)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(catalog, list):
        raise ValueError('Il catalogo deve essere una lista')
    if policy is None:
        policy = robots_policy()
    # Prioritize approved recipes lacking images, then all others needing a retry.
    def missing(r):
        return not r.get('image_url') or not any(r.get('step_images') or [])
    pending = [r for r in catalog if r.get('source') == 'GialloZafferano' and
               r.get('url') and r.get('steps') and
               (r.get('images_import_version', 0) < IMAGE_VERSION or
                (not r.get('step_images') and not r.get('image_url')))]
    pending.sort(key=lambda r: (not bool(r.get('validazione_automatica', {}).get('approved')),
                                not missing(r), str(r.get('name', ''))))
    checked = main_added = step_added = blocked = errors = no_match = 0
    missing_main_before = 0
    examples_printed = 0
    reasons = {'no_numbered_photos': 0, 'steps_mismatch': 0, 'numbering_mismatch': 0, 'other': 0}
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
            if not rec.get('image_url'):
                missing_main_before += 1
            if main and not rec.get('image_url'):
                rec['image_url'] = main
                main_added += 1
            if not rec.get('step_images'):
                raw = original_steps(html, url, rec['steps'])
                groups = associate_steps(parser, raw, len(rec['steps']))
                if groups:
                    rec['step_images'] = groups
                    if raw:
                        rec['steps_raw'] = raw
                        rec['steps_clean'] = list(rec['steps'])
                    step_added += 1
                    print(f"Foto passaggi associate: {rec['name']} | {sum(map(len, groups))} immagini / {len(groups)} blocchi")
                else:
                    no_match += 1
                    source_present = raw is not None
                    original_count = None
                    try:
                        original_count = len(parse_recipe(html, url)['steps'])
                    except (ValueError, TypeError, KeyError):
                        pass
                    if not parser.photos:
                        reason = 'no_numbered_photos'
                    elif not source_present:
                        reason = 'steps_mismatch'
                    elif sorted(parser.photos) != list(range(1, len(parser.photos) + 1)):
                        reason = 'numbering_mismatch'
                    else:
                        reason = 'other'
                    reasons[reason] += 1
                    print(f"Foto non abbinabili: {rec['name']} | motivo={reason} | foto numerate={len(parser.photos)} | passaggi salvati={len(rec['steps'])} | passaggi fonte={original_count} | immagine_principale={'si' if rec.get('image_url') else 'no'}")
                    if reason == 'no_numbered_photos' and examples_printed < 3:
                        examples_printed += 1
                        print(f"DIAGNOSTICA HTML: {rec['name']} | tag_img={parser.image_tag_count} | tag_source={parser.source_tag_count} | campioni={len(parser.image_samples)}")
                        for tag, alt_text, filename, css in parser.image_samples[:12]:
                            print(f"  FOTO HTML tag={tag} | alt={alt_text!r} | file={filename!r} | classe={css!r}")
            rec['images_import_version'] = IMAGE_VERSION
            rec['step_images_checked_at'] = datetime.now(timezone.utc).isoformat()
            checked += 1
            # Save in increments so a later network failure cannot discard good work.
            path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        except Exception as exc:
            checked += 1
            errors += 1
            print(f'Errore recupero immagini: {rec.get("name")}: {exc}')
        if delay:
            time.sleep(delay)
    print(f'Diagnostica immagini: schede_senza_foto_principale_inizialmente={missing_main_before}; '
          f'motivi_senza_abbinamento={json.dumps(reasons, ensure_ascii=False)}', flush=True)
    print(f'Immagini v3: controllate={checked}; foto_principali_aggiunte={main_added}; '
          f'ricette_con_foto_passaggi_aggiunte={step_added}; senza_abbinamento={no_match}; '
          f'bloccate={blocked}; errori={errors}; rimanenti={max(0,len(pending)-checked)}', flush=True)
    return main_added, step_added


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--limit', type=int, default=12)
    cli.add_argument('--delay', type=float, default=2.5)
    args = cli.parse_args()
    if not 1 <= args.limit <= 40 or args.delay < 2:
        cli.error('limit 1..40; delay >= 2')
    run(limit=args.limit, delay=args.delay)
