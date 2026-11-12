"""One media pipeline: source-owned blocks, legacy fallback, conservative merge.

Run --dry-run --report report.json to compare without writing. Existing
verified galleries are retained; unknown extraction never proves absence.
"""
import argparse
import copy
from difflib import SequenceMatcher
import json
import re
import time
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from app.catalog import parse_recipe
from pulisci_procedimenti import clean_steps, candidates
from app.photo_policy import certified_source_absence

CATALOG = Path('data/catalogo.json')
BASE = 'https://ricette.giallozafferano.it'
UA = 'CheffinoPersonalProject/0.1 (weekly recipe discovery; respects robots.txt)'
IMAGE_VERSION = 12


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
    for field in ('data-src', 'data-lazy-src', 'data-original', 'data-lazy', 'src'):
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
        self.picture_image = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and (a.get('property') == 'og:image' or a.get('name') == 'twitter:image'):
            self.og_image = self.og_image or valid_image(a.get('content'), self.base_url)
        if tag == 'source':
            # Le immagini <picture> possono esporre il file solo nel srcset.
            url = image_from_attrs(a, self.base_url)
            if url:
                self.picture_image = url
            return
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



def steps_equivalent(source, stored):
    """Accetta solo cambiamenti editoriali minimi, nello stesso ordine.

    Non ricolloca foto su procedure riscritte o con blocchi fusi/divisi:
    la somiglianza di TUTTI i passaggi deve essere sufficientemente alta.
    """
    cleaned, _ = clean_steps(source)
    if len(cleaned) != len(stored) or not cleaned:
        return False
    for a, b in zip(cleaned, stored):
        left, right = normalize(a), normalize(b)
        if not left or not right:
            return False
        if left == right:
            continue
        if SequenceMatcher(None, left, right, autojunk=False).ratio() < 0.90:
            return False
    return True


def original_steps(html, url, stored):
    try:
        source = parse_recipe(html, url)['steps']
    except (ValueError, TypeError, KeyError):
        return None
    return source if steps_equivalent(source, stored) else None


def associate_numbered(parser, source_steps, count):
    photo = parser.photos
    if not photo or count < 1:
        return []
    keys = sorted(photo)
    if source_steps:
        hits = candidates(source_steps)
        selected = [(idx, n) for idx, _a, _b, n in hits if n in photo]
        numbers = [n for _idx, n in selected]
        # La fonte puo' omettere immagini numerate; non inventiamo le mancanti.
        # Occorre una mappatura crescente, senza duplicati e con copertura
        # significativa per escludere falsi positivi (es. quantita').
        if (len(selected) >= 3 and
                numbers == sorted(set(numbers)) and
                all(0 <= idx < count for idx, _n in selected) and
                len(selected) >= max(3, int(len(photo) * 0.70))):
            blocks = [[] for _ in range(count)]
            for idx, num in selected:
                blocks[idx].append(photo[num])
            if any(blocks):
                return blocks
    # Solo procedimenti con un'immagine per blocco oppure triplette perfette
    # consentono l'abbinamento posizionale.
    if keys == list(range(1, len(keys) + 1)):
        if len(keys) == count:
            return [[photo[i + 1]] for i in range(count)]
        if len(keys) == count * 3:
            return [[photo[j] for j in range(i * 3 + 1, i * 3 + 4)] for i in range(count)]
    return []


def associate_strips(parser, source_steps, count):
    """Abbina soltanto strisce con intervalli numerici certificabili.

    GZ può includere più formati (JPEG/WebP o risoluzioni) di una
    stessa strip: scegliamo un solo URL per intervallo, senza
    richiedere tutte le strisce della procedura.
    """
    strips_by_range = {}
    for start, end, url in sorted(parser.strips, key=lambda x: (x[0],x[1],x[2])):
        if 1 <= start <= end <= 120 and end - start <= 2:
            strips_by_range.setdefault((start, end), url)
    strips = [(a,b,u) for (a,b),u in sorted(strips_by_range.items())]
    if not strips or count < 1:
        return []
    ref_step = {}
    if source_steps:
        hits = candidates(source_steps)
        numbers = [h[3] for h in hits]
        if len(numbers) >= 3 and numbers == sorted(set(numbers)):
            ref_step = {number: step for step, _a, _b, number in hits}
    blocks = [[] for _ in range(count)]
    if ref_step:
        for start, end, url in strips:
            matched = {ref_step.get(n) for n in range(start, end + 1)}
            if None in matched or len(matched) != 1:
                continue
            idx = matched.pop()
            if 0 <= idx < count and not blocks[idx]:
                blocks[idx].append(url)
        if any(blocks):
            return blocks
    # In assenza di riferimenti numerici affidabili, soltanto la
    # copertura continua di un gruppo per ciascun blocco e' sicura.
    if len(strips) != count:
        return []
    next_no = 1
    for idx, (start, end, url) in enumerate(strips):
        if start != next_no:
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
    return SourcePolicies()


