"""Sola lettura: documenta i casi residui senza indovinare associazioni."""
import json
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urlparse
from app.public_catalog import public_catalog
from app.catalog import parse_recipe
from importa_foto_passaggi import fetch_html, robots_policy, UA, ImagesHTML, normalize
from pulisci_procedimenti import candidates

NAMES=("Brodo di prosciutto crudo, merluzzo sfogliato con pane croccante e rapanelli",
       "Hamburger alle erbe aromatiche con verdure miste e patatine",
       "Hamburger vegetariano autunnale",
       "Pasta al pomodoro e basilico")

class BlogMedia(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items=[]
        self.in_article=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ("article",): self.in_article+=1
        if tag=="img":
            self.items.append((a.get("alt",""),a.get("src") or a.get("data-src") or a.get("srcset") or ""))
    def handle_endtag(self,tag):
        if tag=="article":self.in_article=max(0,self.in_article-1)

def run():
    catalog={r["name"]:r for r in public_catalog()}
    policy=robots_policy()
    for name in NAMES:
        rec=catalog[name]
        url=rec["url"]
        print("\nRICETTA",name,"id",rec["id"],"pubblicata",not rec.get("needs_review"),flush=True)
        if urlparse(url).hostname != "ricette.giallozafferano.it":
            print("BLOG DA ESAMINARE MANUALMENTE:",url,flush=True)
            continue
        if not policy.can_fetch(UA,url):
            print("ROBOTS: blocco",flush=True);continue
        html=fetch_html(url)
        source=parse_recipe(html,url)
        parser=ImagesHTML(source["name"],url);parser.feed(html)
        hits=candidates(source["steps"])
        bystep=Counter(i for i,_a,_b,_n in hits)
        print("PASSI",len(source["steps"]),"FOTO NUMERATE",sorted(parser.photos)[:50],
              "STRIP", sorted(set((a,b) for a,b,_ in parser.strips))[:40],flush=True)
        print("NUMERI NEL TESTO",[(i+1,n) for i,_a,_b,n in hits][:90],flush=True)
        print("BLOCCHI CON NUMERI",dict(bystep),flush=True)
        print("STRIP URL",[(a,b,u) for a,b,u in parser.strips[:10]],flush=True)

if __name__=="__main__":
    run()
