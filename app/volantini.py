"""Volantini ufficiali dei supermercati scelti nell'onboarding.

Ogni catena ha una *pagina ufficiale dei volantini* verificata (mai siti
aggregatori). Per le catene che pubblicano un volantino unico nazionale il
recupero giornaliero (``aggiorna_volantini.py``) legge quella pagina e ricava
il link diretto al volantino in corso con le date di validità; l'app apre
quello. Se il volantino non si trova, è scaduto o la catena ha offerte diverse
per punto vendita, l'app apre la pagina ufficiale dei volantini, che mostra
sempre l'ultimo pubblicato.
"""
import re
from datetime import date, timedelta
from urllib.parse import urljoin
import html as _html

MESI = {m: i for i, m in enumerate(
    ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto',
     'settembre', 'ottobre', 'novembre', 'dicembre'], 1)}
_MESE = '(' + '|'.join(MESI) + ')'

# nazionale: stesso volantino in tutta Italia (link diretto possibile)
# per_negozio: offerte diverse per zona/punto vendita (si sceglie il negozio sul sito)
CATENE = {
    'Aldi': {'sito': 'https://www.aldi.it/', 'pagina': 'https://www.aldi.it/volantino-online', 'tipo': 'nazionale', 'estrattore': 'aldi'},
    'Alì': {'sito': 'https://www.alisupermercati.it/', 'pagina': 'https://www.alisupermercati.it/', 'tipo': 'per_negozio', 'estrattore': None},
    'Bennet': {'sito': 'https://www.bennet.com/', 'pagina': 'https://www.bennet.com/flyer', 'tipo': 'nazionale', 'estrattore': 'bennet'},
    'Carrefour': {'sito': 'https://www.carrefour.it/', 'pagina': 'https://www.carrefour.it/volantino', 'tipo': 'per_negozio', 'estrattore': None},
    'Conad': {'sito': 'https://www.conad.it/', 'pagina': 'https://www.conad.it/ricerca-negozi', 'tipo': 'per_negozio', 'estrattore': None},
    'Coop': {'sito': 'https://www.coop.it/', 'pagina': 'https://www.coop.it/', 'tipo': 'per_negozio', 'estrattore': None},
    'Decò': {'sito': 'https://supermercatideco.multicedi.it/', 'pagina': 'https://supermercatideco.multicedi.it/web/volantini.aspx', 'tipo': 'per_negozio', 'estrattore': None},
    'Despar': {'sito': 'https://www.despar.it/', 'pagina': 'https://www.despar.it/it/offerte-per-te/', 'tipo': 'per_negozio', 'estrattore': None},
    'Dodecà': {'sito': 'https://www.dodeca.it/', 'pagina': 'https://www.dodeca.it/', 'tipo': 'nazionale', 'estrattore': 'dodeca'},
    'Esselunga': {'sito': 'https://www.esselunga.it/', 'pagina': 'https://www.esselunga.it/it-it/promozioni/volantini.html', 'tipo': 'per_negozio', 'estrattore': None},
    'Eurospin': {'sito': 'https://www.eurospin.com/it-it/', 'pagina': 'https://www.eurospin.com/it-it/volantino/', 'tipo': 'nazionale', 'estrattore': 'eurospin'},
    'Famila': {'sito': 'https://www.famila.it/', 'pagina': 'https://www.famila.it/punti-vendita', 'tipo': 'per_negozio', 'estrattore': None},
    'Il Gigante': {'sito': 'https://ilgigante.net/', 'pagina': 'https://ilgigante.net/volantini/', 'tipo': 'per_negozio', 'estrattore': None},
    'Lidl': {'sito': 'https://www.lidl.it/', 'pagina': 'https://www.lidl.it/c/volantino-lidl/s10018048', 'tipo': 'nazionale', 'estrattore': 'lidl'},
    'MD': {'sito': 'https://www.mdspa.it/', 'pagina': 'https://www.mdspa.it/volantino/', 'tipo': 'nazionale', 'estrattore': 'md'},
    'PAM': {'sito': 'https://www.pampanorama.it/', 'pagina': 'https://www.pampanorama.it/promoinstoredest', 'tipo': 'per_negozio', 'estrattore': None},
    'Penny': {'sito': 'https://www.penny.it/', 'pagina': 'https://www.penny.it/sfoglia-il-volantino-mobile', 'tipo': 'per_negozio', 'estrattore': None},
    'Sole365': {'sito': 'https://www.sole365.it/', 'pagina': 'https://www.sole365.it/', 'tipo': 'per_negozio', 'estrattore': None},
    'Tigros': {'sito': 'https://www.tigros.it/', 'pagina': 'https://www.tigros.it/volantini', 'tipo': 'per_negozio', 'estrattore': None},
}
ALIAS = {'Dec': 'Decò'}

