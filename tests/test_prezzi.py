"""Costo delle ricette stimato dai prezzi medi dei prodotti (app/prezzi.py)."""
import app.main as m
from app.prezzi import costo_ingrediente, stima_ricetta, voce_listino


def test_listino_riconosce_gli_ingredienti_comuni():
    for nome in ("Spaghetti", "Olio extravergine d'oliva", "Petto di pollo", "Zucchine", "Parmigiano Reggiano DOP (da grattugiare)",
                 "Uova medie", "Pomodorini ciliegino", "Passata di pomodoro", "Ceci precotti (peso sgocciolato)", "Mezzi rigatoni"):
        assert voce_listino(nome), nome
    assert voce_listino("Ingrediente inesistente xyz") is None


def test_costo_per_unita():
    assert costo_ingrediente("Spaghetti", 500, "g") == 1.0
    assert abs(costo_ingrediente("Uova", 2, "pezzi") - 0.605) < 1e-9
    assert costo_ingrediente("Sale fino", None, "q.b.") is None
    assert costo_ingrediente("Acqua", 1, "l") == 0
    assert costo_ingrediente("Spaghetti", 1, "unità sconosciuta") is None


def test_stima_ricetta_prudente():
    r = {"servings": 4, "ingredients": [["Spaghetti", 320, "g"], ["Pomodorini ciliegino", 400, "g"],
                                        ["Sale fino", None, "q.b."], ["Basilico", 4, "foglie"]]}
    s = stima_ricetta(r)
    assert s and s["copertura"] == 1 and 0.5 < s["porzione"] < 1
    # troppi ingredienti senza prezzo: nessuna stima invece di un numero sbagliato
    assert stima_ricetta({"servings": 4, "ingredients": [["Xyz", 100, "g"], ["Abc", 50, "g"], ["Spaghetti", 300, "g"]]}) is None
    assert stima_ricetta({"servings": None, "ingredients": [["Spaghetti", 300, "g"]]}) is None


def test_api_invia_il_prezzo_stimato():
    payload = m.recipes()
    rows = payload["recipes"]
    assert payload["listino_prezzi"]
    con_prezzo = [r for r in rows if r.get("prezzo")]
    assert len(con_prezzo) >= len(rows) * 0.9
    for r in con_prezzo:
        assert 0.1 < r["prezzo"]["porzione"] < 25, (r["name"], r["prezzo"])
