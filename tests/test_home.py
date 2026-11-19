"""Home: oggi in cima, ricerca visibile, barra in basso, impostazioni compatte."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_home_diretta_in_entrambe_le_versioni():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        i = html.index('function renderHome(main)')
        home = html[i:html.index('function renderBottomNav', i)]
        assert home.index('class="searchbox"') < home.index('todayMealsHtml()') < home.index('class="actiongrid"') \
            < home.index('id="pianoSettimana"') < home.index('class="settingsline"')
        assert 'summarybar' not in home
        assert "nav.className='bottomnav'" in html and "document.getElementById('bottomnav')?.remove()" in html
        assert '.topright .search-trigger{display:none}' in html


def test_niente_riquadri_nd_nella_ricetta():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        i = html.index('function showRecipe(')
        det = html[i:i + 3000]
        assert "val==='n.d.'" in det and ":'n.d.'}</b>" not in det
