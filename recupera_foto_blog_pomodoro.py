"""Recupera soltanto la galleria autentica dell'articolo blog ID 5.

Tre fotografie di preparazione inserite nel corpo del post, non nel
formato delle gallerie classiche. Nessuna foto e' inventata: ogni URL
deve comparire in un tag <img> della pagina sorgente ed essere immagine HTTP.
"""
import json
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen
from urllib.robotparser import RobotFileParser

from app.photo_policy import has_step_gallery, safe_photo

ID=5
URL="https://blog.giallozafferano.it/allacciateilgrembiule/pasta-pomodoro-basilico/"
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")
USER_AGENT="CheffinoPersonalProject/0.1 (source photo verification)"
IMAGES=(
    "pasta-pomodoro-basilico-2-720x184.jpg",
    "pasta-pomodoro-basilico-3-720x184.jpg",
    "pasta-pomodoro-basilico-4-720x184.jpg",
)
STEPS=[
    "Taglia i pomodorini e cuocili in padella con olio extravergine d'oliva e aglio.",
    "Dopo qualche minuto aggiungi la polpa di pomodoro e il basilico; prosegui la cottura del sugo.",
    "Cuoci la pasta in acqua salata, scolala al dente nel sugo, saltala con poca acqua di cottura e servi con basilico fresco.",
]

class InlinePhotos(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=set()
    def handle_starttag(self,tag,attrs):
        if tag!="img":return
        a=dict(attrs)
        for key in ("src","data-src","data-lazy-src","data-original"):
            url=a.get(key)
            if url and safe_photo(url):self.images.add(url)

def fetch_page(url=URL):
    req=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"text/html"})
    with urlopen(req,timeout=25) as res:
        if urlparse(res.geturl()).hostname!="blog.giallozafferano.it":
            raise ValueError("Redirect fuori dalla fonte")
        data=res.read(3_000_001)
    if len(data)>3_000_000:raise ValueError("Pagina troppo grande")
    return data.decode("utf-8","replace")

def check_image(url):
    req=Request(url,headers={"User-Agent":USER_AGENT,"Accept":"image/*","Range":"bytes=0-127"})
    with urlopen(req,timeout=15) as res:
        return (res.status in (200,206) and
                urlparse(res.geturl()).hostname=="blog.giallozafferano.it" and
                res.headers.get("Content-Type","").lower().startswith("image/"))

def source_permits():
    req=Request("https://blog.giallozafferano.it/robots.txt",headers={"User-Agent":USER_AGENT})
    with urlopen(req,timeout=20) as resp:
        if urlparse(resp.geturl()).hostname!="blog.giallozafferano.it":
            return False
        robots=resp.read(500001)
    if len(robots)>500000:return False
    policy=RobotFileParser()
    policy.parse(robots.decode("utf-8","replace").splitlines())
    return policy.can_fetch(USER_AGENT,URL)

def plan(raw=RAW,pub=PUB,fetcher=fetch_page,checker=check_image,policy=source_permits):
    raw_data=json.loads(Path(raw).read_text(encoding="utf-8"))
    snapshot=json.loads(Path(pub).read_text(encoding="utf-8"))
    records=[r for r in raw_data if r.get("id")==ID and r.get("url")==URL]
    if len(records)!=1:raise ValueError("Scheda di origine non univoca")
    rec=records[0]
    if has_step_gallery(rec):return raw_data,snapshot,False
    if not policy():raise ValueError("Fonte non consente accesso robots.txt")
    html=fetcher()
    text=unescape(re.sub(r"<[^>]+>"," ",html)).casefold()
    if not all(marker in text for marker in ("pasta pomodoro basilico",
                                             "tagliate i pomodorini",
                                             "scolate la pasta al dente",
                                             "servite calda")):
        raise ValueError("L'articolo originale non corrisponde alla preparazione prevista")
    parser=InlinePhotos();parser.feed(html)
    imgs=[]
    for filename in IMAGES:
        matching=[u for u in parser.images if urlparse(u).path.endswith("/"+filename)
                  and urlparse(u).path.startswith("/allacciateilgrembiule/wp-content/uploads/")]
        if len(matching)!=1:
            raise ValueError("Foto preparazione non univoca: "+filename)
        if not checker(matching[0]):
            raise ValueError("Foto della preparazione non verificabile: "+filename)
        imgs.append(matching[0])
    rec["steps_precedenti"]=list(rec["steps"])
    rec["steps"]=STEPS
    rec["step_images"]=[[u] for u in imgs]
    rec["images_import_version"]=10
    print("BLOG POMODORO: 3 fotografie verificate, 3 blocchi, ID=5",flush=True)
    return raw_data,snapshot,True

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    full,snapshot,changed=plan(raw,pub,**kwargs)
    print("RECUPERO BLOG",changed,"apply",apply,flush=True)
    if apply and changed:
        temp=Path(raw).with_suffix(".blog-tmp")
        temp.write_text(json.dumps(full,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        temp.replace(Path(raw))
    return changed

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    run(args.apply)
