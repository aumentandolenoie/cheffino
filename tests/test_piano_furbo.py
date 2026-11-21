"""Piano: tempi adatti al momento della settimana e budget dai prezzi dei prodotti."""
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
    script = '''let state={budget:'60',lunch:[0,1,2,3,4,5,6],dinner:[0,1,2,3,4,5,6],meals:'both',plan:{}};
function peopleCount(){return 2}
function requestedSlots(){return Array.from({length:14},(_,i)=>i)}
function chosenDays(){return [0,1,2,3,4,5,6]}
const R={};function getRecipe(id){return R[id]}
''' + js + '''
const t=[slotTimeLevel({time:25},'1-Pranzo'),slotTimeLevel({time:55},'1-Pranzo'),slotTimeLevel({time:380},'1-Pranzo'),
 slotTimeLevel({time:100},'2-Cena'),slotTimeLevel({time:380},'5-Pranzo'),slotTimeLevel({},'1-Pranzo')];
const b60=[perPortionBudget(),priceFits({price:2.5},1),priceFits({price:2},1),priceFits({price:3},1.5),priceFits({cost:'Elevato'},1),priceFits({},1)];
// piano oltre il budget: i pasti più cari passano a ricette più economiche
for(let i=0;i<20;i++)R[i]={id:i,price:i<4?6:1,time:20};
const plan={'0-Pranzo':0,'1-Pranzo':1,'2-Pranzo':2,'3-Pranzo':3};
state.budget='20';const prima=planCost(plan).total;
fitBudget(plan,Object.values(R));
const dopo=planCost(plan).total;
console.log(JSON.stringify({t,b60,prima,dopo,uniche:new Set(Object.values(plan)).size}));'''
    f = tmp_path / 'p.js'
    f.write_text(script)
    out = json.loads(subprocess.run(['node', str(f)], capture_output=True, text=True, check=True).stdout)
    assert out['t'] == [0, 1, 2, 1, 1, 1]
    assert abs(out['b60'][0] - 60 / 28) < 1e-9 and out['b60'][1:] == [False, True, True, False, True]
    assert out['prima'] == 48 and out['dopo'] <= 20 and out['uniche'] == 4
