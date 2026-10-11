"""Regole fotografiche del catalogo finale: solo foto reali o assenza certificata.

L'assenza NON e' provata da step_images vuoto, da un 403 o da un parser
che non riconosce il formato. Serve un'attestazione della fonte originale
con ID e URL corrispondenti, creata da un controllo approfondito.
"""
from urllib.parse import urlparse
from controlla_integrita_catalogo import image_id

METHODS={"gz-full-html-article-no-steps-v1"}

def safe_photo(url):
    if not isinstance(url,str):
        return False
    try:
        p=urlparse(url)
        host=(p.hostname or "").lower()
        return (p.scheme=="https" and
                (host=="giallozafferano.it" or host.endswith(".giallozafferano.it"))
                and p.port in (None,443) and not p.username and not p.password)
    except ValueError:
        return False

def has_step_gallery(rec):
    groups=rec.get("step_images")
    return (isinstance(groups,list) and
            any(isinstance(g,list) and any(safe_photo(url) for url in g)
                for g in groups))

def certified_source_absence(rec):
    proof=rec.get("step_photo_source_evidence")
    if not isinstance(proof,dict) or proof.get("status")!="verified_absent":
        return False
    if proof.get("source_url")!=rec.get("url") or proof.get("method") not in METHODS:
        return False
    pid=str(proof.get("recipe_image_id") or "")
    if not pid or image_id(rec.get("image_url"))!=pid:
        return False
    if not isinstance(proof.get("verified_at"),str) or "T" not in proof["verified_at"]:
        return False
    return not has_step_gallery(rec)

def publishable_step_photos(rec):
    return has_step_gallery(rec) or certified_source_absence(rec)
