"""Ripristino fotografico mirato della ricetta a sei sottoprocedimenti.

Verifica 23 strip originali nell'ordine di pagina, 23 blocchi nel testo,
6 gruppi consecutivi con sequenze numerate indipendenti e almeno un
riferimento numerico coerente in ogni blocco (>=16 forti).
"""
import json
from pathlib import Path
from urllib.parse import urlparse
from app.catalog import parse_recipe
from app.photo_policy import has_step_gallery
from importa_foto_passaggi import ImagesHTML, fetch_html, robots_policy, UA, steps_equivalent
from controlla_integrita_catalogo import image_id
from pulisci_procedimenti import candidates

ID=74528043300452
IMAGE_ID="18593"
NAME="Brodo di prosciutto crudo, merluzzo sfogliato con pane croccante e rapanelli"
URL="https://ricette.giallozafferano.it/Brodo-di-prosciutto-crudo-merluzzo-sfogliato-con-pane-croccante-e-rapanelli.html"
RAW=Path("data/catalogo.json")
PUB=Path("data/catalogo_pubblicato.json")
SECTIONS=(
    ("brodo",6),("polvere_di_prosciutto",2),("rapanelli_2",3),
    ("cialda_prezzemolo",7),("merluzzo",2),("composizione",3)
)

def plan(raw=RAW,pub=PUB,fetcher=fetch_html,policy=None):
    all_rows=json.loads(Path(raw).read_text(encoding="utf-8"))
    snapshot=json.loads(Path(pub).read_text(encoding="utf-8"))
    matches=[r for r in all_rows if r.get("id")==ID and r.get("name")==NAME and r.get("url")==URL]
    if len(matches)!=1:raise ValueError("Identità ricetta non univoca")
    rec=matches[0]
    if has_step_gallery(rec):return all_rows,snapshot,False
    if image_id(rec.get("image_url"))!=IMAGE_ID:raise ValueError("Identificativo copertina non corretto")
    if policy is None:policy=robots_policy()
    if not policy.can_fetch(UA,URL):raise ValueError("robots.txt non consente accesso")
    html=fetcher(URL)
    source=parse_recipe(html,URL)
    if source.get("name")!=NAME or not steps_equivalent(source.get("steps"),rec.get("steps")):
        raise ValueError("Testo originale modificato o non corrispondente")
    if len(rec["steps"])!=23:raise ValueError("Numero passaggi cambiato")
    gallery=ImagesHTML(NAME,URL)
    gallery.feed(html)
    strips=gallery.strips
    if len(strips)!=23:raise ValueError("Numero strisce diverso dalla fonte verificata")
    offset=0
    strong=0
    for prefix,count in SECTIONS:
        current=strips[offset:offset+count]
        if len(current)!=count:raise ValueError("Gruppo fotografico incompleto: "+prefix)
        for i,(start,end,url) in enumerate(current):
            want_start=1+3*i
            basename=urlparse(url).path.rsplit("/",1)[-1]
            if (start,end)!=(want_start,want_start+2):
                raise ValueError(f"Numerazione incoerente: {prefix} {i}")
            if not basename.startswith(IMAGE_ID+"_"+prefix+"_strip_"):
                raise ValueError(f"Sottoprocedimento errato: {basename}")
            if image_id(url)!=IMAGE_ID:raise ValueError("Foto di ricetta differente")
            step=source["steps"][offset+i]
            nums=[n for _,_a,_b,n in candidates([step])]
            overlap={n for n in nums if start<=n<=end}
            if not overlap:raise ValueError(f"Nessuna corrispondenza al passaggio {offset+i+1}")
            if len(overlap)>=2:strong+=1
        offset+=count
    if strong<16:raise ValueError("Verifiche incrociate insufficienti")
    groups=[[url] for _a,_b,url in strips]
    for target in [rec]+[x for x in snapshot if x.get("id")==ID and x.get("url")==URL]:
        target["step_images"]=groups
        target["images_import_version"]=10
    print(f"BRODO VERIFICATO: 23 gallerie in 6 sezioni, corrispondenze forti={strong}, senza match=0",flush=True)
    return all_rows,snapshot,True

def run(apply=False,raw=RAW,pub=PUB,**kwargs):
    full,snapshot,changed=plan(raw,pub,**kwargs)
    print("RECUPERO BRODO",changed,"apply",apply,flush=True)
    if apply and changed:
        for file,rows in ((Path(raw),full),(Path(pub),snapshot)):
            tmp=file.with_suffix(".brodo-tmp")
            tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+chr(10),encoding="utf-8")
            tmp.replace(file)
    return changed

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument("--apply",action="store_true")
    args=ap.parse_args()
    run(args.apply)
