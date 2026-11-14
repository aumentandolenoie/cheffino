"""Completamento delle ricette in revisione: fonte, classificazione, unità, attrezzatura."""
import json

from app.ingredienti import deduce_quantity, parse_ingredient
from classifica_catalogo import classify_record
from sincronizza_fonte import apply_source, cook_minutes, run, same_recipe
from valida_catalogo import detect_tools, validate

URL = 'https://ricette.giallozafferano.it/Crema-di-lenticchie.html'


def raw(**extra):
    data = {'name': 'Crema di lenticchie', 'url': URL, 'category': 'Primi piatti', 'cost_text': 'Molto basso',
            'ingredients': ['Lenticchie secche di Castelluccio di Norcia 250', 'Carote 1', 'Sedano 1 costa',
                            'Acqua 1,5 l', 'Sale fino q.b.'],
            'steps': ['Sciacquate le lenticchie 1 e mettetele in pentola 2 .', 'Frullate 3 e servite.'],
            'yield_text': '4', 'prep_time': 'PT15M', 'cook_time': 'PT105M', 'total_time': 'PT120M',
            'nutrition': {'calories': '297,3 kcal', 'carbohydrateContent': '33,2 g', 'fatContent': '15,7 g'},
            'image_url': 'https://www.giallozafferano.it/images/1-100/Crema.jpg'}
    data.update(extra)
    return data


def record(**extra):
    rec = {'id': 500000, 'name': 'Crema di lenticchie', 'url': URL, 'source': 'GialloZafferano',
           'needs_review': True, 'servings': None, 'time': None, 'ingredients_display': ['Lenticchie 250'],
           'ingredients': [['Lenticchie 250', None, 'da verificare']], 'steps': ['vecchio testo'],
           'image_url': None, 'kcal': None}
    rec.update(extra)
    return rec


def test_apply_source_completa_la_scheda_in_modo_coerente():
    out, changed = apply_source(record(), raw())
    assert out['servings'] == 4 and out['time'] == 120 and out['kcal'] == 297.3
    assert out['source_category'] == 'Primi piatti' and out['source_cook_minutes'] == 105
    assert out['ingredients'][2] == ['Sedano', 1, 'coste']
    assert out['steps'] == ['Sciacquate le lenticchie e mettetele in pentola.', 'Frullate e servite.']
    assert out['needs_review'] is True  # nessuna approvazione qui
    assert 'servings' in changed and 'ingredients' in changed


def test_apply_source_non_disallinea_le_foto():
    groups = [['https://www.giallozafferano.it/images/1-100/Crema_1.jpg']]
    out, _ = apply_source(record(steps=['Uno.'], step_images=groups), raw())
    assert out['steps'] == ['Uno.'] and 'sincronizzazione_note' in out


def test_cook_minutes_distingue_zero_da_assente():
    assert cook_minutes('PT0M') == 0 and cook_minutes('PT20M') == 20 and cook_minutes(None) is None


def test_same_recipe():
    assert same_recipe('Pasta al pomodoro', 'Pasta al pomodoro e basilico')
    assert not same_recipe('Pollo al limone', 'Torta al cioccolato fondente')


def test_run_salva_e_salta_ricette_diverse(tmp_path):
    path = tmp_path / 'c.json'
    path.write_text(json.dumps([record(), record(id=500001, url=URL.replace('Crema', 'Altra'), name='Altra cosa')]))

    class Permit:
        def can_fetch(self, *_):
            return True

    def fetcher(url):
        return raw() if 'Crema' in url else raw(name='Torta al cioccolato')
    stats = run(path, limit=10, delay=0, fetcher=fetcher, policy=Permit())
    data = json.loads(path.read_text())
    assert stats['sincronizzate'] == 1 and stats['titolo_diverso_saltata'] == 1
    assert data[0]['source_sync_version'] == 1 and data[0]['servings'] == 4
    assert 'source_sync_version' not in data[1]


def test_unita_dedotte_solo_nei_casi_sicuri():
    siblings = [['Riso', 320, 'g'], ['Burro', 90, 'g']]
    assert deduce_quantity('Capperi sotto sale 30', siblings)[0] == ['Capperi sotto sale', 30, 'g']
    assert deduce_quantity('Lenticchie secche 250', [])[0] == ['Lenticchie secche', 250, 'g']
    assert deduce_quantity('Scorza di limone ½', [])[0] == ['Scorza di limone', 0.5, 'pezzi']
    assert deduce_quantity('Capperi sotto sale 10', siblings) is None
    assert deduce_quantity("Acciughe sott'olio 60", siblings) is None  # si contano
    assert parse_ingredient('Lattuga qualche foglia') == ['Lattuga', None, 'q.b.']
    assert parse_ingredient("Acciughe sott'olio filetti 2") == ["Acciughe sott'olio", 2, 'filetti']


