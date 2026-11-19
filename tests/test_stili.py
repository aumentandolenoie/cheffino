"""Stili scelti nell'onboarding: calcolati dai dati della fonte, mai inventati."""
import json
from pathlib import Path

from app.stili import STILI, proteico, stili

ROOT = Path(__file__).resolve().parent.parent


def rec(**kw):
    base = {'name': 'Ricetta', 'time': 40, 'steps': ['a', 'b', 'c'], 'servings': 4,
            'ingredients': [['Zucchine', 400, 'g']], 'kcal': None, 'fats': None, 'source_cost': 'Medio'}
    base.update(kw)
    return base


def test_veloci_economiche_calorie():
    assert 'Veloci e facili' in stili(rec(time=25))
    assert 'Veloci e facili' not in stili(rec(time=25, steps=['x'] * 12))
    assert 'Veloci e facili' not in stili(rec(time=45))
    assert 'Economiche' in stili(rec(source_cost='Basso'))
    assert 'Economiche' not in stili(rec(source_cost='Elevato'))
    assert 'Poche calorie' in stili(rec(kcal=380))
    assert 'Poche calorie' not in stili(rec(kcal=None))


def test_salutari_esclude_fritture_e_grassi():
    assert 'Piatti salutari' in stili(rec(kcal=500, fats=15))
    assert 'Piatti salutari' not in stili(rec(kcal=500, fats=35))
    assert 'Piatti salutari' not in stili(rec(name='Baccalà fritto', kcal=500, fats=15))


def test_proteici_da_proteine_o_quantita():
    assert proteico(rec(protein=30))
    assert not proteico(rec(protein=12, ingredients=[['Petto di pollo', 800, 'g']]))
    assert proteico(rec(ingredients=[['Petto di pollo', 600, 'g'], ['Limoni', 2, 'pezzi']]))
    assert not proteico(rec(ingredients=[['Pancetta', 100, 'g'], ['Pasta', 320, 'g']]))
    assert proteico(rec(servings=2, ingredients=[['Uova', 4, 'pezzi'], ['Spinaci', 300, 'g']]))
    assert proteico(rec(ingredients=[['Ceci secchi', 0.5, 'kg']]))


def test_famiglia_classici_takeaway():
    assert 'Per tutta la famiglia' in stili(rec(time=40))
    assert 'Per tutta la famiglia' not in stili(rec(time=40, ingredients=[['Vino bianco', 100, 'ml']]))
    assert 'Per tutta la famiglia' not in stili(rec(time=40, name='Pasta piccante'))
    assert 'Classici italiani' in stili(rec(name='Baccalà alla vicentina'))
    assert 'Classici italiani' in stili(rec(name='Spaghetti alla carbonara'))
    assert 'Classici italiani' not in stili(rec(name='Pasta con pesto di asparagi e speck'))
    assert 'Takeaway fatto in casa' in stili(rec(name='Burger di salmone'))


def test_catalogo_pubblicato_quasi_tutto_classificato():
    d = json.loads((ROOT / 'data' / 'catalogo_pubblicato.json').read_text())
    senza = [r['name'] for r in d if not stili(r)]
    assert len(senza) <= len(d) * 0.15
    for s in STILI:
        assert any(s in stili(r) for r in d), s


def test_stili_uguali_all_onboarding_e_usati_dal_frontend():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        for s in STILI:
            assert f"['{s}'," in html
        assert 'Da classificare' not in html
        assert "if(!options.relaxStyles&&state.styles.length&&!styleHits(r))return false;" in html
        assert 'Math.min(2,styleHits(r))*1.5' in html