class SourcePolicies:
    def __init__(self):
        self.policies = {}

    def can_fetch(self, agent, url):
        host = urlparse(url).hostname
        if host not in ('ricette.giallozafferano.it', 'blog.giallozafferano.it'):
            return False
        if host not in self.policies:
            self.policies[host] = read_robots('https://' + host)
        return self.policies[host].can_fetch(agent, url)


def read_robots(origin):
    req = Request(origin + '/robots.txt', headers={'User-Agent': UA})
    with urlopen(req, timeout=25) as response:
        if urlparse(response.geturl()).hostname != urlparse(origin).hostname:
            raise ValueError('Redirect robots fuori fonte')
        raw = response.read(512001)
    if len(raw) > 512000:
        raise ValueError('robots.txt troppo grande')
    policy = RobotFileParser()
    policy.parse(raw.decode('utf-8-sig', 'replace').splitlines())
    return policy



def fetch_html(url):
    """HTML della fonte con nuovi tentativi sugli errori temporanei (vedi app/rete.py)."""
    from app.rete import fetch_text
    return fetch_text(url)



def missing_photos(rec):
    """Le gallerie parziali vanno ritentate: una foto non completa tutti i passaggi."""
    base = rec.get('url') or BASE
    if not valid_image(rec.get('image_url'), base):
        return True
    groups = rec.get('step_images')
    steps = rec.get('steps') or []
    if not steps or not isinstance(groups, list) or len(groups) != len(steps):
        return True
    return any(not isinstance(group, list) or
               not any(valid_image(photo, base) for photo in group) for group in groups)


def should_recheck(rec, now=None, retry_days=7):
    if rec.get('media_extraction_version', rec.get('images_import_version', 0)) < IMAGE_VERSION:
        return True
    if not missing_photos(rec):
        return False
    checked = rec.get('step_images_checked_at')
    if not checked:
        return True
    try:
        last = datetime.fromisoformat(checked.replace('Z', '+00:00'))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return (now or datetime.now(timezone.utc)) - last >= timedelta(days=retry_days)
    except (ValueError, TypeError, AttributeError):
        return True


