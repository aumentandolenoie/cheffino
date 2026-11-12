"""Compatibilità delle ricette con le esigenze alimentari scelte nell'onboarding.

Esigenze: Vegetariano, Vegano, Senza Glutine, Senza Lattosio.

Per ogni ricetta e per ogni esigenza l'esito è:
  - "si"       nessun ingrediente in conflitto e nessun ingrediente dubbio;
  - "no"       almeno un ingrediente incompatibile (es. pancetta per Vegetariano);
  - "incerto"  nessun conflitto certo, ma almeno un prodotto la cui composizione
               dipende dalla marca o dalla preparazione (brodo pronto, salumi,
               cioccolato, lievito in polvere...).
Solo "si" entra nel piano: la preferenza dell'utente è sempre rispettata e le
ricette dubbie restano escluse invece di essere proposte come sicure.

Il controllo si basa sugli ingredienti dichiarati dalla fonte; non sostituisce
la lettura delle etichette (contaminazioni, ingredienti nascosti, allergie gravi).
Valutazione al volo nell'API: le regole si applicano subito anche alle ricette nuove.
"""
import re
import unicodedata

DIETS = ('Vegetariano', 'Vegano', 'Senza Glutine', 'Senza Lattosio')
VERSION = 1


def fold(text):
    text = unicodedata.normalize('NFD', str(text or '').casefold())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return ' ' + re.sub(r"[^a-z0-9]+", ' ', text).strip() + ' '


def _rx(*words):
    return re.compile(r'\s(?:' + '|'.join(words) + r')\s')


# Le parole sono confrontate sul testo «piegato» (minuscole, senza accenti,
# punteggiatura -> spazio); i prefissi usano [a-z]* per plurali e varianti.
MEAT = _rx('pollo', 'polli', 'tacchino', 'manzo', 'vitell[a-z]*', 'maial[a-z]*', 'suin[a-z]*', 'agnell[a-z]*',
           'capretto', 'conigli[a-z]*', 'anatra', 'oca', 'faraona', 'cavallo', 'selvaggina', 'cinghiale',
           'salsicc[a-z]*', 'salam[a-z]*', 'prosciutt[a-z]*', 'speck', 'pancetta', 'guanciale', 'bacon', 'bresaola',
           'mortadella', 'wurstel', 'w[uü]rstel', 'coppa', 'nduja', 'lardo', 'strutto', 'carne', 'carni',
           'braciol[a-z]*', 'costin[a-z]*', 'carre', 'biancostato', 'controfiletto',
           'cotechino', 'zampone', 'salame', 'pesteda', 'gelatina', 'colla di pesce',
           'fegat[a-z]*', 'trippa', 'ossobuc[a-z]*', 'cotolett[a-z]*',
           'lonza', 'arista', 'noce di manzo', 'luganega', 'soppressata', 'culatello', 'fiocchetto', 'porchetta')
FISH = _rx('acciug[a-z]*', 'alici', 'alice', 'tonno', 'salmon[a-z]*', 'merluzz[a-z]*', 'baccala', 'stoccafisso',
           'branzin[a-z]*', 'spigol[a-z]*', 'orata', 'orate', 'sgombr[a-z]*', 'sarde', 'sardine', 'sardina', 'triglie', 'triglia',
           'nasello', 'platessa', 'trot[a-z]*', 'pesce', 'pesci', 'ombrina', 'rana pescatrice', 'gamber[a-z]*',
           'mazzancoll[a-z]*', 'scampi', 'canocchi[a-z]*', 'cozz[a-z]*', 'vongol[a-z]*', 'calamari', 'calamaro', 'sepp[a-z]*',
           'seppiolin[a-z]*', 'polpo', 'polpi', 'polipett[a-z]*', 'moscardini', 'bottarga', 'crostace[a-z]*',
           'fumetto', 'colatura', 'worcestershire', 'surimi', 'frutti di mare', 'aragost[a-z]*', 'astice',
           'granchi[a-z]*', 'ostrich[a-z]*', 'capesant[a-z]*', 'cernia', 'dentice', 'rombo', 'sogliol[a-z]*',
           'persico', 'pesce spada', 'halibut', 'uova di salmone', 'uova di lompo', 'uova di trota', 'caviale', 'tarama')
