"""Confronto non distruttivo tra catalogo disponibile in Cheffino e snapshot candidato.

Non approva nuovi record, non esegue download e non modifica file.
Un record pubblicato in precedenza non deve sparire in silenzio.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

def current_visible(rec):
    if rec.get("needs_review") or rec.get("validazione_automatica", {}).get("approved") is False:
        return False
    return (isinstance(rec.get("id"), int) and bool(rec.get("name")) and
            isinstance(rec.get("url"), str) and rec["url"].startswith("https://") and
            bool(rec.get("source")) and isinstance(rec.get("ingredients"), list) and
            len(rec["ingredients"]) > 0)

def compare(source, snapshot, previous=None):
    source_data=json.loads(Path(source).read_text(encoding="utf-8"))
    published=json.loads(Path(snapshot).read_text(encoding="utf-8"))
    if not isinstance(source_data,list) or not isinstance(published,list):
        raise ValueError("Cataloghi non validi")
    old={rec["id"]:rec for rec in source_data if current_visible(rec)}
    new={rec["id"]:rec for rec in published}
    missing=[rec for rid,rec in old.items() if rid not in new]
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
        if lost_previous:
            for rec in lost_previous[:20]:
                print(f"PERDITA SNAPSHOT PRECEDENTE: {rec.get('name')} | id={rec.get('id')}")
            raise ValueError("Snapshot nuovo rimuove ricette già pubblicate: arresto per verifica")
    if missing:
        raise ValueError("Snapshot non sicuro: ricette precedentemente visibili scomparse. Nessuna pubblicazione automatica.")
    return len(old),len(new)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=Path("data/catalogo.json"))
    parser.add_argument("--snapshot",type=Path,default=Path("data/catalogo_pubblicato.json"))
    parser.add_argument("--previous",type=Path,default=None)
    args=parser.parse_args()
    compare(args.source,args.snapshot,args.previous)
