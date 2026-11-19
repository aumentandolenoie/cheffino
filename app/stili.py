"""Stili delle ricette scelti nell'onboarding («Che tipo di ricette preferisci?»).

Una ricetta può avere più stili. Le regole usano solo dati pubblicati dalla
fonte (tempo, costo, calorie e valori nutrizionali, ingredienti con quantità,
nome e procedimento): nessun valore viene stimato o inventato. Calcolati al
volo nell'API, valgono subito anche per le ricette nuove.

  Veloci e facili        tempo totale ≤ 30 min e al massimo 8 passaggi
  Economiche             costo della fonte «Molto basso» o «Basso»
  Poche calorie          ≤ 450 kcal a porzione
  Piatti salutari        ≤ 600 kcal e ≤ 25 g di grassi a porzione, niente fritture
  Proteici               ≥ 25 g di proteine a porzione (se la fonte le indica),
                         altrimenti ≥ 120 g a porzione di carne, pesce, legumi o
                         tofu, oppure almeno 2 uova a porzione
  Per tutta la famiglia  ≤ 60 min, costo non elevato, niente alcol né piccante
  Classici italiani      ricette tradizionali riconoscibili dal nome
  Takeaway fatto in casa burger, panini, pizza, wrap, poke e simili
"""
import re

from app.diete import EGGS, FISH, MEAT, fold

STILI = ('Veloci e facili', 'Proteici', 'Piatti salutari', 'Per tutta la famiglia',
         'Classici italiani', 'Poche calorie', 'Economiche', 'Takeaway fatto in casa')
VERSION = 1

LEGUMI_TOFU = re.compile(r'\s(?:ceci|fagiol[a-z]*|lenticchi[a-z]*|fave|piselli|pisellini|cicerchi[a-z]*|'
                         r'lupini|edamame|soia|tofu|tempeh|seitan)\s')
FRITTURA = re.compile(r'\s(?:fritt[a-z]*|friggere|friggete|frigge[a-z]*|frittura|in pastella)\s')
ALCOL = re.compile(r'\s(?:vino|vini|birra|liquore|rum|brandy|cognac|grappa|marsala|vermouth|vermut|whisky|'
                   r'vodka|gin|porto|sherry|limoncello|amaretto liquore|cointreau|sake)\s')
PICCANTE = re.compile(r'\s(?:piccant[a-z]*|nduja|habanero|jalapeno[a-z]*|tabasco|sriracha|harissa|chili)\s')
CLASSICI = re.compile(
    r'\s(?:carbonara|amatriciana|gricia|cacio e pepe|ragu|bolognese|lasagn[a-z]*|parmigiana|ossobuc[a-z]*|'
    r'saltimbocca|vitello tonnato|pasta e fagioli|pasta e ceci|pasta e patate|pasta e lenticchie|minestrone|'
    r'ribollita|pappa al pomodoro|panzanella|caponata|peperonata|arancin[a-z]*|supplì|suppli|pizzoccheri|'
    r'orecchiette|trofie|al pesto|pesto alla genovese|alla genovese|milanese|romana|napoletana|siciliana|vicentina|veneziana|livornese|'
    r'pizzaiola|cacciatora|alla norma|puttanesca|aglio olio|scaloppin[a-z]*|involtin[a-z]*|spezzatino|'
    r'brasato|bollito|polpette al sugo|frittata|cotoletta|gnocchi alla sorrentina|tortellini|cannelloni|'
    r'pasta al forno|risotto alla milanese|baccala|sarde a beccafico|pasta con le sarde|melanzane ripiene|'
    r'zuppa di cipolle|pasta fagioli|polenta|tiella|pasta al pomodoro|tagliatelle al ragu|pasta alla norma|'
    r'friarielli|cime di rapa|carciofi alla|fiori di zucca)\s')
TAKEAWAY = re.compile(r'\s(?:burger[a-z]*|hamburger[a-z]*|panin[oi]|sandwich|club sandwich|toast|piadin[a-z]*|'
                      r'pizz[ae]|pizzette|calzon[ei]|kebab|pita|wrap|tacos?|burrito[s]?|quesadill[a-z]*|'
                      r'hot dog|nuggets?|crocchett[a-z]*|pulled|poke|sushi|noodles|ramen|fish and chips|'
                      r'patatine|chicken|bao|falafel|felafel|gyros|street food|tramezzin[a-z]*)\s')


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0 else None


def _grammi(qty, unit):
    q = _num(qty)
    if q is None:
        return None
    unit = (unit or '').strip().lower()
    return {'g': q, 'gr': q, 'kg': q * 1000, 'hg': q * 100}.get(unit)


def _porzioni(rec):
    s = _num(rec.get('servings'))
    return s if s and s > 0 else None


def proteico(rec):
    prot = _num(rec.get('protein'))
    if prot is not None:
        return prot >= 25
    porz = _porzioni(rec)
    if not porz:
        return False
    grammi = uova = 0
    for ing in rec.get('ingredients') or []:
        if not isinstance(ing, (list, tuple)) or not ing:
            continue
        nome = fold(ing[0])
        qty = ing[1] if len(ing) > 1 else None
        unit = ing[2] if len(ing) > 2 else ''
        if re.search(r'\s(?:brodo|fumetto|colatura|salsa|maionese|dado)\s', nome):
            continue
        if EGGS.search(nome) and re.search(r'\suov[ao]\s', nome):
            n = _num(qty)
            if n is not None and (unit or '').lower() in ('', 'pezzi', 'pz', 'n'):
                uova += n
            elif _grammi(qty, unit):
                uova += _grammi(qty, unit) / 55
            continue
        if MEAT.search(nome) or FISH.search(nome) or LEGUMI_TOFU.search(nome):
            g = _grammi(qty, unit)
            if g:
                grammi += g
    return grammi / porz >= 120 or uova / porz >= 2


def stili(rec):
    """Elenco degli stili della ricetta, nell'ordine di STILI."""
    out = set()
    nome = fold(rec.get('name'))
    ingredienti = fold(' '.join(str(i[0]) for i in rec.get('ingredients') or [] if isinstance(i, (list, tuple)) and i))
    testo = fold(' '.join(str(s) for s in rec.get('steps') or []))
    tempo = _num(rec.get('time'))
    passaggi = len(rec.get('steps') or [])
    costo = (rec.get('source_cost') or rec.get('cost') or '').strip().lower()
    kcal, grassi = _num(rec.get('kcal')), _num(rec.get('fats'))
    fritto = bool(FRITTURA.search(nome) or FRITTURA.search(testo))

    if tempo is not None and tempo <= 30 and 0 < passaggi <= 8:
        out.add('Veloci e facili')
    if costo in ('molto basso', 'basso'):
        out.add('Economiche')
    if kcal is not None and 0 < kcal <= 450:
        out.add('Poche calorie')
    if kcal is not None and 0 < kcal <= 600 and (grassi is None or grassi <= 25) and not fritto:
        out.add('Piatti salutari')
    if proteico(rec):
        out.add('Proteici')
    if (tempo is not None and tempo <= 60 and costo != 'elevato'
            and not ALCOL.search(ingredienti) and not PICCANTE.search(nome + ingredienti)):
        out.add('Per tutta la famiglia')
    if CLASSICI.search(nome):
        out.add('Classici italiani')
    if TAKEAWAY.search(nome):
        out.add('Takeaway fatto in casa')
    return [s for s in STILI if s in out]