EGGS = _rx('uov[ao]', 'tuorl[a-z]*', 'album[a-z]*', 'maionese', 'all uovo', 'e uova', 'pavesini', 'amaretti',
           'meringh[a-z]*', 'savoiardi', 'zabaione', 'frittata')
DAIRY = _rx('latte', 'latti', 'burro', 'panna', 'yogurt', 'yoghurt', 'skyr', 'kefir', 'ricott[a-z]*', 'mozzarell[a-z]*',
            'fiordilatte', 'fior di latte', 'burrat[a-z]*', 'stracciatella', 'parmigiano', 'grana', 'pecorino',
            'asiago', 'brie', 'caciocavallo', 'caciott[a-z]*', 'caprino', 'casizolu', 'cheddar', 'crescenza', 'edamer',
            'emmental[a-z]*', 'feta', 'fontina', 'formagg[a-z]*', 'gorgonzola', 'mascarpone', 'philadelphia',
            'primosale', 'provol[a-z]*', 'quartirolo', 'robiola', 'roquefort', 'scamorza', 'sottilett[a-z]*',
            'stracchino', 'taleggio', 'toma', 'casera', 'montasio', 'fontal', 'groviera', 'gruyere', 'camembert',
            'halloumi', 'paneer', 'squacquerone', 'besciamella', 'nutella', 'cacio', 'cioccolato al latte',
            'cioccolato bianco', 'cappuccino', 'colomba', 'panettone', 'pandoro', 'ghee', 'caseina', 'siero')
HONEY = _rx('miele')
# Alternative vegetali: neutralizzano le parole sopra quando presenti nello stesso ingrediente.
PLANT_ALT = _rx('di soia', 'di mandorl[a-z]*', 'di riso', 'di avena', 'di cocco', 'vegetal[a-z]*', 'vegan[a-z]*',
                'di arachidi', 'di cacao', 'di anacardi', 'di nocciol[a-z]*', 'senza uova', 'veg', 'tofu', 'di farro')
LACTOSE_FREE = _rx('senza lattosio', 'delattosat[a-z]*', 'zero lattosio')

GLUTEN = _rx('farin[a-z]*', 'semola', 'semolino', 'grano', 'frumento', 'orzo', 'farro', 'segale', 'kamut', 'spelta',
             'bulgur', 'cous cous', 'couscous', 'seitan', 'pasta', 'pane', 'pani', 'panin[a-z]*', 'pancarre',
             'pangrattato', 'panko', 'piadin[a-z]*', 'tortill[a-z]*', 'crostini', 'fette biscottate', 'taralli',
             'tarall[a-z]*', 'baguette', 'focacc[a-z]*', 'puccia', 'filoncin[a-z]*', 'grissin[a-z]*', 'cracker[a-z]*',
             'biscott[a-z]*', 'pavesini', 'savoiardi', 'colomba', 'panettone', 'pandoro', 'birra', 'malto',
             'lievito madre', 'salsa di soia', 'soia chiara', 'crusca', 'gnocch[a-z]*', 'sfoglia', 'fillo',
             'noodles', 'udon', 'ramen', 'wafer', 'pan di spagna', 'brioche', 'croissant', 'friselle', 'tigelle',
             'spaghett[a-z]*', 'spaghettoni', 'bucatini', 'linguine', 'fettuccine', 'tagliatelle', 'tagliolini',
             'pappardelle', 'capellini', 'fusill[a-z]*', 'penne', 'pennette', 'pennoni', 'pennotti', 'rigatoni',
             'mezzi rigatoni', 'mezze maniche', 'paccheri', 'orecchiette', 'farfalle', 'casarecce', 'conchiglioni',
             'ditalini', 'cellentani', 'calamarata', 'mafaldotte', 'busiate', 'strozzapreti', 'pipe', 'trofie',
             'cavatelli', 'lasagn[a-z]*', 'cannelloni', 'tortellini', 'tortelli', 'ravioli', 'cappellacci',
             'agnolotti', 'plin', 'pizzoccheri', 'bavette', 'vermicelli', 'maccheroni', 'pastina', 'dischetti',
             'dischi volanti', 'mini penne', 'mezze penne', 'elicoidali', 'avena')
