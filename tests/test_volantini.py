"""Volantini: sempre l'ultimo volantino ufficiale del supermercato scelto."""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from app import volantini as V
from aggiorna_volantini import aggiorna
from app.rete import FetchError

ROOT = Path(__file__).resolve().parent.parent
OGGI = date(2026, 11, 15)

ALDI = '''<a href="https://volantino.aldi.it/aldi_offerte_da_lunedi_9_novembre/page/1">Sfoglia</a>
<a href="https://volantino.aldi.it/aldi_offerte_da_lunedi_16_novembre/page/1">Sfoglia</a>
<a href="https://volantino.aldi.it/brochurevinotecaaldi2024/page/1">Vini</a>'''

BENNET = '''<div><h3>Volantino Bennet</h3><a href="https://nativa.bennet.volantinopiu.com/volantino2950100.html"></a>
<p>Dal 12/11 al 25/11</p><a href="https://nativa.bennet.volantinopiu.com/volantino2950100.html">Visualizza volantino</a></div>
<div><h3>Natale</h3><a href="https://nativa.bennet.volantinopiu.com/volantino2950500.html"></a>
<p>Dal 05/11 al 24/12</p><a href="https://nativa.bennet.volantinopiu.com/volantino2950500.html">Visualizza volantino</a></div>
<div><a href="https://nativa.bennet.volantinopiu.com/volantino2936100.html"></a>
<p>Dal 05/11 al 18/11</p><a href="https://nativa.bennet.volantinopiu.com/volantino2936100.html">Visualizza volantino</a></div>'''

LIDL = '''<button class="flyer"><div class="flyer__content"><div class="flyer__name"> Offerte valide dal 12/11 al 18/11 </div>
<span class="flyer__title"> Volantino settimanale </span></div></button>
<button class="flyer"><div class="flyer__content"><div class="flyer__name"> Offerte valide dal 19/11 al 25/11 </div>
<span class="flyer__title"> Volantino settimanale </span></div></button>
<a href="https://www.lidl.it/l/it/volantini/mercatini/ar/0" class="flyer"><div class="flyer__content"><div class="flyer__name"> Mercatini </div></div></a>'''

EUROSPIN = '<p>Dal 5 al 15 novembre 2026</p><a href="https://flyer.eurospin.com/it-it/volantino">Leggi volantino</a>'
MD = '<h2>Volantino valido dal 3 al 15 Novembre 2026</h2>'
DODECA = '<a href="https://viewer.flyer.volantinopiu.ai/preview-dodeca-1?mode=scroll"><img></a>'
PAGINE = {'Aldi': ALDI, 'Bennet': BENNET, 'Lidl': LIDL, 'Eurospin': EUROSPIN, 'MD': MD, 'Dodecà': DODECA}


@pytest.mark.parametrize('testo,atteso', [
    ('Dal 12/11 al 25/11', (date(2026, 11, 12), date(2026, 11, 25))),
    ('Offerte valide dal 19/11 al 25/11', (date(2026, 11, 19), date(2026, 11, 25))),
    ('Dal 5 al 15 novembre 2026', (date(2026, 11, 5), date(2026, 11, 15))),
    ('dal 30 ottobre al 9 novembre', (date(2026, 10, 30), date(2026, 11, 9))),
    ("Dall'8 al 21 gennaio 2027", (date(2027, 1, 8), date(2027, 1, 21))),
    ('dal 28/12 al 3/1', (date(2026, 12, 28), date(2027, 1, 3))),
    ('Da giovedì 19/11', (date(2026, 11, 19), None)),
    ('nessuna data', (None, None)),
])
def test_periodo(testo, atteso):
    assert V.periodo(testo, OGGI) == atteso


def test_catene_coprono_onboarding_e_solo_siti_ufficiali():
    html = (ROOT / 'frontend' / 'index.html').read_text()
    elenco = re.search(r"const supermarkets=\[(.*?)\];", html).group(1)
    nomi = re.findall(r"'([^']+)'", elenco)
    assert set(nomi) == set(V.CATENE)
    for nome, info in V.CATENE.items():
        assert info['pagina'].startswith('https://')
        assert not re.search(r'doveconviene|promoqui|volantinofacile|portavolantino', info['pagina'])
    # le pagine scritte nell'app coincidono con quelle usate dal recupero
    pagine_js = dict(re.findall(r"'([^']+)':'(https://[^']+)'", re.search(r'const flyerPages=\{(.*?)\};', html).group(1)))
    assert pagine_js == {n: i['pagina'] for n, i in V.CATENE.items()}


def test_aldi_sceglie_il_volantino_della_settimana_e_annuncia_il_prossimo():
    v = V.voce('Aldi', ALDI, OGGI, 'x')
    assert v['volantino']['url'].endswith('lunedi_9_novembre/page/1')
    assert v['prossimo']['valido_dal'] == '2026-11-16'
    # lunedì il prossimo diventa quello in corso
    v2 = V.voce('Aldi', ALDI, date(2026, 11, 16), 'x')
    assert v2['volantino']['url'].endswith('lunedi_16_novembre/page/1')