def run(catalog_path=CATALOG, limit=25, delay=2.5, fetcher=fetch_html, policy=None, retry_days=7,
        published_only=False, force=False, published_path=Path('data/catalogo_pubblicato.json'),
        dry_run=False, report_path=None, recipe_ids=None):
    path = Path(catalog_path)
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(catalog, list):
        raise ValueError('Il catalogo deve essere una lista')
    if policy is None:
        policy = robots_policy()

    published = None
    if published_only:
        published_file = Path(published_path)
        if not published_file.exists():
            raise ValueError('Catalogo pubblicato assente: non eseguo recupero generico')
        published_data = json.loads(published_file.read_text(encoding='utf-8'))
        if not isinstance(published_data, list):
            raise ValueError('Catalogo pubblicato non valido')
        published = {(r.get('id'), r.get('url')) for r in published_data if isinstance(r, dict)}
        # Non abbandonare le schede sospese: continuano a essere il nostro
        # obiettivo di recupero, senza toccare le altre ricette in revisione.
        review_manifest = Path('data/revisioni_foto_pubblicazione.json')
        if review_manifest.exists():
            review_items = json.loads(review_manifest.read_text(encoding='utf-8'))
            if not isinstance(review_items, list):
                raise ValueError('Manifest revisione foto non valido')
            published.update((r.get('id'),r.get('url')) for r in review_items
                             if isinstance(r,dict) and r.get('id') is not None and r.get('url'))
        # Le schede già approvate dalla validazione ma non ancora pubblicate
        # attendono proprio le foto dei passaggi: senza includerle qui non
        # potrebbero mai entrare nello snapshot (requisito di pubblicazione).
        published.update((r.get('id'), r.get('url')) for r in catalog
                         if isinstance(r, dict) and r.get('needs_review') is False and
                         (r.get('validazione_automatica') or {}).get('approved') is True)

    pending = [r for r in catalog if 'giallozafferano' in str(r.get('source', '')).lower() and
               r.get('url') and r.get('steps') and
               (not certified_source_absence(r) or missing_photos(r) and not valid_image(r.get('image_url'), r.get('url'))) and
               (published is None or (r.get('id'), r.get('url')) in published) and
               (missing_photos(r) if force and published_only else
                should_recheck(r, retry_days=retry_days))]
    # Copertine mancanti prima di gallerie mancanti, poi ricette già pubblicate.
    if recipe_ids is not None:
        wanted = set(recipe_ids)
        # Explicit comparison includes verified records, but remains read-only.
        if not dry_run:
            raise ValueError('--recipe-id richiede --dry-run')
        pending = [r for r in catalog if r.get('id') in wanted and r.get('url') and r.get('steps')
                   and (published is None or (r.get('id'), r.get('url')) in published)]
        if {r['id'] for r in pending} != wanted:
            raise ValueError('ID richiesti assenti dal catalogo selezionato')
    pending.sort(key=lambda r: (bool(valid_image(r.get('image_url'), r.get('url') or BASE)),
                                not missing_photos(r),
                                not bool(r.get('validazione_automatica', {}).get('approved')),
                                not (not r.get('image_url') or not any(r.get('step_images') or [])),
                                str(r.get('name', ''))))

    checked = main_added = step_added = blocked = errors = no_match = 0
    consecutive_transient = 0
    strips_used = numbered_used = steps_filled_total = 0
    report = []
    for rec in pending:
        if checked >= limit:
            break
        url = rec['url']
        if urlparse(url).hostname not in ('ricette.giallozafferano.it', 'blog.giallozafferano.it'):
            continue
        if not policy.can_fetch(UA, url):
            blocked += 1
            continue
        original = copy.deepcopy(rec)
        try:
            html = fetcher(url)
            from app.recipe_media import extract_media
            from app.photo_policy import has_step_gallery
            from controlla_integrita_catalogo import image_id
            media = extract_media(html, url, rec.get('name', ''), rec['steps'])
            main = media['cover']
            if main and not valid_image(rec.get('image_url'), url):
                rec['image_url'] = main
                main_added += 1
            groups, method = media['groups'], media['method']
            # Only fall back after the source recipe identity was established.
            # Numbered legacy mapping is secondary to explicit block ownership.
            if not any(groups) and main and media.get('reason') != 'foreign_image':
                parser = ImagesHTML(rec.get('name', ''), url)
                parser.feed(html)
                raw = original_steps(html, url, rec['steps'])
                groups, method = associate_steps(parser, raw, len(rec['steps'])) if raw is not None else ([], None)
            cover_id = image_id(rec.get('image_url'))
            if cover_id and any(image_id(u) not in (None, cover_id) for group in groups for u in group):
                groups, method = [], None
                media['reason'] = 'foreign_image'
            previous = rec.get('step_images') or []
            had_gallery = has_step_gallery(rec)
            steps_filled = 0
            merged = None
            if groups and len(groups) == len(rec['steps']) and any(groups):
                if not had_gallery:
                    merged = [list(g) for g in groups]
                    steps_filled = sum(bool(g) for g in merged)
                elif (isinstance(previous, list) and len(previous) == len(groups) and
                      rec.get('images_import_version', 0) >= 10 and
                      all(isinstance(g, list) for g in previous)):
                    # Solo i blocchi ancora vuoti: mai sostituire fotografie
                    # esistenti o mescolare la vecchia mappatura pre-v10.
                    merged = [list(g) for g in previous]
                    for index, candidate in enumerate(groups):
                        if not merged[index] and candidate:
                            merged[index] = list(candidate)
                            steps_filled += 1
            if merged is not None and steps_filled:
                rec['step_images'] = merged
                rec.pop('step_photo_source_evidence', None)
                original_blocks = rec.get('step_media_blocks') or []
                rec['step_media_blocks'] = [
                    {'text': text, 'images': group, 'section': (
                        media['blocks'][i].get('section', '')
                        if method == media['method'] and len(media['blocks']) == len(merged)
                        else original_blocks[i].get('section', '')
                        if i < len(original_blocks) and isinstance(original_blocks[i], dict)
                        else '')}
                    for i, (text, group) in enumerate(zip(rec['steps'], merged))]
                rec['images_import_version'] = IMAGE_VERSION
                step_added += 1
                steps_filled_total += steps_filled
            elif not had_gallery:
                no_match += 1
            if method == 'strip':
                strips_used += 1
            elif method == 'numbered':
                numbered_used += 1
            status = ('complete' if groups and all(groups) else
                      'partial' if any(groups) else 'unknown')
            # Absence needs a recognized complete source page and independent
            # negative checks. An HTTP error or unfamiliar template cannot pass.
            if not had_gallery and not any(groups) and main and not media.get('reason') and urlparse(url).hostname == 'ricette.giallozafferano.it':
                from certifica_assenza_foto_fonte import absence_verified, VERSION as PROOF_VERSION
                source_id = image_id(main)
                recognized = 'gz-content-recipe' in html and '</html>' in html.lower()
                if source_id and recognized and absence_verified(html, url, rec['name'], source_id):
                    rec['step_photo_source_evidence'] = {
                        'status': 'verified_absent', 'source_url': url,
                        'recipe_image_id': source_id,
                        'verified_at': datetime.now(timezone.utc).isoformat(),
                        'method': PROOF_VERSION}
                    status = 'verified_absent'
            evidence = {'status': status, 'source_url': url,
                        'source_hash': media['source_hash'], 'method': method,
                        'checked_at': datetime.now(timezone.utc).isoformat(),
                        'existing_preserved': had_gallery,
                        'candidate_differs': had_gallery and groups != previous,
                        'updated': bool(steps_filled),
                        'steps_filled': steps_filled,
                        'effective_status': ('complete' if rec.get('step_images') and
                                             len(rec['step_images']) == len(rec['steps']) and
                                             all(rec['step_images']) else
                                             'partial' if has_step_gallery(rec) else 'unknown'),
                        'reason': media.get('reason')}
            rec['media_extraction'] = evidence
            report.append({'id': rec.get('id'), 'name': rec.get('name'), **evidence})
            if not had_gallery:
                rec['images_import_version'] = IMAGE_VERSION
            rec['media_extraction_version'] = IMAGE_VERSION
            rec['step_images_checked_at'] = datetime.now(timezone.utc).isoformat()
            checked += 1
            if not dry_run:
                temporary = path.with_suffix('.media-tmp')
                temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temporary.replace(path)
        except Exception as exc:
            # Nessuna modifica parziale: la scheda torna esattamente com'era.
            rec.clear()
            rec.update(original)
            checked += 1
            errors += 1
            transient = bool(getattr(exc, 'transient', False))
            consecutive_transient = consecutive_transient + 1 if transient else 0
            report.append({'id': rec.get('id'), 'status': 'fetch_failed', 'error': str(exc),
                           'transient': transient})
            print(f'Errore recupero immagini: {rec.get("name")}: {exc}')
            if consecutive_transient >= 4:
                print('Errori temporanei ripetuti: sito non disponibile o limitazione in corso, arresto prudenziale.', flush=True)
                break
        else:
            consecutive_transient = 0
        if delay:
            time.sleep(delay)

    print(f'Immagini v{IMAGE_VERSION}: controllate={checked}; foto_principali_aggiunte={main_added}; '
          f'ricette_con_foto_passaggi_aggiunte_o_completate={step_added}; blocchi_riempiti={steps_filled_total}; con_strip={strips_used}; '
          f'con_numerate={numbered_used}; senza_abbinamento={no_match}; '
          f'bloccate={blocked}; errori={errors}; rimanenti={max(0, len(pending) - checked)}', flush=True)
    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return main_added, step_added


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--limit', type=int, default=25)
    cli.add_argument('--delay', type=float, default=2.5)
    cli.add_argument('--retry-days', type=int, default=7)
    cli.add_argument('--published-only', action='store_true', help='Controlla solo schede gia pubblicate')
    cli.add_argument('--dry-run', action='store_true', help='Confronta senza modificare il catalogo')
    cli.add_argument('--recipe-id', action='append', type=int, help='ID da confrontare in sola lettura (ripetibile)')
    cli.add_argument('--report', type=Path, help='Report JSON dei risultati e delle differenze')
    cli.add_argument('--force', action='store_true', help='Ritenta immediatamente le schede incomplete pubblicate')
    args = cli.parse_args()
    if args.retry_days < 1: cli.error('--retry-days deve essere >= 1')
    run(limit=args.limit, delay=args.delay, retry_days=args.retry_days,
        published_only=args.published_only, force=args.force, dry_run=args.dry_run, report_path=args.report, recipe_ids=args.recipe_id)

