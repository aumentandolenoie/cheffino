"""Compatibilità con le esigenze alimentari (app/diete.py)."""
import pytest

from app.diete import assess_recipe, classify_ingredient


def recipe(*ingredients, name='Ricetta', steps=('Cuocete tutto.',)):
    return {'name': name, 'steps': list(steps), 'ingredients': [[x, 1, 'g'] for x in ingredients]}


def diets(*ingredients, **kw):
    return assess_recipe(recipe(*ingredients, **kw))['compatibilita']


def test_pasta_al_pomodoro_vegana_ma_non_senza_glutine():
    d = diets('Spaghetti', 'Passata di pomodoro', 'Basilico', "Olio extravergine d'oliva", 'Sale fino')
    assert d == {'Vegetariano': 'si', 'Vegano': 'si', 'Senza Glutine': 'no', 'Senza Lattosio': 'si'}


def test_formaggi_e_uova_vegetariani_non_vegani_ne_senza_lattosio():
    d = diets('Uova', 'Spinaci', 'Parmigiano Reggiano DOP', 'Sale')
    assert d['Vegetariano'] == 'si' and d['Vegano'] == 'no'
    assert d['Senza Lattosio'] == 'no' and d['Senza Glutine'] == 'si'


@pytest.mark.parametrize('ingredient', ['Guanciale', 'Petto di pollo', 'Acciughe sott\'olio', 'Gelatina in fogli',
                                        'Brodo di carne', 'Salsa Worcestershire', 'Mazzancolle (da pulire)'])
def test_carne_e_pesce_esclusi_per_vegetariani(ingredient):
    assert diets('Riso carnaroli', ingredient)['Vegetariano'] == 'no'


def test_sostituti_dichiarati():
    d = diets('Fusilli senza glutine', 'Latte di soia', 'Burro di arachidi', 'Farina di riso', 'Tofu')
    assert d == {'Vegetariano': 'si', 'Vegano': 'si', 'Senza Glutine': 'si', 'Senza Lattosio': 'si'}
    assert diets('Ricotta senza lattosio', 'Pomodori')['Senza Lattosio'] == 'si'


def test_falsi_amici():
    assert 'pesce' not in classify_ingredient('Calamarata')          # formato di pasta
    assert 'pesce' not in classify_ingredient('Pecorino sardo')
    assert 'carne' not in classify_ingredient('Ricotta di pecora')
    assert 'glutine' not in classify_ingredient('Patate per gnocchi e purè')
    assert 'glutine' not in classify_ingredient('Burro (per ungere i panini)')
    assert 'glutine' not in classify_ingredient('Lievito di birra fresco')
    assert 'glutine' not in classify_ingredient('Grano saraceno')


def test_prodotti_dubbi_restano_esclusi():
    assert diets('Riso', 'Brodo vegetale')['Senza Glutine'] == 'incerto'
    assert diets('Riso', 'Salsiccia')['Senza Lattosio'] == 'incerto'
    assert diets('Pasta Sfoglia rotonda', 'Zucchine')['Vegetariano'] == 'incerto'
    assert diets('Riso', 'Cioccolato fondente')['Vegano'] == 'incerto'


def test_ingredienti_citati_solo_nel_testo():
    d = diets('Merluzzo', 'Sale', name='Merluzzo con pane croccante')
    assert d['Senza Glutine'] == 'incerto'
    d = diets('Zucchine', 'Sale', steps=['Saltate con il burro.'])
    assert d['Senza Lattosio'] == 'incerto' and d['Vegano'] == 'incerto'
    assert diets('Zucchine', steps=['Completate con una macinata di pepe.'])['Vegano'] == 'si'


def test_senza_ingredienti_niente_promesse():
    assert set(assess_recipe({'name': 'X', 'ingredients': []})['compatibilita'].values()) == {'incerto'}


def test_api_espone_le_diete():
    from app.public_catalog import public_catalog
    rows = public_catalog()
    assert rows and all(set(r['diete']['compatibilita']) == {'Vegetariano', 'Vegano', 'Senza Glutine', 'Senza Lattosio'}
                        for r in rows)


def test_frontend_non_esclude_piu_tutte_le_ricette_con_una_dieta():
    for path in ('frontend/index.html', 'index.html'):
        html = open(path, encoding='utf-8').read()
        assert "if(diets.some(d=>d!=='Nessuna'))return false;" not in html
        assert "dietInfo[d]!=='si'" in html