# Host ammessi per i link diretti: solo domini dei marchi o i visualizzatori
# ufficiali che i marchi stessi incorporano nelle proprie pagine.
HOST_UFFICIALI = {
    'Aldi': ('volantino.aldi.it', 'www.aldi.it'),
    'Bennet': ('nativa.bennet.volantinopiu.com', 'www.bennet.com', 'bennet-cdn.thron.com'),
    'Dodecà': ('viewer.flyer.volantinopiu.ai', 'www.dodeca.it'),
    'Eurospin': ('flyer.eurospin.com', 'www.eurospin.com'),
    'Lidl': ('www.lidl.it',),
    'MD': ('www.mdspa.it',),
}


def _testo(fragment):
    return re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', fragment))).strip()


def _anno_vicino(giorno, mese, oggi):
    """Data senza anno: l'anno che la rende più vicina a oggi."""
    best = None
    for anno in (oggi.year - 1, oggi.year, oggi.year + 1):
        try:
            d = date(anno, mese, giorno)
        except ValueError:
            continue
        if best is None or abs((d - oggi).days) < abs((best - oggi).days):
            best = d
    return best


def _data(giorno, mese, anno, oggi):
    giorno, mese = int(giorno), int(mese)
    if anno:
        anno = int(anno)
        anno = anno + 2000 if anno < 100 else anno
        try:
            return date(anno, mese, giorno)
        except ValueError:
            return None
    return _anno_vicino(giorno, mese, oggi)


def periodo(testo, oggi):
    """Ricava (dal, al) da frasi come «dal 12/11 al 18/11», «Dal 5 al 15 novembre
    2026», «dal 30 ottobre al 9 novembre», «da lunedì 16 novembre»."""
    t = _testo(testo).lower()
    m = re.search(r'\bdal?l?[’\']?\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*(?:al|fino al|-)\s*(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', t)
    if m:
        dal = _data(m.group(1), m.group(2), m.group(3), oggi)
        al = _data(m.group(4), m.group(5), m.group(6), oggi)
        if dal and al and al < dal and not m.group(3):
            dal = _data(m.group(1), m.group(2), al.year - (1 if int(m.group(2)) > al.month else 0), oggi)
        return dal, al
    m = re.search(r'\bdal?l?[’\']?\s*(\d{1,2})(?:\s+' + _MESE + r')?(?:\s+(\d{4}))?\s+(?:al|all[’\'])\s*(\d{1,2})\s+' + _MESE + r'(?:\s+(\d{4}))?', t)
    if m:
        g1, m1, a1, g2, m2, a2 = m.groups()
        mese2 = MESI[m2]
        al = _data(g2, mese2, a2, oggi)
        mese1 = MESI[m1] if m1 else mese2
        anno1 = a1 or (str(al.year - (1 if mese1 > mese2 else 0)) if al else None)
        dal = _data(g1, mese1, anno1, oggi)
        return dal, al
    m = re.search(r'\bda\s+(?:lunedì|lunedi|martedì|martedi|mercoledì|mercoledi|giovedì|giovedi|venerdì|venerdi|sabato|domenica)?\s*(\d{1,2})(?:/(\d{1,2})|\s+' + _MESE + r')', t)
    if m:
        mese = int(m.group(2)) if m.group(2) else MESI[m.group(3)]
        return _data(m.group(1), mese, None, oggi), None
    return None, None


