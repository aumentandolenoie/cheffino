"""Ripristina passaggi e fotografie originali nelle ricette storiche pubblicate.

Solo schede con ID e URL identici in catalogo e snapshot; solo contenuti
autentici della pagina sorgente, rispettando robots.txt.
Aggiorna entrambi i cataloghi o nessuno (scrive dopo tutti i controlli).
Non cambia ingredienti, classificazioni o stato di pubblicazione.
"""
import argparse
import json
from copy import deepcopy
from pathlib import Path

from app.catalog import parse_recipe
from controlla_integrita_catalogo import image_id
from importa_foto_passaggi import (
    ImagesHTML, UA, associate_steps, fetch_html, robots_policy, valid_image,
)
from pulisci_procedimenti import clean_steps

RAW = Path("data/catalogo.json")
PUBLISHED = Path("data/catalogo_pubblicato.json")
LEGACY_IDS = {26}


def plan(source=RAW, published=PUBLISHED, fetcher=fetch_html, policy=None):
    full = json.loads(Path(source).read_text(encoding="utf-8"))
    public = json.loads(Path(published).read_text(encoding="utf-8"))
    if not isinstance(full,list) or not isinstance(public,list):
        raise ValueError("Cataloghi non validi")
    if policy is None:
        policy = robots_policy()
    latest = {r.get("id"): r for r in full}
    approved = {r.get("id"): r for r in public}
    corrections = []
    for recipe_id in sorted(LEGACY_IDS):
        rec = latest.get(recipe_id)
        pub = approved.get(recipe_id)
        if not rec or not pub or rec.get("url") != pub.get("url"):
            raise ValueError(f"Ricetta storica incoerente: {recipe_id}")
        if rec.get("step_images") or pub.get("step_images"):
            continue
        url = rec["url"]
        if not url.startswith("https://ricette.giallozafferano.it/"):
            raise ValueError(f"Fonte non prevista per ID {recipe_id}")
        if not policy.can_fetch(UA,url):
            print(f"ID {recipe_id}: robots.txt non consente accesso")
            continue
        try:
            html = fetcher(url)
            data = parse_recipe(html,url)
            raw_steps = data["steps"]
            steps,_ = clean_steps(raw_steps)
            if not steps or not all(isinstance(s,str) and s.strip() for s in steps):
                raise ValueError("Procedimento originale vuoto")
            parser = ImagesHTML(data["name"], url)
            parser.feed(html)
            groups,method = associate_steps(parser,raw_steps,len(steps))
            if not groups or not any(groups) or len(groups)!=len(steps):
                print(f"ID {recipe_id}: nessuna mappatura fotografica verificabile "
                      f"(passaggi={len(steps)}, numerate={len(parser.photos)}, strip={len(parser.strips)})")
                continue
            cover = rec.get("image_url") or pub.get("image_url")
            if not valid_image(cover,url):
                print(f"ID {recipe_id}: copertina non certificata")
                continue
            main_id = image_id(cover)
            step_ids = {image_id(u) for group in groups for u in group if image_id(u)}
            if main_id and any(i != main_id for i in step_ids):
                # La scheda storica puo' avere una copertina di un'altra ricetta.
                # Una sostituzione e' consentita soltanto se la foto principale
                # ORIGINALE della pagina corrente coincide con TUTTE le foto step.
                fresh = valid_image(data.get("image_url"),url)
                fresh_id = image_id(fresh)
                if not fresh or not fresh_id or not step_ids or any(i != fresh_id for i in step_ids):
                    print(f"ID {recipe_id}: foto fonte non coerenti, nessuna sostituzione")
                    continue
                print(f"ID {recipe_id}: sostituisco copertina storica discordante con originale verificata")
                for target in (rec,pub):
                    target["image_url_precedente"] = target.get("image_url")
                    target["image_url"] = fresh
            for target in (rec,pub):
                target["steps_precedenti"] = list(target["steps"])
                target["steps"] = steps
                target["steps_raw"] = raw_steps
                target["steps_clean"] = steps
                target["step_images"] = groups
                target["images_import_version"] = 10
            corrections.append((recipe_id,rec["name"],method,sum(map(len,groups))))
            print(f"PRONTA: ID={recipe_id} | {rec['name']} | metodo={method} | foto={sum(map(len,groups))} | blocchi={len(groups)}")
        except Exception as exc:
            print(f"SKIP ID {recipe_id} ({rec['name']}): {type(exc).__name__}: {exc}")
    return full,public,corrections


def run(apply=False, source=RAW, published=PUBLISHED, **kwargs):
    full,public,changes=plan(source,published,**kwargs)
    print(f"Ripristino storico: recuperate={len(changes)} su {len(LEGACY_IDS)} schede candidate; mode={'apply' if apply else 'dry-run'}")
    if apply and changes:
        for target, records in ((Path(source),full),(Path(published),public)):
            tmp=target.with_suffix(".recover-tmp")
            tmp.write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            tmp.replace(target)
    return changes


if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--apply",action="store_true")
    args=p.parse_args()
    run(apply=args.apply)
