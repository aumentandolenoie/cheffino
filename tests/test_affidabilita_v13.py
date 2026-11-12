"""Regressioni per l'affidabilità di importazione ricette, pulizia testi e rete."""
import io
import json
from urllib.error import HTTPError

import pytest

from app.catalog import build_record, normalize_url, parse_recipe
from app.ingredienti import clean_text, format_ingredient, is_resolved, parse_ingredient
from app.rete import FetchError, fetch_text
from audit_ricette import check_record
from normalizza_catalogo import normalize_record
from pulisci_procedimenti import clean_steps, photo_numbers

URL = 'https://ricette.giallozafferano.it/Pasta-test.html'


# --- ingredienti -------------------------------------------------------------
@pytest.mark.parametrize('text,expected', [
    ('Spaghetti 320 g', ['Spaghetti', 320, 'g']),
    ('Farina 00 200 g', ['Farina 00', 200, 'g']),
    ('Aglio 1 spicchio', ['Aglio', 1, 'spicchio']),
    ('Sale fino q.b.', ['Sale fino', None, 'q.b.']),
    ('Uova medie 3', ['Uova medie', 3, 'pezzi']),
    ('Cipolle &frac12;', ['Cipolle', 0.5, 'pezzi']),
    ('Pasta Sfoglia 2 rotoli rettangolari 460 g', ['Pasta Sfoglia 2 rotoli rettangolari', 460, 'g']),
    ('Lasagne all\'uovo (20 sfoglie) 440 g', ["Lasagne all'uovo (20 sfoglie)", 440, 'g']),
    ('Pepe nero 1 pizzico', ['Pepe nero', 1, 'pizzichi']),
    ('Acqua 1,5 l', ['Acqua', 1.5, 'l']),
])
def test_parser_ingredienti(text, expected):
    assert parse_ingredient(text) == expected


@pytest.mark.parametrize('text', [
    'Succo di limone ½',            # derivato: non è «mezzo pezzo»
    'Lenticchie secche 250',        # numero grande senza unità: probabilmente grammi
    'Zucchero 75',                  # ingrediente che si pesa, unità assente
    'Lattuga qualche foglia',
])
def test_parser_non_inventa_quantita(text):
    assert not is_resolved(parse_ingredient(text))


def test_clean_text_decodifica_entita_e_spazi():
    assert clean_text('Cipolle&nbsp;&frac12;<br>  rosse') == 'Cipolle ½ rosse'
    assert clean_text('&amp;frac12;') == '½'


def test_format_ingredient():
    assert format_ingredient(['Fusilli', 320, 'g']) == 'Fusilli 320 g'
    assert format_ingredient(['Sale', None, 'q.b.']) == 'Sale q.b.'
    assert format_ingredient(['Uova', 2, 'pezzi']) == 'Uova 2'


# --- riferimenti alle foto nei passaggi ----------------------------------------
STEPS = [
    "Grattugiate la scorza 1 e spremete il succo 2 e filtratelo 3 .",
    "Passate il pollo nella farina 4 e mescolate per farla aderire (5. Versate l'olio 6 e scaldatelo;",
    "Cuocete per 10 minuti, unite 2 cucchiai d'acqua 7 , tagliate in 4 parti e servite 8 .",
    "Tagliate a cubetti di 1,5 cm (9-10) e decorate con 3 foglie di basilico.",
]
IMAGES = [[f'https://ricette.giallozafferano.it/images/ricette/1/123/p_{i}.jpg' for i in r]
          for r in ((1, 2, 3), (4, 5, 6), (7, 8), (9, 10))]


def test_photo_numbers_da_nomi_file_e_strip():
    assert photo_numbers(IMAGES)[1] == {4, 5, 6}
    strip = [['https://www.giallozafferano.it/images/ricette/1/123/123_p_strip_7-9.jpg']]
    assert photo_numbers(strip) == [{7, 8, 9}]
    assert photo_numbers([['https://www.giallozafferano.it/images/123-12345/p_650x433_wm.jpg']]) is None


def test_pulizia_v2_rimuove_tutti_i_riferimenti_e_conserva_le_dosi():
    cleaned, removed = clean_steps(STEPS, IMAGES)
    assert removed == 9
    assert cleaned[0] == 'Grattugiate la scorza e spremete il succo e filtratelo.'
    assert cleaned[1] == "Passate il pollo nella farina e mescolate per farla aderire. Versate l'olio e scaldatelo;"
    assert '10 minuti' in cleaned[2] and '2 cucchiai' in cleaned[2] and 'in 4 parti' in cleaned[2]
    assert cleaned[2].endswith('e servite.')
    assert cleaned[3] == 'Tagliate a cubetti di 1,5 cm e decorate con 3 foglie di basilico.'


