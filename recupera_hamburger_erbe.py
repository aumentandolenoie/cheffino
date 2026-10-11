"""Recupera 12 strisce da due sottoprocedimenti originali (panino e ripieno).

Il formato della fonte riparte da foto 1 nel secondo sottoprocedimento.
Richiede un match strutturale completo, inclusa la tripletta numerata
di ciascun passaggio. In caso di dubbio non modifica nessun dato.
"""
import json
from pathlib import Path
from controlla_integrita_catalogo import image_id
from app.catalog import parse_recipe
from app.photo_policy import has_step_gallery
from importa_foto_passaggi import (
    ImagesHTML, UA, fetch_html, robots_policy, steps_equivalent
)
from pulisci_procedimenti import candidates

ID=149444968096049
TITLE="Hamburger alle erbe aromatiche con verdure miste e patatine"
URL="https://ricette.giallozafferano.it/Hamburger-alle-erbe-aromatiche-con-verdure-miste-e-patatine.html"
IMAGE_ID="15458"
RANGES=tuple((n,n+2) for n in (1,4,7,10,13,16))
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")

def plan(raw=RAW,pub=PUB,fetcher=fetch_html,policy=None):
    full=json.loads(Path(raw).read_text(encoding="utf-8"))
    snapshot=json.loads(Path(pub).read_text(encoding="utf-8"))
    recs=[r for r in full if r.get("id")==ID and r.get("url")==URL and r.get("name")==TITLE]
    if len(recs)!=1:raise ValueError("ID / URL / titolo fonte non univoci")
    rec=recs[0]
    if has_step_gallery(rec):return full,snapshot,False
    if image_id(rec.get("image_url"))!=IMAGE_ID:raise ValueError("Copertina fonte incoerente")
    if policy is None:policy=robots_policy()
    if not policy.can_fetch(UA,URL):raise ValueError("robots.txt blocca la pagina")
    html=fetcher(URL)
    parsed=parse_recipe(html,URL)
    if parsed.get("name")!=TITLE or not steps_equivalent(parsed.get("steps"),rec.get("steps")):
        raise ValueError("Procedimento o titolo diversi dalla fonte")
    if len(rec["steps"])!=12:raise ValueError("Struttura procedimento diversa")
    gallery=ImagesHTML(TITLE,URL)
    gallery.feed(html)
    strips=gallery.strips
    if len(strips)!=12:raise ValueError(f"Numero di strisce inatteso: {len(strips)}")
    for index, (start,end,url) in enumerate(strips):
        expected=RANGES[index%6]
        if (start,end)!=expected or image_id(url)!=IMAGE_ID:
            raise ValueError(f"Striscia non corrispondente al gruppo {index+1}: {(start,end)}")
        # 6 passi per la preparazione dei panini e 6 per ripieno/patatine.
        nums=[n for step,_a,_b,n in candidates([parsed["steps"][index]])]
        ordered=iter(nums)
        if not all(any(v==required for v in ordered) for required in range(start,end+1)):
            raise ValueError(f"Numerazione non univoca nel passaggio {index+1}: {nums}")
    groups=[[entry[2]] for entry in strips]
    for row in [rec]+[r for r in snapshot if r.get("id")==ID and r.get("url")==URL]:
        row["step_images"]=groups
        row["images_import_version"]=10
    print("HAMBURGER ERBE VERIFICATO: 12 strisce, 12 passi, due sequenze 1-18",flush=True)
    return full,snapshot,True

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    full,snapshot,changed=plan(raw,pub,**kwargs)
    print("RECUPERO HAMBURGER ERBE",changed,"apply",apply,flush=True)
    if apply and changed:
        for file,rows in ((Path(raw),full),(Path(pub),snapshot)):
            tmp=file.with_suffix(".erbe-tmp")
            tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            tmp.replace(file)
    return changed

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    run(args.apply)
