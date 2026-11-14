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
    'filo': ('fili', 1), 'fili': ('fili', 1), 'mestolo': ('mestoli', 1), 'mestoli': ('mestoli', 1),
    'tazzina': ('tazzine', 1), 'tazzine': ('tazzine', 1), 'manciata': ('manciate', 1), 'manciate': ('manciate', 1),
}
_UNIT_RE = '|'.join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
WITH_UNIT = re.compile(rf'^(?P<name>.+?)\s+(?P<qty>{_NUMBER})\s*(?P<unit>{_UNIT_RE})\.?'
                       rf'(?:\s+da\s+(?:caff[eè]|t[eè]|tavola|cucina))?(?:\s*\((?P<note>[^)]*)\))?$', re.I)
# «Acciughe sott'olio filetti 2»: unità prima del numero.
UNIT_FIRST = re.compile(rf'^(?P<name>.+?)\s+(?P<unit>{_UNIT_RE})\s+(?P<qty>{_NUMBER})$', re.I)
QTY_FIRST = re.compile(rf'^(?P<qty>{_NUMBER})\s*(?P<unit>{_UNIT_RE})?\.?\s+(?P<name>[^\W\d_].*)$', re.I)
# Condimenti elencati senza dose (blog): equivalgono a «q.b.».
BARE_SEASONING = re.compile(r"^(?:olio(?: extra ?vergine)?(?: d['’]oliva| di oliva| evo)?|sale(?: fino| grosso)?|pepe(?: nero)?|"
                            r"peperoncino|origano|basilico|prezzemolo|erba cipollina|timo|rosmarino|salvia)$", re.I)
# «Lattuga qualche foglia», «Timo rametto qualche»: quantità non indicata, come q.b.
SOME = re.compile(rf'^(?P<name>.+?)\s+(?:qualche(?:\s+\w+)?|(?:{_UNIT_RE})\s+qualche|un\s+po[\'’]?)$', re.I)
COUNT_ONLY = re.compile(rf'^(?P<name>.+?)\s+(?P<qty>{_NUMBER})$')
QB = re.compile(r'^(?P<name>.+?)\s*(?:q\.?\s*b\.?|quanto basta|a piacere|qb)$', re.I)
# Derivati: un numero senza unità non è un numero di pezzi.
DERIVED = re.compile(r'\b(?:succo|scorza|polpa|estratto|concentrato|passata|purea|purè|'
                     r'salsa|spremuta|brodo|acqua|latte|(?<!sott[\'’])olio|vino|aceto|farina|zucchero|sale)\b', re.I)
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
    # Formato dei blog: «360 g Pasta», «1 spicchio aglio».
    m = QTY_FIRST.match(s)
    if m and m.group('name').strip():
        qty = parse_quantity(m.group('qty'))
        if qty is not None:
            if m.group('unit'):
                unit, factor = UNITS[m.group('unit').lower()]
                return [m.group('name').strip(' ,;:'), _number(qty * factor), unit]
            if qty < MAX_COUNT and not DERIVED.search(m.group('name')):
                return [m.group('name').strip(' ,;:'), _number(qty), 'pezzi']
    if BARE_SEASONING.match(s):
        return [s, None, 'q.b.']
    m = SOME.match(s)
    if m and m.group('name').strip():
        return [m.group('name').strip(' ,;:'), None, 'q.b.']
    m = UNIT_FIRST.match(s)
    if m and not WITH_UNIT.match(s):
        qty = parse_quantity(m.group('qty'))
        unit, factor = UNITS[m.group('unit').lower()]
        if qty is not None and m.group('name').strip():
            return [m.group('name').strip(' ,;:'), _number(qty * factor), unit]
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


# --- Unità mancanti nella fonte ------------------------------------------------
# GialloZafferano a volte omette l'unità sia nel JSON-LD sia nella pagina
# («Lenticchie secche 250», «Capperi sotto sale 30», «Scorza di limone ½»).
# Due sole deduzioni, sempre registrate in ``quantita_dedotte`` e visibili:
#   1. scorza/succo/buccia con numero <= 3: il numero indica gli agrumi -> pezzi;
#   2. numero senza unità, per un ingrediente che non si conta a pezzi:
#      >= 50 -> grammi (un conteggio sarebbe implausibile); 25-49 -> grammi solo
#      se la ricetta pesa in grammi almeno altri due ingredienti.
DERIVED_PIECE = re.compile(r'\b(?:scorza|succo|buccia|scorzetta)\b', re.I)
NOT_WEIGHED = re.compile(r'\b(?:cubett|fett|fogli|pezz|spicch|bacch|chicch|filett|ciuff|rametti|uova|uovo|tuorl|album|'
                         r'acciug|alic|oliv|gamber|mazzancoll|scamp|cozz|vongol|pomodorin|datterin|ciliegin|'
                         r'noci\b|mandorl|nocciol|pistacch|biscott|savoiard|amarett)', re.I)


def deduce_quantity(text, siblings):
    """Restituisce ([nome, quantità, unità], regola) se la deduzione è sicura, altrimenti None."""
    s = clean_text(text)
    m = COUNT_ONLY.match(s)
    if not m:
        return None
    name = m.group('name').strip(' ,;:')
    qty = parse_quantity(m.group('qty'))
    if not name or qty is None or re.search(r'[\d(]$', name):
        return None
    if DERIVED_PIECE.search(name) and qty <= 3:
        return [name, _number(qty), 'pezzi'], 'agrumi_contati'
    weighed = sum(1 for x in siblings if is_resolved(x) and x[2] in ('g', 'kg'))
    if not NOT_WEIGHED.search(name) and (qty >= 50 or (qty >= 25 and weighed >= 2)):
        return [name, _number(qty), 'g'], ('grammi_dose_non_contabile' if qty >= 50 else 'grammi_come_le_altre_dosi')
    return None