def test_pulizia_v2_senza_foto_usa_catena_crescente_con_buchi():
    # La v1 si fermava al primo numero mancante (qui il 3) lasciando «5» e «6».
    steps = ['Lavate i pomodori 1 e tagliateli 2 .', 'Scaldate la padella 4 , unite i pomodori 5 .',
             'Servite 6 .']
    cleaned, removed = clean_steps(steps)
    assert removed == 5
    assert cleaned == ['Lavate i pomodori e tagliateli.', 'Scaldate la padella, unite i pomodori.', 'Servite.']


def test_pulizia_v2_non_tocca_numeri_isolati():
    steps = ['Dividete la pasta in 4 .', 'Cuocete a 180° per 20 minuti.']
    assert clean_steps(steps) == (steps, 0)


# --- parser JSON-LD ----------------------------------------------------------
def page(obj):
    return f'<html><script type="application/ld+json">{obj}</script></html>'


def test_parse_recipe_sezioni_entita_e_immagini():
    data = {'@context': 'https://schema.org', '@graph': [{'@type': ['Recipe'], 'name': 'Pasta &amp; ceci',
            'image': [{'@type': 'ImageObject', 'url': 'https://www.giallozafferano.it/images/1-100/a.jpg'}],
            'recipeIngredient': ['Cipolle &frac12;', 'Pasta 200 g'], 'recipeYield': ['4'],
            'nutrition': {'calories': '300 kcal', 'protein': '12 g'},
            'recipeInstructions': [{'@type': ['HowToSection'], 'name': 'Sugo',
                                    'itemListElement': [{'@type': 'HowToStep', 'text': 'Soffriggete<br>la cipolla.'}]},
                                   {'@type': 'HowToStep', 'text': 'Cuocete&nbsp;la pasta.'}]}]}
    raw = parse_recipe(page(json.dumps(data)), URL)
    assert raw['name'] == 'Pasta & ceci'
    assert raw['ingredients'] == ['Cipolle ½', 'Pasta 200 g']
    assert raw['steps'] == ['Soffriggete la cipolla.', 'Cuocete la pasta.']  # la sezione non è un passaggio
    assert raw['image_url'].endswith('/a.jpg')
    assert raw['yield_text'] == '4'
    assert raw['nutrition']['proteinContent'] == '12 g'


def test_parse_recipe_json_con_virgola_finale_e_istruzioni_testuali():
    html = page('{"@type":"Recipe","name":"Zuppa","recipeIngredient":["Acqua 1 l","Sale q.b.",],'
                '"recipeInstructions":"Scaldate l\'acqua.\\nSalate.",}')
    raw = parse_recipe(html, URL)
    assert raw['steps'] == ["Scaldate l'acqua.", 'Salate.']


def test_build_record_completa_porzioni_tempi_e_quantita():
    raw = {'name': 'Pasta', 'url': URL + '?utm=1', 'ingredients': ['Pasta 320 g', 'Sale q.b.'],
           'steps': ['Cuocete la pasta 1 .', 'Scolatela 2 .', 'Servite 3 .'],
           'yield_text': '4 persone', 'prep_time': 'PT10M', 'cook_time': 'PT15M',
           'nutrition': {'calories': '350 kcal', 'proteinContent': '11 g'}, 'image_url': None}
    rec = build_record(raw)
    assert rec['url'] == URL and rec['servings'] == 4 and rec['time'] == 25
    assert rec['ingredients'] == [['Pasta', 320, 'g'], ['Sale', None, 'q.b.']]
    assert rec['steps'] == ['Cuocete la pasta.', 'Scolatela.', 'Servite.']
    assert rec['kcal'] == 350 and rec['protein'] == 11 and rec['needs_review'] is True
    assert rec['source'] == 'GialloZafferano'


def test_normalize_url():
    assert normalize_url('https://Ricette.GialloZafferano.it//Pasta.html?x=1#a') == 'https://ricette.giallozafferano.it/Pasta.html'


# --- rete --------------------------------------------------------------------
class Response(io.BytesIO):
    def __init__(self, body, url, headers=None):
        super().__init__(body)
        self.url, self.headers = url, headers or {'Content-Type': 'text/html; charset=utf-8'}
    def geturl(self):
        return self.url
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


