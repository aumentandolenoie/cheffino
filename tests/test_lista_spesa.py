"""Lista della spesa settimanale: quantità sommate, arrotondate e divise per reparto."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _js(file):
    html = (ROOT / file).read_text()
    return html[html.index('const UNIT_SING='):html.index('function cartChecked')]


@pytest.mark.skipif(not shutil.which('node'), reason='node non disponibile')
@pytest.mark.parametrize('file', ['frontend/index.html', 'index.html'])
def test_quantita_e_reparti(file, tmp_path):
    casi_qty = [[13.333, 'g', ''], [6.67, 'g', ''], [0.333, 'kg', ''], [1234, 'g', ''], [0.5, 'l', ''],
                [1.33, 'pezzi', 'Limoni'], [0.67, 'spicchi', 'Aglio'], [2, 'spicchi', 'Aglio'],
                [0.5, 'pezzi', 'Uova'], [2.4, 'pezzi', 'Uova medie'], [3, 'cucchiai', 'Olio'], [None, 'q.b.', 'Sale']]
    casi_rep = ['Zucchine', 'Petto di pollo', 'Pecorino sardo', 'Passata di pomodoro', 'Brodo di pollo',
                'Fecola di patate', 'Spaghetti', 'Ceci lessati', 'Uova', 'Casizolu']
    script = _js(file) + f'''
const q={json.dumps(casi_qty)}.map(([a,b,c])=>fmtQty(a,b,c));
const r={json.dumps(casi_rep)}.map(aisleOf);
const p=["Sale fino","Olio extravergine d'oliva","Pepe nero","Peperoni rossi"].map(n=>PANTRY.test(n));
console.log(JSON.stringify({{q,r,p}}));'''
    f = tmp_path / 's.js'
    f.write_text(script)
    out = json.loads(subprocess.run(['node', str(f)], capture_output=True, text=True, check=True).stdout)
    assert out['q'] == ['15 g', '7 g', '330 g', '1,25 kg', '500 ml', '1 e ½', '½ spicchio', '2 spicchi',
                        '1', '3', '3 cucchiai', 'q.b.']
    assert out['r'] == ['🥬 Frutta e verdura', '🥩 Carne e pesce', '🧀 Latticini e uova', '🥫 Dispensa e scatolame',
                        '🥫 Dispensa e scatolame', '🍝 Pasta, riso, pane e farine', '🍝 Pasta, riso, pane e farine',
                        '🥫 Dispensa e scatolame', '🧀 Latticini e uova', '🧀 Latticini e uova']
    assert out['p'] == [True, True, True, False]


def test_home_apre_la_lista_della_settimana():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        assert 'onclick="openCart()"><div class="actionicon">🛍️</div><div><strong>Lista della spesa</strong>' in html
        assert 'function shareCart()' in html and 'navigator.share' in html
