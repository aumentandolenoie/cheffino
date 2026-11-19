"""Piano: tempi adatti al momento della settimana e budget tramite il costo della fonte."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

import app.main as m

ROOT = Path(__file__).resolve().parent.parent


def test_api_invia_il_costo_della_fonte():
    rows = m.recipes()['recipes']
    assert sum(1 for r in rows if r.get('cost')) >= len(rows) * 0.7


@pytest.mark.skipif(not shutil.which('node'), reason='node non disponibile')
@pytest.mark.parametrize('file', ['frontend/index.html', 'index.html'])
def test_tempi_e_budget(file, tmp_path):
    html = (ROOT / file).read_text()
    js = html[html.index('function perPortionBudget'):html.index('function newSeed')]
    script = '''let state={budget:'60',lunch:[0,1,2,3,4,5,6],dinner:[0,1,2,3,4,5,6],meals:'both'};
function peopleCount(){return 2}
function requestedSlots(){return Array.from({length:14},(_,i)=>i)}
''' + js + '''
const t=[slotTimeLevel({time:25},'1-Pranzo'),slotTimeLevel({time:55},'1-Pranzo'),slotTimeLevel({time:380},'1-Pranzo'),
 slotTimeLevel({time:100},'2-Cena'),slotTimeLevel({time:380},'5-Pranzo'),slotTimeLevel({},'1-Pranzo')];
const b60=[perPortionBudget(),costAllowed({cost:'Elevato'},false),costAllowed({cost:'Medio'},true)];
state.budget='30';
const b30=[costAllowed({cost:'Medio'},true),costAllowed({cost:'Basso'},true)];
state.budget='300';
const b300=[costAllowed({cost:'Elevato'},false)];
console.log(JSON.stringify({t,b60,b30,b300}));'''
    f = tmp_path / 'p.js'
    f.write_text(script)
    out = json.loads(subprocess.run(['node', str(f)], capture_output=True, text=True, check=True).stdout)
    assert out['t'] == [0, 1, 2, 1, 1, 1]
    assert abs(out['b60'][0] - 60 / 28) < 1e-9 and out['b60'][1:] == [False, True]
    assert out['b30'] == [False, True]
    assert out['b300'] == [True]
