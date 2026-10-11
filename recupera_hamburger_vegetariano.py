"""Recupera una galleria storica con serie fotografica univoca 1..18.

Esclusivamente la ricetta ID specificata; verifica identita' fonte, testo,
URL foto e ordine esatto. Non tocca ingredienti o validazione.
"""
import json
from pathlib import Path
from app.catalog import parse_recipe
from importa_foto_passaggi import (
    ImagesHTML, fetch_html, robots_policy, UA, steps_equivalent
)
from controlla_integrita_catalogo import image_id
from app.photo_policy import has_step_gallery

ID=182532426058049
NAME="Hamburger vegetariano autunnale"
URL="https://ricette.giallozafferano.it/Hamburger-vegetariano-autunnale.html"
SOURCE_ID="34213"
RANGES=((4,6),(7,9),(10,12),(13,15),(16,18))
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")

def plan(raw=RAW,pub=PUB,fetcher=fetch_html,policy=None):
    full=json.loads(Path(raw).read_text(encoding="utf-8"))
    approved=json.loads(Path(pub).read_text(encoding="utf-8"))
    if policy is None:policy=robots_policy()
    records=[r for r in full if r.get("id")==ID and r.get("name")==NAME and r.get("url")==URL]
    if len(records)!=1:raise ValueError("Scheda target non univoca")
    rec=records[0]
    snapshot=[r for r in approved if r.get("id")==ID]
    if snapshot and snapshot[0].get("url")!=URL:
        raise ValueError("Snapshot contiene ID con URL differente")
    if has_step_gallery(rec):return full,approved,False
    if not policy.can_fetch(UA,URL):raise ValueError("robots.txt non consente accesso")
    html=fetcher(URL)
    recipe=parse_recipe(html,URL)
    if recipe["name"]!=NAME or not steps_equivalent(recipe["steps"],rec["steps"]):
        raise ValueError("Procedimento della fonte non corrisponde")
    if len(rec["steps"])!=6 or image_id(rec.get("image_url"))!=SOURCE_ID:
        raise ValueError("Numero passi o copertina diversi dall'originale")
    p=ImagesHTML(NAME,URL);p.feed(html)
    if set(p.photos)!={1,2,3}:raise ValueError("Prima terna fotografica non confermata")
    ranges={}
    for a,b,url in p.strips:
        if (a,b) in RANGES:
            ranges.setdefault((a,b),set()).add(url)
    if set(ranges)!=set(RANGES):
        raise ValueError("Serie fotografica 4-18 incompleta")
    # Preferire una variante sola; tutte devono puntare alla stessa ricetta.
    strip_urls=[sorted(ranges[key])[0] for key in RANGES]
    groups=[[p.photos[n] for n in (1,2,3)]]+[[u] for u in strip_urls]
    photo_ids={image_id(url) for group in groups for url in group}
    if photo_ids!={SOURCE_ID}:raise ValueError("Identita' fotografica non corrispondente")
    for target in [rec]+snapshot:
        target["step_images"]=groups
        target["images_import_version"]=10
    print("GALLERIA RECUPERABILE",NAME,"foto",sum(map(len,groups)),
          "blocchi",len(groups),"gia_pubblicata",bool(snapshot),flush=True)
    return full,approved,True

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    full,approved,changed=plan(raw,pub,**kwargs)
    print("RECUPERO HAMBURGER VEGETARIANO",changed,"apply",apply,flush=True)
    if apply and changed:
        for path,data in ((Path(raw),full),(Path(pub),approved)):
            tmp=path.with_suffix(".vegetarian-tmp")
            tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            tmp.replace(path)
    return changed

if __name__=="__main__":
    import argparse
    cli=argparse.ArgumentParser()
    cli.add_argument("--apply",action="store_true")
    args=cli.parse_args()
    run(apply=args.apply)
