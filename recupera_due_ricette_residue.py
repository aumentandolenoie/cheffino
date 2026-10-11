"""Recupera due schede storiche: ID 0 e 26, usando soltanto immagini originali.

Non considera affidabile la copertina JSON-LD se non appartiene alla
stessa ricetta delle foto: ricerca la copertina visibile nel corpo pagina
con alt, dominio e identificativo fotografico coerenti.
"""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from importa_foto_passaggi import (
    ImagesHTML, UA, associate_steps, fetch_html, image_from_attrs,
    normalize, robots_policy, valid_image,
)
from app.catalog import parse_recipe
from controlla_integrita_catalogo import image_id
from pulisci_procedimenti import clean_steps

IDS={0: ("Pasta zucchine e ricotta","28200"),
     26: ("Pollo al limone","23580")}
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")

class MainImages(HTMLParser):
    def __init__(self, title, url):
        super().__init__()
        self.title=normalize(title)
        self.url=url
        self.items=[]
    def handle_starttag(self, tag, attrs):
        if tag!="img":return
        a=dict(attrs)
        if normalize(a.get("alt"))==self.title:
            u=image_from_attrs(a,self.url)
            if u:self.items.append(u)

def choose_cover(html,title,url,expected_id):
    scan=MainImages(title,url);scan.feed(html)
    matching=[u for u in scan.items if image_id(u)==expected_id]
    # Immagine di copertina grande, non icona o galleria passaggi.
    main=[u for u in matching if "images/" in u and "/images/ricette/" not in u
          and "_780x520" in urlparse(u).path]
    if len(set(main))==1:
        return main[0]
    # Alcune pagine GZ visualizzano soltanto la copertina 450x300.
    # Non costruiamo varianti 780x520 che potrebbero non esistere.
    fallback=[u for u in matching if "/images/ricette/" not in u and
              "_450x300" in urlparse(u).path]
    if len(set(fallback))==1:
        return fallback[0]
    raise ValueError("Copertina visibile con ID corretto non univoca: "+str(matching[:8]))

def plan(raw=RAW,pub=PUB,fetcher=fetch_html,policy=None):
    full=json.loads(Path(raw).read_text(encoding="utf-8"))
    snapshot=json.loads(Path(pub).read_text(encoding="utf-8"))
    if not isinstance(full,list) or not isinstance(snapshot,list):
        raise ValueError("Cataloghi malformati")
    by_full={r["id"]:r for r in full}
    by_snap={r["id"]:r for r in snapshot}
    if policy is None:policy=robots_policy()
    completed=[]
    for recipe_id,(title,source_image_id) in IDS.items():
        original=by_full.get(recipe_id)
        published=by_snap.get(recipe_id)
        if not original or not published or original.get("url")!=published.get("url"):
            raise ValueError("Scheda pubblicata e catalogo discordanti: "+str(recipe_id))
        if any(any(isinstance(g,list) and g for g in (r.get("step_images") or []))
               for r in (original,published)):
            continue
        url=original["url"]
        if urlparse(url).hostname!="ricette.giallozafferano.it":
            raise ValueError("Dominio originale non valido")
        if not policy.can_fetch(UA,url):
            print("ROBOT NON PERMETTE",recipe_id,flush=True);continue
        html=fetcher(url)
        parsed=parse_recipe(html,url)
        if normalize(parsed["name"])!=normalize(title):
            raise ValueError("Titolo fonte diverso dalla ricetta attesa "+str(recipe_id))
        photos=ImagesHTML(title,url);photos.feed(html)
        raw_steps=parsed["steps"]
        cleaned,_=clean_steps(raw_steps)
        groups,method=associate_steps(photos,raw_steps,len(cleaned))
        if not cleaned or not groups or len(groups)!=len(cleaned):
            print("NO MATCH",recipe_id,len(cleaned),len(photos.photos),flush=True);continue
        step_ids={image_id(u) for group in groups for u in group}
        if step_ids!={source_image_id}:
            print("ID FOTO NON COERENTI",recipe_id,step_ids,flush=True);continue
        cover=choose_cover(html,title,url,source_image_id)
        if not valid_image(cover,url):
            raise ValueError("Copertina non valida")
        for r in (original,published):
            r["steps_precedenti"]=list(r["steps"])
            r["steps"]=cleaned
            r["steps_raw"]=raw_steps
            r["steps_clean"]=cleaned
            r["step_images"]=groups
            if r.get("image_url")!=cover:
                r["image_url_precedente"]=r.get("image_url")
                r["image_url"]=cover
            r["images_import_version"]=10
        completed.append(recipe_id)
        print("RECUPERABILE",recipe_id,original["name"],
              "foto",sum(map(len,groups)),"passi",len(cleaned),"copertina",cover,flush=True)
    return full,snapshot,completed

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    full,snapshot,done=plan(raw,pub,**kwargs)
    print("RIPRISTINO RESIDUE",len(done),"su",len(IDS),"apply",apply,flush=True)
    if apply and done:
        # Il workflow conserva il git history precedente e verifica lo snapshot.
        for file,data in ((Path(raw),full),(Path(pub),snapshot)):
            temp=file.with_suffix(".safe-tmp")
            temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            temp.replace(file)
    return done

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    run(args.apply)
