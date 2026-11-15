"""Ricerca ricette: parole in qualsiasi ordine, senza preposizioni, plurali e refusi."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CATALOGO = [
    {'id': 1, 'name': 'Frittata di spinaci', 'ings': ['Uova', 'Spinaci', 'Parmigiano Reggiano DOP'], 'type': 'Secondo'},
    {'id': 2, 'name': 'Pollo al limone', 'ings': ['Petto di pollo', 'Limoni'], 'type': 'Secondo'},
    {'id': 3, 'name': 'Polpo alla griglia', 'ings': ['Polpo', 'Limone'], 'type': 'Secondo'},
    {'id': 4, 'name': 'Pasta e zucchine', 'ings': ['Pasta', 'Zucchine'], 'type': 'Primo'},
    {'id': 5, 'name': 'Risotto ai funghi porcini', 'ings': ['Riso', 'Funghi porcini'], 'type': 'Primo'},
    {'id': 6, 'name': 'Torta salata con zucchine', 'ings': ['Pasta sfoglia', 'Zucchine', 'Uova'], 'type': 'Piatto unico'},
]
CASI = [
    ('frittata spinaci', [1]), ('spinaci frittata', [1]), ('frittata di spinaci', [1]),
    ('fritata spinaci', [1]), ('frittat', [1]), ('spinacio', [1]),
    ('pollo limone', [2]), ('fungo risotto', [5]), ('zucchina', [4, 6]), ('pasta zucchine', [4, 6]),
    ('4', [4]),
]


def _funzioni(html):
    js = html[html.index('function normalizeRecipeQuery'):html.index('function openRecipeSearch')]
    return js


@pytest.mark.skipif(not shutil.which('node'), reason='node non disponibile')
@pytest.mark.parametrize('file', ['frontend/index.html', 'index.html'])
def test_ricerca(file, tmp_path):
    js = _funzioni((ROOT / file).read_text())
    script = js + f'''
const list={json.dumps([{**r, 'review': False} for r in CATALOGO])};
const out={{}};for(const q of {json.dumps([q for q, _ in CASI])})out[q]=searchRecipes(list,q).items.map(r=>r.id);
console.log(JSON.stringify(out));'''
    p = tmp_path / 's.js'
    p.write_text(script)
    out = json.loads(subprocess.run(['node', str(p)], capture_output=True, text=True, check=True).stdout)
    for q, attesi in CASI:
        assert out[q][:len(attesi)] == attesi, (q, out[q])
    assert out['pollo limone'] == [2]  # «polpo» non è un refuso di «pollo»
