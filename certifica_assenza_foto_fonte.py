"""Documenta assenza di galleria nella fonte, senza dedurla da parser parziale.

Certificazione possibile solo con HTML completo di ricetta originale,
senza riferimenti a foto del procedimento nell'HTML, nei dati strutturati
o negli URL delle immagini della ricetta. Il record di verifica rimane
associato a ID, URL e data. Non cambia approvazioni o ingredienti.
"""
import argparse
import json
import time
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlparse
from app.catalog import JsonLdParser, recipe_nodes, parse_recipe
from importa_foto_passaggi import ImagesHTML, fetch_html, robots_policy, UA, valid_image, normalize
from controlla_integrita_catalogo import image_id
from app.photo_policy import certified_source_absence, has_step_gallery

TARGETS={211658408928202:("22290", "Insalata di farro alla greca")}
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")
VERSION="gz-full-html-article-no-steps-v1"

class ImageElements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values=[]
    def handle_starttag(self,tag,attrs):
        if tag not in ("img","source"):return
        a=dict(attrs)
        for field in ("src","data-src","data-lazy-src","data-original","srcset","data-srcset"):
            value=a.get(field) or ""
            if value:self.values.append(value)

def structured_step_images(html):
    parsed=JsonLdParser()
    parsed.feed(html)
    def has_image(value):
        if isinstance(value,list):return any(has_image(x) for x in value)
        if isinstance(value,dict):
            if value.get("image") or value.get("thumbnailUrl"):return True
            return any(has_image(value.get(k)) for k in ("itemListElement",))
        return False
    for item in parsed.scripts:
        try:
            obj=json.loads(item)
        except (TypeError,ValueError):
            continue
        for node in recipe_nodes(obj):
            if has_image(node.get("recipeInstructions")):return True
    return False

def absence_verified(html,url,title,recipe_id):
    parsed=parse_recipe(html,url)
    if parsed.get("name")!=title or not parsed.get("steps"):
        return False
    gallery=ImagesHTML(title,url);gallery.feed(html)
    if gallery.photos or gallery.strips:
        return False
    if structured_step_images(html):
        return False
    # La directory /images/ricette/<gruppo>/<id>/ identifica immagini
    # dei passaggi. Se c'e' anche un solo riferimento nella pagina,
    # non si puo' dichiarare assenza.
    if f"/images/ricette/{int(recipe_id)//100}/{recipe_id}/" in html.lower():
        return False
    elements=ImageElements();elements.feed(html)
    for value in elements.values:
        if "strip_" in value.lower() or "step_" in value.lower():
            # Un contenuto generico estraneo non prova nulla; segnali di
            # galleria in HTML sono motivo sufficiente per non certificare.
            if recipe_id in value:
                return False
    return True

def plan(raw=RAW,pub=PUB,fetcher=fetch_html,policy=None,
         auto=False,limit=10,delay=2.5):
    all_rec=json.loads(Path(raw).read_text(encoding="utf-8"))
    published=json.loads(Path(pub).read_text(encoding="utf-8"))
    if not isinstance(all_rec,list) or not isinstance(published,list):
        raise ValueError("Cataloghi non validi")
    a={x["id"]:x for x in all_rec}
    b={x["id"]:x for x in published}
    if policy is None:policy=robots_policy()
    selected=[]
    if auto:
        # Includi soltanto candidate gia' approvate per gli altri criteri.
        # Non controllare il resto delle 256 ricette in revisione.
        for rec in all_rec:
            verdict=rec.get("validazione_automatica")
            if (not isinstance(verdict,dict) or verdict.get("approved") is not True
                    or rec.get("needs_review") or has_step_gallery(rec)
                    or certified_source_absence(rec)):
                continue
            identifier=image_id(rec.get("image_url"))
            if identifier and urlparse(rec.get("url","")).hostname=="ricette.giallozafferano.it":
                selected.append((rec["id"],identifier,None))
    else:
        selected=[(key,identifier,title) for key,(identifier,title) in TARGETS.items()]
    ok=[]
    attempted=0
    for id,source_id,title in selected:
        if attempted >= limit:break
        rec=a.get(id);pubrec=b.get(id)
        if not rec:
            raise ValueError("ID ricetta non trovato")
        if pubrec and rec.get("url")!=pubrec.get("url"):
            raise ValueError("Scheda differente nei cataloghi")
        url=rec["url"]
        if urlparse(url).hostname!="ricette.giallozafferano.it":
            if auto:continue
            raise ValueError("Fonte fuori dominio")
        if has_step_gallery(rec) or certified_source_absence(rec):
            continue
        if not policy.can_fetch(UA,url):
            print("ROBOTS BLOCCA",id,flush=True);continue
        try:
            html=fetcher(url)
            attempted+=1
            recipe=parse_recipe(html,url)
            source_title=recipe["name"]
            if title is not None and normalize(source_title)!=normalize(title):
                print("TITOLO DIVERSO",id,flush=True);continue
            if auto:
                # Non certificare un URL riutilizzato per un'altra ricetta.
                similarity=SequenceMatcher(None,normalize(source_title),normalize(rec.get("name")),autojunk=False).ratio()
                if similarity<0.8 or image_id(recipe.get("image_url"))!=source_id:
                    print("IDENTITA FONTE NON CERTA",id,flush=True);continue
            if not absence_verified(html,url,source_title,source_id):
                print("ASSENZA NON CERTIFICABILE",id,flush=True);continue
            proof={"status":"verified_absent","source_url":url,
                   "recipe_image_id":source_id,"verified_at":datetime.now(timezone.utc).isoformat(),
                   "method":VERSION}
            for target in (rec,pubrec):
                if target is not None:
                    target["step_photo_source_evidence"]=proof
            ok.append(id)
            print("ASSENZA DOCUMENTATA",id,source_title,proof,flush=True)
        except Exception as exc:
            print("VERIFICA FONTE FALLITA",id,type(exc).__name__,str(exc)[:200],flush=True)
        if delay and auto:
            time.sleep(delay)
    print("RICETTE FONTI CONTROLLATE",attempted,"certificate",len(ok),flush=True)
    return all_rec,published,ok

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    all_rec,published,ids=plan(raw,pub,**kwargs)
    print("FONTI VERIFICATE SENZA GALLERIA",len(ids),"apply",apply,flush=True)
    if apply and ids:
        for path,records in ((Path(raw),all_rec),(Path(pub),published)):
            temp=path.with_suffix(".proof-tmp")
            temp.write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            temp.replace(path)
    return ids

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    p.add_argument("--auto",action="store_true",help="Controlla le nuove candidate approvate senza foto")
    p.add_argument("--limit",type=int,default=10)
    p.add_argument("--delay",type=float,default=2.5)
    args=p.parse_args()
    if not 1<=args.limit<=35 or not 0<=args.delay<=10:
        p.error("limit 1..35 e delay 0..10")
    run(args.apply,auto=args.auto,limit=args.limit,delay=args.delay)
