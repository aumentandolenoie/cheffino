"""Diagnostica solo lettura per capire perche' immagini e testo non corrispondono."""
import json
from difflib import SequenceMatcher
from importa_foto_passaggi import (fetch_html, robots_policy, UA, ImagesHTML,
                                  normalize, steps_equivalent)
from app.catalog import parse_recipe
from pulisci_procedimenti import clean_steps

TARGETS = ("Hamburger alle erbe aromatiche con verdure miste e patatine",
           "Pasta con datterini, capperi, stracciatella",
           "Pasta alla sorrentina")

def main():
    catalog=json.load(open("data/catalogo.json",encoding="utf-8"))
    policy=robots_policy()
    for name in TARGETS:
        rec=next(r for r in catalog if r["name"]==name)
        url=rec["url"]
        print("RICETTA:",name,"passaggi salvati",len(rec["steps"]),flush=True)
        if not policy.can_fetch(UA,url):
            print("SKIP robots");continue
        html=fetch_html(url)
        raw=parse_recipe(html,url)["steps"]
        clean,_=clean_steps(raw)
        p=ImagesHTML(name,url);p.feed(html)
        print("Fonte:",len(raw),"foto numerate:",len(p.photos),"strisce:",len(p.strips),
              "testi_equivalenti:",steps_equivalent(raw,rec["steps"]),flush=True)
        for i,(a,b) in enumerate(zip(clean,rec["steps"])):
            print(f"BLOCCO {i+1}, ratio={SequenceMatcher(None,normalize(a),normalize(b),autojunk=False).ratio():.2f}")
            print("  fonte:",normalize(a)[:230])
            print("  salvato:",normalize(b)[:230])
        print("STRISCE:",[(a,b) for a,b,_ in sorted(p.strips)][:35],flush=True)

if __name__=="__main__":
    main()
