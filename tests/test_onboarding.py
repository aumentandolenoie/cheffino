"""Onboarding in 5 passaggi: stesse preferenze di prima, meno schermate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_onboarding_cinque_passaggi():
    for f in ('frontend/index.html', 'index.html'):
        html = (ROOT / f).read_text()
        assert "const stepTitles=['Dove fai la spesa?','Per chi cucini?','Quando mangi a casa?','Cosa ti piace?','La tua cucina'];" in html
        i = html.index('function renderOnboard(main)')
        onb = html[i:html.index('\nfunction choice(', i)]
        # tutte le preferenze restano: supermercati, budget, persone, diete, giorni, tipi, stili, esclusi, strumenti
        for key in ("toggleArray('stores'", 'budgetInput', "setVal('people'", 'toggleDiet(', "dayButton(i,'lunch')",
                    "dayButton(i,'dinner')", 'toggleType(', 'toggleStyle(', 'ingredientChips(', "toggleArray('kitchen'"):
            assert key in onb, key
        assert "state.meals=state.lunch.length&&state.dinner.length?'both'" in html
        assert 'if(state.step>4)state.step=4' in onb
