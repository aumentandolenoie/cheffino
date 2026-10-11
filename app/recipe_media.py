"""Extract source-owned procedure blocks; never infer absence from an empty parse.

The HTML adapter only accepts explicit procedure containers. Blog proximity and
filename numbering alone are not evidence. Legacy numbered extraction remains a
fallback in the CLI while existing associations are preserved.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.catalog import JsonLdParser, recipe_nodes, parse_recipe
from app.photo_policy import safe_photo
from controlla_integrita_catalogo import image_id

VERSION = 11


def text_key(value):
    # GZ embeds numbered photo references in its instruction text.
    text = unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))
    return re.sub(r'\s+', ' ', text).strip().casefold()


def image_url(value, base):
    if isinstance(value, dict):
        value = value.get('url') or value.get('contentUrl')
    if not isinstance(value, str) or not value.strip():
        return None
    url = urljoin(base, value.strip())
    return url if safe_photo(url) else None


def urls(value, base):
    items = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(u for item in items if (u := image_url(item, base))))


def attr_image(attrs, base):
    # Prefer explicit lazy source; select the largest declared srcset candidate.
    for key in ('data-src', 'data-lazy-src', 'data-original', 'data-lazy'):
        if result := image_url(attrs.get(key), base):
            return result
    for key in ('data-srcset', 'srcset'):
        choices = []
        for candidate in attrs.get(key, '').split(','):
            parts = candidate.split()
            if parts and (result := image_url(parts[0], base)):
                rank = float(parts[1][:-1]) if len(parts) > 1 and re.fullmatch(r'\d+(?:\.\d+)?[wx]', parts[1]) else 0
                choices.append((rank, result))
        if choices:
            return max(choices)[1]
    return image_url(attrs.get('src'), base)


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def text(self):
        if self.tag in ('script', 'style'):
            return ''
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)


class Document(HTMLParser):
    VOID = {'img', 'source', 'br', 'hr', 'meta', 'link', 'input', 'area', 'base', 'embed', 'param', 'track', 'wbr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('document')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs))
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def is_step(node):
    classes = set(node.attrs.get('class', '').split())
    return (bool(classes & {'gz-content-recipe-step', 'wprm-recipe-instruction'}) or
            node.attrs.get('itemtype', '').rstrip('/').endswith('/HowToStep'))


def node_images(node, base):
    found = []
    def visit(current):
        if current.tag == 'picture':
            # One picture is one asset, even if several encodings are exposed.
            candidates = [attr_image(n.attrs, base) for n in current.walk() if n.tag in ('source', 'img')]
            found.extend(next(([u] for u in candidates if u), []))
            return
        if current.tag == 'img':
            if u := attr_image(current.attrs, base):
                found.append(u)
        for child in current.children:
            if isinstance(child, Node):
                visit(child)
    visit(node)
    return list(dict.fromkeys(found))


def structured_blocks(html, base, title):
    parser = JsonLdParser(); parser.feed(html)
    matches = []
    for script in parser.scripts:
        try:
            obj = json.loads(script)
        except ValueError:
            continue
        for recipe in recipe_nodes(obj):
            if text_key(recipe.get('name')) != text_key(title):
                continue
            blocks = []
            def add(value, section=''):
                if isinstance(value, list):
                    for item in value:
                        add(item, section)
                elif isinstance(value, dict):
                    kind = value.get('@type', [])
                    kind = [kind] if isinstance(kind, str) else kind
                    if any(str(k).endswith('HowToSection') for k in kind):
                        add(value.get('itemListElement', []), value.get('name', section))
                    elif value.get('text') or value.get('name'):
                        blocks.append({'text': value.get('text') or value['name'], 'section': section,
                                       'images': urls(value.get('image') or value.get('thumbnailUrl'), base)})
                elif isinstance(value, str) and value.strip():
                    blocks.append({'text': value, 'section': section, 'images': []})
            add(recipe.get('recipeInstructions', []))
            matches.append(blocks)
    return matches[0] if len(matches) == 1 else []


def extract_media(html, base, title, stored_steps):
    """Return a candidate only; caller controls migration and persistence."""
    result = {'status': 'unknown', 'cover': None, 'groups': [], 'blocks': [],
              'method': None, 'source_hash': hashlib.sha256(html.encode()).hexdigest()}
    try:
        source = parse_recipe(html, base)
    except (ValueError, TypeError, KeyError):
        return result
    if text_key(source['name']) != text_key(title):
        result['reason'] = 'source_identity_changed'
        return result
    result['cover'] = image_url(source.get('image_url'), base)
    blocks = structured_blocks(html, base, source['name'])
    method = 'jsonld-blocks'
    doc = Document(); doc.feed(html)
    if not result['cover']:
        for node in doc.root.walk():
            if node.tag == 'meta' and node.attrs.get('property') == 'og:image':
                result['cover'] = image_url(node.attrs.get('content'), base)
                if result['cover']:
                    break
    dom = []
    for node in doc.root.walk():
        if is_step(node) and not any(is_step(child) for child in list(node.walk())[1:]):
            paragraphs = [n for n in node.walk() if n.tag == 'p']
            dom.append({'text': ' '.join(n.text() for n in paragraphs) if paragraphs else node.text(),
                        'section': '', 'images': node_images(node, base)})
    # DOM associations must correspond one-to-one to source instructions.
    # A different number/order of blocks is ambiguous, not a positional guess.
    if dom and len(dom) == len(blocks) and all(text_key(a['text']) == text_key(b['text']) for a, b in zip(dom, blocks)):
        for a, b in zip(blocks, dom):
            if not a['images']:
                a['images'] = b['images']
        method = 'jsonld-dom-blocks'
    from importa_foto_passaggi import steps_equivalent
    if not blocks or not steps_equivalent([b['text'] for b in blocks], stored_steps):
        result['reason'] = 'procedure_changed_or_unmapped'
        return result
    cover_id = image_id(result['cover'])
    for block in blocks:
        if cover_id and any(image_id(u) not in (None, cover_id) for u in block['images']):
            result['reason'] = 'foreign_image'
            return result
    groups = [b['images'] for b in blocks]
    result.update(groups=groups, blocks=blocks, method=method,
                  status='complete' if all(groups) else 'partial' if any(groups) else 'unknown')
    return result


def display_groups(rec):
    """Compatibility for V5–V7 data, formerly interpreted in browser JS.

    Do not mutate stored evidence. V10+ block associations are authoritative;
    old strip ranges preserve the established display until reverified.
    """
    groups = [[] for _ in rec.get('steps', [])]
    for index, values in enumerate(rec.get('step_images') or []):
        if not isinstance(values, list):
            continue
        for url in values:
            if not safe_photo(url):
                continue
            target = index
            match = re.search(r'(?:^|[_-])strip[_-]?(\d{1,3})-(\d{1,3})\.(?:jpe?g|png|webp)(?:\?|$)', url, re.I)
            if match and (rec.get('images_import_version') or 0) < 10:
                start, end = map(int, match.groups())
                if 1 <= start <= end and end-start <= 2:
                    target = (start-1)//3
            if 0 <= target < len(groups) and url not in groups[target]:
                groups[target].append(url)
    return groups