def _ammesso(catena, url):
    host = re.sub(r'^https?://', '', url).split('/')[0].lower()
    return host in HOST_UFFICIALI.get(catena, ())


# --- Estrattori: ognuno restituisce candidati {url, titolo, dal, al} -------

def estrai_aldi(html, base, oggi):
    out = []
    for url in sorted(set(re.findall(r'https://volantino\.aldi\.it/[^"\'\s<>]+', html))):
        slug = url.split('/')[3].lower()
        m = re.search(r'(?:da_)?(?:lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)?_?(\d{1,2})_' + _MESE, slug.replace('-', '_'))
        if not m or 'offerte' not in slug:
            continue
        dal = _anno_vicino(int(m.group(1)), MESI[m.group(2)], oggi)
        out.append({'url': url, 'titolo': 'Offerte ALDI della settimana', 'dal': dal, 'al': None})
    return out


def estrai_bennet(html, base, oggi):
    out = []
    parti = re.split(r'Visualizza volantino', html)
    for parte in parti[:-1]:
        urls = re.findall(r'https://nativa\.bennet\.volantinopiu\.com/volantino\d+\.html', parte)
        if not urls:
            continue
        coda = parte[-3000:]
        dal, al = periodo(coda, oggi)
        if not dal:
            continue
        titoli = [t for t in (_testo(x) for x in re.findall(r'<h\d[^>]*>(.*?)</h\d>', coda, re.S)) if t and len(t) < 90]
        out.append({'url': urls[-1], 'titolo': titoli[-1] if titoli else 'Volantino Bennet', 'dal': dal, 'al': al})
    return out


def estrai_eurospin(html, base, oggi):
    dal, al = periodo(html, oggi)
    if not dal or 'flyer.eurospin.com/it-it/volantino' not in html:
        return []
    return [{'url': 'https://flyer.eurospin.com/it-it/volantino', 'titolo': 'Volantino Eurospin', 'dal': dal, 'al': al}]


def estrai_md(html, base, oggi):
    dal, al = periodo(html, oggi)
    if not dal:
        return []
    return [{'url': base, 'titolo': 'Volantino MD', 'dal': dal, 'al': al}]


def estrai_lidl(html, base, oggi):
    """I volantini settimanali Lidl si sfogliano dopo aver scelto il punto vendita
    nella pagina ufficiale: il link resta la pagina, con le date del volantino in corso."""
    out = []
    for m in re.finditer(r'flyer__name[^>]*>(.*?)</div>\s*(?:<span class="flyer__title">(.*?)</span>)?', html, re.S):
        dal, al = periodo(m.group(1), oggi)
        if not dal:
            continue
        titolo = _testo(m.group(2) or '') or 'Volantino settimanale'
        out.append({'url': base, 'titolo': titolo, 'dal': dal, 'al': al, 'scegli_negozio': True})
    return out


def estrai_dodeca(html, base, oggi):
    out = []
    for url in dict.fromkeys(re.findall(r'https://viewer\.flyer\.volantinopiu\.ai/[^"\'\s<>]+', html)):
        # La home linka sempre il volantino attuale; non riporta date affidabili.
        out.append({'url': _html.unescape(url), 'titolo': 'Volantino Dodecà', 'dal': None, 'al': None, 'senza_date': True})
    return out[:1]


ESTRATTORI = {'aldi': estrai_aldi, 'bennet': estrai_bennet, 'eurospin': estrai_eurospin,
              'md': estrai_md, 'lidl': estrai_lidl, 'dodeca': estrai_dodeca}


def in_corso(c, oggi):
    if c.get('senza_date'):
        return True
    dal, al = c.get('dal'), c.get('al')
    if not dal or dal > oggi:
        return False
    if al is None:
        return (oggi - dal).days <= 7  # volantini settimanali senza data di fine
    return oggi <= al


