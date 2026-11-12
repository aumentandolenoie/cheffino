"""Interpretazione unica e prudente delle righe ingrediente di GialloZafferano.

GialloZafferano pubblica gli ingredienti come «Nome quantità unità», per esempio
«Spaghetti 320 g», «Aglio 1 spicchio», «Uova medie 3», «Sale fino q.b.».
Questo modulo sostituisce le regole sparse in ripara_catalogo.py e negli script
recupera_quantita_*.py: le stesse regole valgono in importazione e riparazione.

Principi:
- il testo originale resta in ``ingredients_display``; qui si produce solo la
  forma strutturata ``[nome, quantità, unità]``;
- nessuna quantità viene inventata o convertita in grammi se la fonte non la
  indica; un numero senza unità è un conteggio solo se plausibile (< 20) e
  l'ingrediente non è un derivato (succo, scorza, ...);
- ciò che non è interpretabile resta ``da verificare``.
"""
import html
import re

FRACTIONS = {'¼': 0.25, '½': 0.5, '¾': 0.75, '⅓': 1 / 3, '⅔': 2 / 3, '⅛': 0.125}
_NUMBER = r'(?:\d+(?:[.,]\d+)?(?:\s*[¼½¾⅓⅔⅛])?|[¼½¾⅓⅔⅛]|\d+/\d+)'

# unità sorgente -> (unità normalizzata, fattore)
UNITS = {
    'g': ('g', 1), 'gr': ('g', 1), 'gr.': ('g', 1), 'grammo': ('g', 1), 'grammi': ('g', 1),
    'kg': ('kg', 1), 'chilo': ('kg', 1), 'chili': ('kg', 1), 'chilogrammo': ('kg', 1), 'chilogrammi': ('kg', 1),
    'hg': ('g', 100), 'etto': ('g', 100), 'etti': ('g', 100),
    'mg': ('mg', 1),
    'ml': ('ml', 1), 'millilitro': ('ml', 1), 'millilitri': ('ml', 1),
    'cl': ('ml', 10), 'centilitro': ('ml', 10), 'centilitri': ('ml', 10),
    'dl': ('ml', 100), 'decilitro': ('ml', 100), 'decilitri': ('ml', 100),
    'l': ('l', 1), 'lt': ('l', 1), 'litro': ('l', 1), 'litri': ('l', 1),
    'spicchio': ('spicchio', 1), 'spicchi': ('spicchi', 1),
    'cucchiaio': ('cucchiai', 1), 'cucchiai': ('cucchiai', 1),
    'cucchiaino': ('cucchiaini', 1), 'cucchiaini': ('cucchiaini', 1),
    'rametto': ('rametti', 1), 'rametti': ('rametti', 1),
    'foglia': ('foglie', 1), 'foglie': ('foglie', 1),
    'fetta': ('fette', 1), 'fette': ('fette', 1),
    'pizzico': ('pizzichi', 1), 'pizzichi': ('pizzichi', 1),
    'costa': ('coste', 1), 'coste': ('coste', 1),
    'filetto': ('filetti', 1), 'filetti': ('filetti', 1),
    'ciuffo': ('ciuffi', 1), 'ciuffi': ('ciuffi', 1),
    'mazzetto': ('mazzetti', 1), 'mazzetti': ('mazzetti', 1),
    'bicchiere': ('bicchieri', 1), 'bicchieri': ('bicchieri', 1),
    'tazza': ('tazze', 1), 'tazze': ('tazze', 1),
    'bustina': ('bustine', 1), 'bustine': ('bustine', 1),
    'vasetto': ('vasetti', 1), 'vasetti': ('vasetti', 1),
    'rotolo': ('rotoli', 1), 'rotoli': ('rotoli', 1),
    'confezione': ('confezioni', 1), 'confezioni': ('confezioni', 1),
    'scatola': ('scatole', 1), 'scatole': ('scatole', 1),
    'barattolo': ('barattoli', 1), 'barattoli': ('barattoli', 1),
    'goccia': ('gocce', 1), 'gocce': ('gocce', 1),
    'pezzo': ('pezzi', 1), 'pezzi': ('pezzi', 1), 'pz': ('pezzi', 1), 'unità': ('pezzi', 1),
    'cespo': ('cespi', 1), 'cespi': ('cespi', 1),
    'gambo': ('gambi', 1), 'gambi': ('gambi', 1),
    'bacca': ('bacche', 1), 'bacche': ('bacche', 1),
    'stecca': ('stecche', 1), 'stecche': ('stecche', 1),
    'baccello': ('baccelli', 1), 'baccelli': ('baccelli', 1),
    'noce': ('noci', 1),
}
_UNIT_RE = '|'.join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
WITH_UNIT = re.compile(rf'^(?P<name>.+?)\s+(?P<qty>{_NUMBER})\s*(?P<unit>{_UNIT_RE})\.?(?:\s*\((?P<note>[^)]*)\))?$', re.I)
COUNT_ONLY = re.compile(rf'^(?P<name>.+?)\s+(?P<qty>{_NUMBER})$')
QB = re.compile(r'^(?P<name>.+?)\s*(?:q\.?\s*b\.?|quanto basta|a piacere|qb)$', re.I)
# Derivati: un numero senza unità non è un numero di pezzi.
DERIVED = re.compile(r'\b(?:succo|scorza|polpa|estratto|concentrato|passata|purea|purè|'
                     r'salsa|spremuta|brodo|acqua|latte|olio|vino|aceto|farina|zucchero|sale)\b', re.I)
