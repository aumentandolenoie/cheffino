"""Home: oggi in cima, ricerca visibile, barra in basso, impostazioni compatte."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_home_diretta_in_entrambe_le_versioni():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        i = html.index('function renderHome(main)')
        home = html[i:html.index('function renderBottomNav', i)]
        assert home.index('class="searchbox"') < home.index('todayMealsHtml()') < home.index('budgetCardHtml()') \
            < home.index('id="pianoSettimana"')
        assert 'summarybar' not in home and 'actiongrid' not in home and 'settingsline' not in home
        assert "nav.className='bottomnav'" in html and "document.getElementById('bottomnav')?.remove()" in html


def test_un_solo_accesso_per_funzione():
    """Niente doppioni: ricerca solo nella barra della home, preferenze solo con ⚙,
    spesa e volantino solo nella barra in basso."""
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        body = html[html.index('<body>'):]
        assert body.count('onclick="openRecipeSearch()"') == 1
        assert 'search-trigger' not in html
        i = html.index('function renderBottomNav')
        nav = html[i:html.index('\n', html.index('nav.innerHTML', i))]
        assert 'openCart()' in nav and 'openFlyer()' in nav and 'openRecipeSearch' not in nav
        home = html[html.index('function renderHome(main)'):i]
        assert 'openCart()' not in home and 'openFlyer()' not in home and 'openSettings()' not in home


def test_niente_riquadri_nd_nella_ricetta():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        i = html.index('function showRecipe(')
        det = html[i:i + 3000]
        assert "val==='n.d.'" in det and ":'n.d.'}</b>" not in det