def scegli(candidati, oggi):
    """Il volantino in corso più recente e, se già pubblicato, il prossimo."""
    validi = [c for c in candidati if _ok_url(c)]
    correnti = [c for c in validi if in_corso(c, oggi)]
    # più recente = inizio più tardi; a parità, quello che finisce prima (il settimanale)
    correnti.sort(key=lambda c: (c.get('dal') or date.min, -((c.get('al') or date.max) - (c.get('dal') or date.min)).days))
    futuri = sorted((c for c in validi if c.get('dal') and c['dal'] > oggi), key=lambda c: c['dal'])
    return (correnti[-1] if correnti else None), (futuri[0] if futuri else None)


def _ok_url(c):
    return bool(c.get('url', '').startswith('https://'))


def _serializza(c, oggi):
    if not c:
        return None
    out = {'url': c['url'], 'titolo': c.get('titolo') or '',
           'valido_dal': c['dal'].isoformat() if c.get('dal') else None,
           'valido_al': c['al'].isoformat() if c.get('al') else None}
    if c.get('scegli_negozio'):
        out['scegli_negozio'] = True
    if c.get('senza_date'):
        # Link letto oggi dalla home ufficiale: vale finché i controlli lo confermano.
        out['verificato_il'] = oggi.isoformat()
    return out


def voce(catena, html, oggi, controllato_il, precedente=None, errore=None):
    """Voce di data/volantini.json per una catena."""
    info = CATENE[catena]
    base = {'pagina_ufficiale': info['pagina'], 'sito': info['sito'], 'tipo': info['tipo'],
            'controllato_il': controllato_il, 'volantino': None, 'prossimo': None,
            'metodo': 'pagina_ufficiale'}
    if not info['estrattore']:
        return base
    corrente = prossimo = None
    if html is not None:
        candidati = [c for c in ESTRATTORI[info['estrattore']](html, info['pagina'], oggi)
                     if _ammesso(catena, c['url'])]
        corrente, prossimo = scegli(candidati, oggi)
    if corrente:
        base.update(volantino=_serializza(corrente, oggi), metodo='link_diretto')
    elif precedente and _ancora_valido(precedente.get('volantino'), oggi):
        # Pagina momentaneamente non leggibile: si tiene il volantino già trovato finché vale.
        base.update(volantino=precedente['volantino'], metodo='link_diretto_precedente')
    if prossimo:
        base['prossimo'] = _serializza(prossimo, oggi)
    elif precedente and _ancora_futuro(precedente.get('prossimo'), oggi):
        base['prossimo'] = precedente['prossimo']
    if errore:
        base['errore'] = errore
    return base


def _iso(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _ancora_valido(v, oggi):
    if not v or not v.get('url'):
        return False
    dal, al = _iso(v.get('valido_dal')), _iso(v.get('valido_al'))
    if not dal and not al:
        ver = _iso(v.get('verificato_il'))
        return bool(ver and timedelta(0) <= (oggi - ver) <= timedelta(days=3))
    if al:
        return (not dal or dal <= oggi) and oggi <= al
    return bool(dal and dal <= oggi and (oggi - dal) <= timedelta(days=7))


def _ancora_futuro(v, oggi):
    return bool(v and _iso(v.get('valido_dal')) and _iso(v['valido_dal']) > oggi)


def link_da_aprire(catena, dati, oggi):
    """Lo stesso criterio usato dall'app: link diretto se valido oggi, altrimenti la pagina ufficiale."""
    catena = ALIAS.get(catena, catena)
    info = CATENE.get(catena)
    if not info:
        return None
    entry = (dati or {}).get('catene', {}).get(catena) or {}
    v = entry.get('volantino')
    prossimo = entry.get('prossimo')
    if _ancora_valido(prossimo, oggi) and (not _ancora_valido(v, oggi) or
                                           _iso(prossimo.get('valido_dal')) > (_iso(v.get('valido_dal')) or date.min)):
        v = prossimo  # il nuovo volantino è iniziato dopo l'ultimo controllo
    if _ancora_valido(v, oggi):
        return v['url']
    return entry.get('pagina_ufficiale') or info['pagina']