def test_fetch_text_ritenta_errori_temporanei():
    calls = []
    def opener(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise HTTPError(req.full_url, 503, 'busy', {}, None)
        return Response('Città'.encode('utf-8'), req.full_url)
    assert fetch_text(URL, opener=opener, sleep=lambda s: None) == 'Città'
    assert len(calls) == 3


def test_fetch_text_non_ritenta_blocchi_e_redirect_esterni():
    calls = []
    def forbidden(req, timeout):
        calls.append(1)
        raise HTTPError(req.full_url, 403, 'no', {}, None)
    with pytest.raises(FetchError) as err:
        fetch_text(URL, opener=forbidden, sleep=lambda s: None)
    assert err.value.status == 403 and not err.value.transient and len(calls) == 1
    with pytest.raises(FetchError):
        fetch_text(URL, opener=lambda r, timeout: Response(b'x', 'https://evil.example/'), sleep=lambda s: None)


# --- normalizzazione e audit ---------------------------------------------------
def base_record(**extra):
    rec = {'id': 1, 'name': 'Pasta e ceci', 'url': URL, 'source': 'GialloZafferano', 'servings': 4, 'time': 30,
           'image_url': 'https://www.giallozafferano.it/images/1-123/Pasta_650x433_wm.jpg', 'type': 'Primo',
           'ingredients_display': ['Pasta 320 g', 'Ceci 1 &frac12;'],
           'ingredients': [['Pasta', 320, 'g'], ['Ceci 1 &frac12;', None, 'da verificare']],
           'steps': ['Cuocete i ceci 1 .', 'Unite la pasta 2 .', 'Servite 3 .'],
           'kcal': 400, 'protein': 15, 'carbs': 60, 'fats': 9}
    rec.update(extra)
    return rec


def test_normalizza_record_e_audit():
    rec = base_record()
    errors, _ = check_record(rec, published=True)
    assert any(e.startswith('riferimenti_foto_nel_testo') for e in errors)
    assert any(e.startswith('quantita_da_verificare') for e in errors)
    fixed, changes = normalize_record(rec)
    assert fixed['ingredients'][1] == ['Ceci', 1.5, 'pezzi']
    assert fixed['steps'] == ['Cuocete i ceci.', 'Unite la pasta.', 'Servite.']
    assert check_record(fixed, published=True)[0] == []
    assert normalize_record(fixed)[1] == []  # idempotente


def test_normalizza_riallinea_schede_storiche():
    rec = base_record(ingredients_display=['Pasta'], ingredients=[['Fusilli', 320, 'g'], ['Sale', None, 'q.b.']])
    fixed, _ = normalize_record(rec)
    assert fixed['ingredients_display'] == ['Fusilli 320 g', 'Sale q.b.']


def test_audit_segnala_contorno_pubblicato_come_piatto():
    rec = base_record(name='Carote arrosto', type='Secondo')
    assert any(e.startswith('tipo_non_adatto_al_piano') for e in check_record(rec, published=True)[0])


# --- recupero immagini -------------------------------------------------------
def _media_records():
    cover = 'https://www.giallozafferano.it/images/236-23641/cover.jpg'
    base = {'source': 'GialloZafferano', 'image_url': cover, 'steps': ['Cuoci.', 'Servi.']}
    approved = dict(base, id=2, name='Pasta', url='https://ricette.giallozafferano.it/Pasta.html',
                    needs_review=False, validazione_automatica={'approved': True})
    pending = dict(base, id=3, name='Zuppa', url='https://ricette.giallozafferano.it/Zuppa.html',
                   needs_review=True, validazione_automatica={'approved': False})
    return approved, pending


def test_foto_cercate_anche_per_ricette_approvate_non_ancora_pubblicate(tmp_path):
    from importa_foto_passaggi import run
    approved, pending = _media_records()
    catalog = tmp_path / 'c.json'
    catalog.write_text(json.dumps([approved, pending]))
    published = tmp_path / 'p.json'
    published.write_text('[]')
    seen = []
    def fetcher(url):
        seen.append(url)
        raise FetchError('HTTP 404', 404)
    class Permit:
        def can_fetch(self, *_):
            return True
    run(catalog_path=catalog, limit=5, delay=0, fetcher=fetcher, policy=Permit(),
        published_only=True, published_path=published)
    assert seen == [approved['url']]  # la scheda in revisione non consuma richieste


def test_errore_di_rete_non_lascia_modifiche_parziali(tmp_path):
    from importa_foto_passaggi import run
    approved, _ = _media_records()
    catalog = tmp_path / 'c.json'
    catalog.write_text(json.dumps([approved]))
    class Permit:
        def can_fetch(self, *_):
            return True
    def fetcher(url):
        raise FetchError('Rete: timeout', transient=True)
    run(catalog_path=catalog, limit=5, delay=0, fetcher=fetcher, policy=Permit())
    assert json.loads(catalog.read_text()) == [approved]
