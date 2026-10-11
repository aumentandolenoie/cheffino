"""Confronto non distruttivo tra catalogo disponibile in Cheffino e snapshot candidato.

Non approva nuovi record, non esegue download e non modifica file.
Un record pubblicato in precedenza non deve sparire in silenzio.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from app.photo_policy import publishable_step_photos

def current_visible(rec):
    verdict=rec.get("validazione_automatica")
    if rec.get("needs_review") or (isinstance(verdict,dict) and verdict.get("approved") is False):
        return False
    # Una nuova ricetta con approvazione formale ma senza galleria o
    # prova della fonte non e' visibile sotto le nuove regole.
    if isinstance(verdict,dict) and not publishable_step_photos(rec):
        return False
    return (isinstance(rec.get("id"), int) and bool(rec.get("name")) and
            isinstance(rec.get("url"), str) and rec["url"].startswith("https://") and
            bool(rec.get("source")) and isinstance(rec.get("ingredients"), list) and
            len(rec["ingredients"]) > 0)

def _allowed_photo_review(path, source_records):
    if path is None:
        return set()
    manual=json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manual,list):
        raise ValueError("Elenco esclusioni foto non valido")
    data={r.get("id"):r for r in source_records}
    allowed=set()
    reasons={"galleria_presente_nella_fonte_non_abbinata",
             "foto_nel_corpo_del_blog_non_ancora_abbinate"}
    for item in manual:
        if not isinstance(item,dict) or item.get("reason") not in reasons:
            raise ValueError("Motivo della sospensione non riconosciuto")
        rid=item.get("id")
        rec=data.get(rid)
        if (rid in allowed or not rec or rec.get("url")!=item.get("url")
                or publishable_step_photos(rec)):
            raise ValueError("Sospensione fotografica non valida: "+str(rid))
        allowed.add(rid)
    return allowed


def compare(source, snapshot, previous=None, approved_photo_review=None):
    source_data=json.loads(Path(source).read_text(encoding="utf-8"))
    published=json.loads(Path(snapshot).read_text(encoding="utf-8"))
    if not isinstance(source_data,list) or not isinstance(published,list):
        raise ValueError("Cataloghi non validi")
    old={rec["id"]:rec for rec in source_data if current_visible(rec)}
    new={rec["id"]:rec for rec in published}
    allowed=_allowed_photo_review(approved_photo_review,source_data)
    missing=[rec for rid,rec in old.items() if rid not in new]
    not_authorized=[rec for rec in missing if rec["id"] not in allowed]
    extra=[rec for rid,rec in new.items() if rid not in old]
    print(f"Confronto pubblicazione: catalogo={len(source_data)}; visibili_prima={len(old)}; snapshot={len(new)}; perse={len(missing)}; aggiunte={len(extra)}")
    for rec in missing[:20]:
        print(f"PERDITA DA ESAMINARE: {rec.get('name')} | id={rec.get('id')}")
    if extra:
        for rec in extra[:20]:
            print(f"NUOVA DA ESAMINARE: {rec.get('name')} | id={rec.get('id')}")
    if previous is not None and Path(previous).exists():
        past = json.loads(Path(previous).read_text(encoding="utf-8"))
        if not isinstance(past, list):
            raise ValueError("Snapshot precedente non valido")
        old_published = {rec.get("id"): rec for rec in past}
        lost_previous = [rec for rid, rec in old_published.items() if rid not in new]
        lost_unauthorized=[rec for rec in lost_previous if rec.get("id") not in allowed]
        if lost_unauthorized:
            for rec in lost_unauthorized[:20]:
                print(f"PERDITA SNAPSHOT PRECEDENTE: {rec.get('name')} | id={rec.get('id')}")
            raise ValueError("Snapshot nuovo rimuove ricette già pubblicate: arresto per verifica")
    if not_authorized:
        raise ValueError("Snapshot non sicuro: ricette precedentemente visibili scomparse. Nessuna pubblicazione automatica.")
    if missing:
        print(f"Sospensioni fotografiche deliberate e documentate: {len(missing)}")
    return len(old),len(new)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=Path("data/catalogo.json"))
    parser.add_argument("--snapshot",type=Path,default=Path("data/catalogo_pubblicato.json"))
    parser.add_argument("--previous",type=Path,default=None)
    parser.add_argument("--approved-photo-review",type=Path,default=None)
    args=parser.parse_args()
    compare(args.source,args.snapshot,args.previous,args.approved_photo_review)