# Sostituti senza glutine dichiarati o farine naturalmente prive di glutine.
GLUTEN_FREE = _rx('senza glutine', 'gluten free', 'farina di riso', 'farina di mais', 'farina di ceci',
                  'farina di castagne', 'farina di mandorle', 'farina di nocciole', 'farina di tapioca',
                  'farina di cocco', 'farina di lenticchie', 'farina di legumi', 'farina istantanea per polenta',
                  'farina di mais per polenta', 'grano saraceno', 'amido di mais', 'amido di riso', 'lievito di birra',
                  'fecola', 'pasta di ceci', 'pasta di lenticchie', 'chicchi di farina di legumi',
                  'casarecce di ceci', 'pane carasau senza')
# Ingredienti senza glutine come materia prima ma spesso contaminati: dubbi.
GLUTEN_UNSURE = _rx('avena', 'brodo', 'dado', 'salsicc[a-z]*', 'salam[a-z]*', 'wurstel', 'prosciutto cotto',
                    'mortadella', 'nduja', 'ketchup', 'barbecue', 'senape', 'maionese', 'lievito', 'cioccolat[a-z]*',
                    'nutella', 'sottilett[a-z]*', 'formaggio fuso', 'mix di', 'preparato', 'granola', 'cappuccino',
                    'solubile', 'curry', 'chili', 'salsa(?! tabasco)', 'codette', 'decorazione', 'zucchero a velo',
                    'gelato', 'surimi', 'caramell[a-z]*', 'pesto', 'besciamella',
                    'aceto di malto', 'casarecce di ceci',
                    'chicchi di farina di legumi', 'pasta di ceci', 'pasta di lenticchie', 'bacon')
LACTOSE_UNSURE = _rx('salsicc[a-z]*', 'salam[a-z]*', 'wurstel', 'prosciutto cotto', 'mortadella', 'pancarre',
                     'pan bauletto', 'panini per hamburger', 'panin[a-z]* al latte', 'sfoglia', 'margarina',
                     'fette biscottate', 'biscott[a-z]*', 'granola', 'cioccolato fondente', 'cioccolato', 'brioche',
                     'pesto', 'puccia', 'dado', 'brodo pronto', 'gelato', 'mix di', 'preparato', 'piadin[a-z]*', 'panin[a-z]*')
VEG_UNSURE = _rx('brodo', 'dado', 'caglio', 'pesto', 'piadin[a-z]*', 'tortill[a-z]*', 'sfoglia', 'salsa barbecue',
                 'fondo bruno', 'gelatina', 'preparato')
VEGAN_UNSURE = _rx('cioccolato fondente', 'cioccolato', 'pancarre', 'panin[a-z]*', 'pan bauletto',
                   'pasta fresca', '(?:strozzapreti|tagliatelle|gnocchi|ravioli|orecchiette|trofie) fresch[a-z]*', 'brioche',
                   'fette biscottate', 'biscott[a-z]*', 'granola', 'codette', 'decorazione', 'margarina')
VEG_OK = _rx('brodo vegetale', 'dado vegetale', 'salsa barbecue veg', 'pesto di [a-z]+ vegan[a-z]*')


def classify_ingredient(name):
    """Insieme di etichette per un singolo ingrediente."""
    # Le note fra parentesi e gli usi («per ungere i panini», «per gnocchi»)
    # non sono ingredienti: «Patate per gnocchi» non contiene glutine.
    core = re.sub(r'\([^)]*\)', ' ', str(name or ''))
    core = re.split(r'\s+per\s+', core, maxsplit=1)[0]
    t = fold(core)
    tags = set()
    plant = bool(PLANT_ALT.search(t))
    if FISH.search(t) and not re.search(r'\sfrutti di cappero\s', t):
        tags.add('pesce')
    if MEAT.search(t) and not plant and not re.search(r'\s(?:petto di (?:anatra )?)?(?:sedano|tofu)\s', t):
        # «Pesce spada» non è carne; «cosce di pollo» sì; «carne» vegetale (seitan) no.
        if not (re.search(r'\spolpett[a-z]*\s', t) and re.search(r'\s(?:verdur|legum|cec|lenticch|melanzan)', t)):
            tags.add('carne')
    if EGGS.search(t) and not plant and 'pesce' not in tags:
        tags.add('uova')
    if DAIRY.search(t) and not plant and not re.search(r'\s(?:burro di|latte di cocco|panna vegetale|formaggio vegan)', t):
        tags.add('lattosio' if not LACTOSE_FREE.search(t) else 'latte_senza_lattosio')
    if HONEY.search(t):
        tags.add('miele')
    if GLUTEN.search(t) and not GLUTEN_FREE.search(t) and not t.startswith(' patat'):
        tags.add('glutine')
    if GLUTEN_UNSURE.search(t) and 'glutine' not in tags and not re.search(r'\ssenza glutine\s', t):
        tags.add('glutine_incerto')
    if LACTOSE_UNSURE.search(t) and 'lattosio' not in tags and not LACTOSE_FREE.search(t):
        tags.add('lattosio_incerto')
    if VEG_UNSURE.search(t) and not VEG_OK.search(t) and not tags & {'carne', 'pesce'}:
        tags.add('vegetariano_incerto')
    if VEGAN_UNSURE.search(t) and not tags & {'carne', 'pesce', 'uova', 'lattosio', 'miele'}:
        tags.add('vegano_incerto')
    return tags