def test_classificazione_con_categoria_della_fonte():
    assert classify_record({'name': 'Busiate trapanesi', 'source_category': 'Primi piatti'})[:2] == ('Primo', 'candidato')
    assert classify_record({'name': 'Carote glassate', 'source_category': 'Contorni'})[1] == 'escluso'
    assert classify_record({'name': 'Pizza in teglia', 'source_category': 'Lievitati'})[1] == 'candidato'
    assert classify_record({'name': 'Focaccia', 'source_category': 'Lievitati'})[1] == 'escluso'
    assert classify_record({'name': 'Insalata di ceci', 'source_category': 'Insalate', 'kcal': 402})[1] == 'candidato'
    assert classify_record({'name': 'Insalata di cetrioli', 'source_category': 'Insalate', 'kcal': 90})[1] == 'escluso'
    assert classify_record({'name': 'Pasta e fagioli'})[1] == 'candidato'  # senza categoria: titolo


def test_attrezzatura():
    assert detect_tools('Infornate a 180° per 20 minuti.') == ['Forno']
    assert detect_tools('Rosolatelo in padella, poi infornate.') == ['Forno', 'Fornelli']
    assert detect_tools('Verificate la cottura e sfornate.') == ['Forno']
    assert detect_tools('Tagliate e condite.', {'source_cook_minutes': 0}) == ['Nessuna cottura']
    assert detect_tools('Tagliate e condite.', {}) == []


def test_validazione_ricetta_cruda_completa():
    rec = {'name': 'Ceviche di branzino', 'source_category': 'Secondi piatti', 'source_cook_minutes': 0,
           'url': URL, 'image_url': 'https://x/y.jpg', 'servings': 4, 'time': 30,
           'ingredients': [['Branzino', 400, 'g'], ['Lime', 2, 'pezzi']], 'steps': ['Tagliate e marinate.']}
    result = validate(rec)
    assert result['approved'] and result['tools'] == ['Nessuna cottura'] and result['type'] == 'Secondo'


def test_ritiro_automatico_solo_per_categoria_della_fonte(tmp_path):
    import pytest
    from verifica_snapshot import compare
    base = {'url': URL, 'source': 'GialloZafferano', 'ingredients': [['A', 1, 'g']], 'needs_review': True}
    source = [dict(base, id=1, name='Carote glassate', source_category='Contorni'),
              dict(base, id=2, name='Pasta e ceci')]
    (tmp_path / 's.json').write_text(json.dumps(source))
    (tmp_path / 'n.json').write_text('[]')
    (tmp_path / 'p.json').write_text(json.dumps([{'id': 1, 'name': 'Carote glassate'}]))
    compare(tmp_path / 's.json', tmp_path / 'n.json', tmp_path / 'p.json')
    (tmp_path / 'p.json').write_text(json.dumps([{'id': 2, 'name': 'Pasta e ceci'}]))
    with pytest.raises(ValueError):
        compare(tmp_path / 's.json', tmp_path / 'n.json', tmp_path / 'p.json')


def test_frontend_ricette_senza_cottura():
    for path in ('frontend/index.html', 'index.html'):
        html = open(path, encoding='utf-8').read()
        assert "t!=='Nessuna cottura'&&!state.kitchen.includes(t)" in html
        assert 'function deducedNote' in html


def test_formato_blog_e_condimenti_senza_dose():
    assert parse_ingredient('360 g Pasta') == ['Pasta', 360, 'g']
    assert parse_ingredient('1 spicchio aglio') == ['aglio', 1, 'spicchio']
    assert parse_ingredient("olio extravergine d'oliva") == ["olio extravergine d'oliva", None, 'q.b.']
    assert parse_ingredient('Farina 00 200 g') == ['Farina 00', 200, 'g']


def test_antipasti_sostanziosi_e_leggeri():
    assert classify_record({'name': 'Polpo su crema di piselli', 'source_category': 'Antipasti', 'kcal': 519})[1] == 'candidato'
    assert classify_record({'name': 'Cestini di patate ripieni di salmone', 'source_category': 'Antipasti', 'kcal': 307})[1] == 'escluso'
    assert classify_record({'name': 'Pasta al forno', 'source_category': 'Pasta,Primi Piatti'})[:2] == ('Primo', 'candidato')


def test_riferimento_foto_prima_di_una_parentesi_e_composti():
    from pulisci_procedimenti import clean_steps
    steps = ['Fate bollire il farro 1 (circa 20 minuti), salate 2 . Scolate 3 .']
    assert clean_steps(steps)[0] == ['Fate bollire il farro (circa 20 minuti), salate. Scolate.']
    assert clean_steps(['Tagliate a pezzi (2 cm) e cuocete.'])[1] == 0
    base = {'name': 'Bavette con polpo', 'source_category': 'Primi piatti', 'url': URL, 'image_url': 'https://x/y.jpg',
            'servings': 4, 'time': 30, 'steps': ['Cuocete in padella.']}
    ok = dict(base, ingredients=[['Bavette', 320, 'g'], ['Fumetto di crostacei (preparato con gli scarti)', 1, 'l'],
                                 ['Pepe mix in grani', None, 'q.b.']])
    assert validate(ok)['approved']
    ko = dict(base, ingredients=[['Bavette', 320, 'g'], ['Mix di farine senza glutine', 100, 'g']])
    assert 'ingredienti_composti_non_identificati' in validate(ko)['reasons']
