"""Proposte casuali che rispettano le scelte; ricette escluse per scelta non «in revisione»."""
import json
import shutil
import subprocess

import pytest

from app.public_catalog import public_catalog
from pubblica_catalogo import eligible
from valida_catalogo import process


def _grab(html, start, end):
    i = html.index(start)
    return html[i:html.index(end, i)]


@pytest.mark.parametrize('path', ['frontend/index.html', 'index.html'])
def test_tinder_e_piano_casuali_nel_rispetto_delle_scelte(path, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('node non disponibile')
    html = open(path, encoding='utf-8').read()
    code = '\n'.join([
        _grab(html, 'function filteredRecipes(options={}){', '\n// Gli stili sono preferenze'),
        _grab(html, 'function planRecipes(){', 'function getRecipe('),
        _grab(html, 'function recipePreferenceScore(r){', '// Priorità: GialloZafferano'),
        _grab(html, 'function requestedSlots(){', 'function planKeyUsed('),
    ])
    data = [{'id': e['id'], 'name': e['name'], 'autoValidated': bool((e.get('validazione_automatica') or {}).get('approved')),
             'requiredTools': (e.get('validazione_automatica') or {}).get('tools', []),
             'ings': [x[0] for x in e['ingredients']], 'style': e['style'], 'stili': e.get('stili', []), 'type': e['type'], 'time': e.get('time'),
             'detail': {'diets': e['diete']['compatibilita'], 'ingredients': e['ingredients']}} for e in public_catalog()]
    script = f"""
const recipeData={json.dumps(data)};const sourcedDetails={{}};recipeData.forEach(r=>sourcedDetails[r.id]=r.detail);
function recipeDetailData(r){{return sourcedDetails[r.id]||null}}
let state={{diet:['Nessuna'],avoid:[],styles:[],types:[],kitchen:['Fornelli','Forno'],likes:[],dislikes:[],favorites:[],
           meals:'both',lunch:[0,1,2,3,4,5,6],dinner:[0,1,2,3,4,5,6]}};
{code}
const out={{}};
state.swipeSeed=1;out.t1=tinderRecipes().slice(0,10).map(r=>r.id);
state.swipeSeed=2;out.t2=tinderRecipes().slice(0,10).map(r=>r.id);
state.planSeed=3;generateWeeklyPlan();out.p1=Object.values(state.plan);
state.planSeed=4;generateWeeklyPlan();out.p2=Object.values(state.plan);
state.diet=['Vegetariano'];state.dislikes=[out.p1[0]];state.planSeed=3;generateWeeklyPlan();
out.veg=Object.values(state.plan).map(id=>sourcedDetails[id].diets['Vegetariano']);out.vegIds=Object.values(state.plan);
console.log(JSON.stringify(out));
"""
    js = tmp_path / 't.js'
    js.write_text(script, encoding='utf-8')
    out = json.loads(subprocess.run([node, str(js)], capture_output=True, text=True, check=True).stdout)
    assert out['t1'] != out['t2']                                  # niente proposte iniziali fisse
    assert len(out['p1']) == 14 and len(set(out['p1'])) == 14      # nessun doppione nella settimana
    assert out['p1'] != out['p2']
    legacy = [i for i in out['p1'] if i < 1000]
    assert len(legacy) < 5                                         # le 11 schede storiche non dominano
    assert out['veg'] and set(out['veg']) == {'si'}                 # le esigenze sono sempre rispettate
    assert out['p1'][0] not in out['vegIds']                       # i «no» non tornano


def test_ricette_escluse_per_scelta_non_sono_in_revisione(tmp_path):
    base = {'url': 'https://ricette.giallozafferano.it/X.html', 'source': 'GialloZafferano', 'image_url': 'https://x/y.jpg',
            'servings': 4, 'time': 30, 'needs_review': True, 'steps': ['Cuocete in padella.'],
            'ingredients': [['Riso', 320, 'g'], ['Sale', None, 'q.b.']]}
    recs = [dict(base, id=1, name='Tiramisù', source_category='Dolci'),
            dict(base, id=2, name='Risotto', source_category='Primi piatti'),
            dict(base, id=3, name='Pasta con capperi', source_category='Primi piatti', servings=None)]
    path = tmp_path / 'c.json'
    path.write_text(json.dumps(recs))
    stats = process(path)
    data = {r['id']: r for r in json.loads(path.read_text())}
    assert stats['approvate'] == 1 and stats['escluse_dal_piano'] == 1 and stats['in_revisione'] == 1
    assert data[1]['esclusa_dal_piano']['tipo'] == 'Dolce o colazione'
    assert eligible(data[1]) == (False, 'esclusa_dal_piano')
    assert 'esclusa_dal_piano' not in data[3]


def test_api_non_invia_le_escluse_per_scelta():
    """Le escluse per scelta non devono comparire «in revisione» nell'app."""
    import importlib
    import app.main as m
    importlib.reload(m)
    rows = m.recipes()["recipes"]
    assert rows and not any(r.get("esclusa_dal_piano") for r in rows)
    in_revisione = [r for r in rows if r.get("needs_review")]
    assert len(in_revisione) < 40