RULES = {
    'Vegetariano': ({'carne', 'pesce'}, {'vegetariano_incerto'}),
    'Vegano': ({'carne', 'pesce', 'uova', 'lattosio', 'latte_senza_lattosio', 'miele'},
               {'vegetariano_incerto', 'vegano_incerto'}),
    'Senza Glutine': ({'glutine'}, {'glutine_incerto'}),
    'Senza Lattosio': ({'lattosio'}, {'lattosio_incerto'}),
}


# Controllo di sicurezza sul titolo e sul procedimento: alcune fonti elencano
# solo una parte degli ingredienti (es. «...con pane croccante» senza il pane).
TEXT_CHECKS = {
    'Vegetariano': MEAT, 'Vegano': None,
    'Senza Glutine': _rx('pane', 'pangrattato', 'pan grattato', 'crostini', 'panko', 'crostin[io] di pane'),
    'Senza Lattosio': _rx('burro', 'panna', 'parmigiano', 'grana padano', 'formaggio', 'pecorino', 'mozzarella'),
}
TEXT_CHECKS['Vegano'] = _rx('uov[ao]', 'tuorl[a-z]*', 'burro', 'panna', 'miele', 'formaggio', 'parmigiano',
                            'grana padano', 'pecorino', 'mozzarella', 'latte')


def _text_conflicts(rec, diet):
    pattern = TEXT_CHECKS.get(diet)
    text = fold(' '.join([str(rec.get('name') or '')] +
                         [s for s in rec.get('steps') or [] if isinstance(s, str)]))
    hits = set()
    for rx in ([pattern] if pattern else []) + ([FISH] if diet in ('Vegetariano', 'Vegano') else []) + (
            [MEAT] if diet == 'Vegano' else []):
        for m in rx.finditer(text):
            word = m.group(0).strip()
            # «burro di arachidi», «latte di cocco», «senza burro»... non sono conflitti.
            after = text[m.end():m.end() + 14]
            before = text[max(0, m.start() - 8):m.start()]
            if re.match(r'(?:di |d )?(?:soia|mandorl|riso|avena|cocco|arachid|cacao)', after) or 'senza' in before:
                continue
            hits.add(word)
    return sorted(hits)


def assess_recipe(rec):
    """{'versione', 'compatibilita': {dieta: si|no|incerto}, 'motivi': {dieta: [ingredienti]}}"""
    names = []
    for item in rec.get('ingredients') or []:
        if isinstance(item, (list, tuple)) and item and isinstance(item[0], str):
            names.append(item[0])
    if not names:
        names = [x for x in rec.get('ingredients_display') or [] if isinstance(x, str)]
    tagged = [(n, classify_ingredient(n)) for n in names]
    result, reasons = {}, {}
    for diet, (blocking, unsure) in RULES.items():
        bad = [n for n, tags in tagged if tags & blocking]
        doubt = [n for n, tags in tagged if tags & unsure]
        if not names:
            result[diet] = 'incerto'
        elif bad:
            result[diet] = 'no'
        elif doubt:
            result[diet] = 'incerto'
        else:
            text = _text_conflicts(rec, diet)
            result[diet] = 'incerto' if text else 'si'
            doubt = [f'nel testo: {w}' for w in text]
        if bad or doubt:
            reasons[diet] = list(dict.fromkeys(bad + doubt))[:6]
    return {'versione': VERSION, 'compatibilita': result, 'motivi': reasons}
