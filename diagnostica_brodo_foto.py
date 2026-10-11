"""Diagnosi su ogni striscia originale e testo di Brodo/merluzzo."""
from collections import Counter
from urllib.parse import urlparse
from app.catalog import parse_recipe
from importa_foto_passaggi import ImagesHTML, fetch_html, robots_policy, UA, steps_equivalent
from pulisci_procedimenti import candidates

URL="https://ricette.giallozafferano.it/Brodo-di-prosciutto-crudo-merluzzo-sfogliato-con-pane-croccante-e-rapanelli.html"
TITLE="Brodo di prosciutto crudo, merluzzo sfogliato con pane croccante e rapanelli"

def inspect():
    policy=robots_policy()
    if not policy.can_fetch(UA,URL):raise ValueError("robots.txt")
    html=fetch_html(URL)
    source=parse_recipe(html,URL)
    p=ImagesHTML(TITLE,URL);p.feed(html)
    print("IMMAGINI",len(p.strips),"PASSAGGI",len(source["steps"]),flush=True)
    strong=weak=none=0
    for idx,(step,photo) in enumerate(zip(source["steps"],p.strips)):
        a,b,u=photo
        nums=[n for _,_,_,n in candidates([step])]
        possible=[n for n in nums if a<=n<=b]
        score=len(set(possible))
        if score>=2:strong+=1
        elif score==1:weak+=1
        else:none+=1
        stem=urlparse(u).path.split("/")[-1]
        print(f"STEP {idx+1} | strip={a}-{b} | match={sorted(set(possible))} | riferimenti={nums} | nome={stem}",flush=True)
    print("RIEPILOGO",dict(strong=strong,weak=weak,none=none),flush=True)

if __name__=="__main__":
    inspect()