MAX_COUNT = 20
DA_VERIFICARE = 'da verificare'


def clean_text(value):
    """Testo leggibile: entità HTML decodificate, tag rimossi, spazi uniformi."""
    if value is None:
        return ''
    text = str(value)
    for _ in range(2):  # gestisce anche entità doppiamente codificate (&amp;frac12;)
        text = html.unescape(text)
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.I)
    text = re.sub(r'<[^>]{0,200}>', ' ', text)
    text = text.replace(' ', ' ').replace('​', '')
    return re.sub(r'\s+', ' ', text).strip()


def parse_quantity(raw):
    raw = raw.strip().replace(' ', '')
    if raw in FRACTIONS:
        return FRACTIONS[raw]
    if raw and raw[-1] in FRACTIONS and raw[:-1].isdigit():
        return int(raw[:-1]) + FRACTIONS[raw[-1]]
    if re.fullmatch(r'\d+/\d+', raw):
        num, den = map(int, raw.split('/'))
        return num / den if den else None
    try:
        value = float(raw.replace(',', '.'))
    except ValueError:
        return None
    return value if 0 < value <= 100000 else None


def _number(value):
    value = round(value, 3)
    return int(value) if float(value).is_integer() else value


def parse_ingredient(text):
    """Restituisce sempre ``[nome, quantità|None, unità]``.

    unità = 'q.b.' per «quanto basta», 'da verificare' se non interpretabile.
    """
    s = clean_text(text)
    if not s:
        return ['', None, DA_VERIFICARE]
    m = QB.match(s)
    if m and m.group('name').strip():
        return [m.group('name').strip(' ,;:'), None, 'q.b.']
    m = WITH_UNIT.match(s)
    if m:
        name = m.group('name').strip(' ,;:')
        qty = parse_quantity(m.group('qty'))
        unit, factor = UNITS[m.group('unit').lower()]
        if name and qty is not None and not name.endswith(('(', '-')):
            return [name, _number(qty * factor), unit]
    m = COUNT_ONLY.match(s)
    if m:
        name = m.group('name').strip(' ,;:')
        qty = parse_quantity(m.group('qty'))
        # Nome che termina con parentesi aperta o numero: formato composto,
        # es. «Uova (2 medie) 100 g» è già gestito sopra; altri casi restano da verificare.
        if (name and qty is not None and qty < MAX_COUNT and not DERIVED.search(name)
                and not re.search(r'[\d(]$', name)):
            return [name, _number(qty), 'pezzi']
    return [s, None, DA_VERIFICARE]


def is_resolved(ingredient):
    if not isinstance(ingredient, (list, tuple)) or len(ingredient) < 3:
        return False
    name, qty, unit = ingredient[:3]
    if not isinstance(name, str) or not name.strip() or not isinstance(unit, str):
        return False
    if unit == 'q.b.':
        return qty is None
    return (isinstance(qty, (int, float)) and not isinstance(qty, bool) and qty > 0
            and unit not in ('', 'da fonte', DA_VERIFICARE))


def format_ingredient(ingredient):
    """Testo leggibile da una riga strutturata (per schede storiche prive di display)."""
    name, qty, unit = (list(ingredient) + [None, None, None])[:3]
    if unit == 'q.b.' or qty is None:
        return f'{name} q.b.' if unit == 'q.b.' else str(name)
    qty_text = str(qty).replace('.', ',')
    unit_text = '' if unit == 'pezzi' else f' {unit}'
    return f'{name} {qty_text}{unit_text}'