def test_bennet_preferisce_il_piu_recente_tra_quelli_validi():
    v = V.voce('Bennet', BENNET, OGGI, 'x')
    assert v['volantino']['url'].endswith('volantino2950100.html')
    assert (v['volantino']['valido_dal'], v['volantino']['valido_al']) == ('2026-11-12', '2026-11-25')


def test_lidl_date_e_scelta_del_punto_vendita():
    v = V.voce('Lidl', LIDL, OGGI, 'x')
    assert v['volantino']['valido_al'] == '2026-11-18' and v['volantino']['scegli_negozio']
    assert v['volantino']['url'] == V.CATENE['Lidl']['pagina']
    assert v['prossimo']['valido_dal'] == '2026-11-19'


EUROSPIN_2 = '''<a href="https://flyer.eurospin.com/it-it/punti-vendita/eurospin-italia/promozioni/sapori-in-festa"><img></a>
<p>Dal 16 al 25 novembre 2026</p><p>Sapori in festa</p>
<a href="https://flyer.eurospin.com/it-it/punti-vendita/eurospin-italia/promozioni/black-friday-2026-eurospin-online"><img></a>
<p>Dal 5 al 29 novembre 2026</p><p>Black Friday</p>'''


def test_eurospin_elenco_volantini_con_date():
    v = V.voce('Eurospin', EUROSPIN_2, date(2026, 11, 19), 'x')
    assert v['volantino']['url'].endswith('/promozioni/sapori-in-festa')
    assert (v['volantino']['valido_dal'], v['volantino']['valido_al']) == ('2026-11-16', '2026-11-25')


def test_volantino_scaduto_non_viene_aperto():
    v = V.voce('Eurospin', EUROSPIN, date(2026, 11, 16), 'x')
    assert v['volantino'] is None and v['metodo'] == 'pagina_ufficiale'
    dati = {'catene': {'Eurospin': v}}
    assert V.link_da_aprire('Eurospin', dati, date(2026, 11, 16)) == V.CATENE['Eurospin']['pagina']


def test_prossimo_iniziato_dopo_l_ultimo_controllo_viene_aperto():
    dati = {'catene': {'Aldi': V.voce('Aldi', ALDI, OGGI, 'x')}}
    assert V.link_da_aprire('Aldi', dati, OGGI).endswith('9_novembre/page/1')
    assert V.link_da_aprire('Aldi', dati, date(2026, 11, 17)).endswith('16_novembre/page/1')


def test_catene_per_negozio_aprono_la_pagina_ufficiale():
    for nome in ('Conad', 'Coop', 'Esselunga', 'Carrefour', 'Decò'):
        v = V.voce(nome, None, OGGI, 'x')
        assert v['volantino'] is None and v['tipo'] == 'per_negozio'
        assert V.link_da_aprire(nome, {'catene': {nome: v}}, OGGI) == V.CATENE[nome]['pagina']
    assert V.link_da_aprire('Dec', {}, OGGI) == V.CATENE['Decò']['pagina']


def test_host_non_ufficiale_scartato():
    finto = ALDI.replace('https://volantino.aldi.it', 'https://volantino.esempio.com')
    assert V.voce('Aldi', finto, OGGI, 'x')['volantino'] is None


def test_dodeca_senza_date_vale_solo_se_verificato_di_recente():
    v = V.voce('Dodecà', DODECA, OGGI, 'x')
    dati = {'catene': {'Dodecà': v}}
    assert V.link_da_aprire('Dodecà', dati, OGGI).startswith('https://viewer.flyer.volantinopiu.ai/')
    assert V.link_da_aprire('Dodecà', dati, date(2026, 11, 25)) == V.CATENE['Dodecà']['pagina']


def test_aggiorna_conserva_il_volantino_se_la_pagina_non_risponde():
    def ok(url, **kw):
        return next(h for n, h in PAGINE.items() if V.CATENE[n]['pagina'] == url)
    primo = aggiorna(OGGI, {}, fetch=ok, pausa=0)
    assert all(primo['catene'][n]['volantino'] for n in PAGINE)

    def giu(url, **kw):
        raise FetchError('HTTP 503', 503, True)
    secondo = aggiorna(OGGI, primo, fetch=giu, pausa=0)
    assert secondo['catene']['Bennet']['volantino'] == primo['catene']['Bennet']['volantino']
    assert secondo['catene']['Bennet']['metodo'] == 'link_diretto_precedente'
    assert 'errore' in secondo['catene']['Bennet']
    # a scadenza superata non si riusa più
    terzo = aggiorna(date(2026, 11, 26), primo, fetch=giu, pausa=0)
    assert terzo['catene']['Bennet']['volantino'] is None
    json.dumps(secondo)  # serializzabile


def test_frontend_apre_subito_il_volantino_in_entrambe_le_versioni():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        assert "caricaVolantini();" in html and "'/api/volantini','/data/volantini.json'" in html
        assert 'function openFlyerFor(i){const s=state.stores[i];if(s===undefined)return;const tg=flyerTarget(s);openUrl(tg.url)' in html
        assert 'Questo prototipo apre il sito ufficiale' not in html
        assert "'Coop','Decò','Despar'" in html and "x==='Dec'?'Decò':x" in html
