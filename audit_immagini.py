"""Audit conservativo: segnala foto mancanti, identificativi discordanti e URL non raggiungibili.

Non altera il catalogo e non assume che una richiesta HTTP fallita provi che
l'immagine sia inesistente (anti-hotlink, rete e codici 403/429 sono possibili).
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from controlla_integrita_catalogo import image_id

SOURCE = Path("data/catalogo.json")
USER_AGENT = "CheffinoPersonalProject/0.1 (image link audit)"


def safe_image_url(url):
    if not isinstance(url, str):
        return False
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return (p.scheme == "https"
            and (host == "giallozafferano.it" or host.endswith(".giallozafferano.it"))
            and p.port in (None, 443)
            and not p.username and not p.password)


def inspect_record(rec):
    problems = []
    main = rec.get("image_url")
    if not main:
        problems.append("copertina_mancante")
    elif not safe_image_url(main):
        problems.append("copertina_url_non_ammesso")
    groups = rec.get("step_images")
    if not isinstance(groups, list) or not any(isinstance(g, list) and g for g in groups):
        problems.append("foto_passaggi_mancanti")
    else:
        main_id = image_id(main)
        step_urls = [u for group in groups if isinstance(group, list) for u in group]
        if any(not safe_image_url(u) for u in step_urls):
            problems.append("passaggi_url_non_ammessi")
        known_ids = {image_id(u) for u in step_urls if image_id(u)}
        if main_id and any(x != main_id for x in known_ids):
            problems.append("id_foto_divergenti")
        if main_id is None or any(image_id(u) is None for u in step_urls):
            problems.append("identita_non_verificabile_da_url")
    return problems


def probe(url, opener=urlopen, timeout=8):
    if not safe_image_url(url):
        return "url_non_ammesso"
    for method in ("HEAD", "GET"):
        try:
            headers = {"User-Agent": USER_AGENT, "Accept": "image/*"}
            if method == "GET":
                headers["Range"] = "bytes=0-0"
            request = Request(url, headers=headers, method=method)
            with opener(request, timeout=timeout) as response:
                if not safe_image_url(response.geturl()):
                    return "redirect_non_ammesso"
                status = response.status
                ctype = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
                if status in (200, 206) and ctype.startswith("image/"):
                    return "ok"
                if status in (200, 206):
                    return "tipo_contenuto_non_immagine"
                return "http_" + str(status)
        except HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405, 501):
                continue
            return "http_" + str(exc.code)
        except (URLError, TimeoutError, OSError):
            return "rete_non_verificabile"
    return "non_verificabile"


def audit(path=SOURCE, limit=25, online=False, opener=urlopen):
    records = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Catalogo non valido")
    counts = Counter()
    examined = 0
    for rec in records:
        issues = inspect_record(rec)
        for issue in issues:
            counts[issue] += 1
        if issues:
            print(f"FOTO AUDIT: {rec.get('name')} | problemi={','.join(issues)}")
        if online and examined < limit and rec.get("image_url"):
            status = probe(rec["image_url"], opener=opener)
            counts["http_" + status] += 1
            if status != "ok":
                print(f"FOTO HTTP: {rec.get('name')} | stato={status}")
            examined += 1
    print(f"Audit immagini: ricette={len(records)}; copertine_verificate_http={examined}; riepilogo={dict(counts)}")
    return counts


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--file", type=Path, default=SOURCE)
    cli.add_argument("--limit", type=int, default=25)
    cli.add_argument("--online", action="store_true")
    opts = cli.parse_args()
    if not 1 <= opts.limit <= 100:
        cli.error("--limit deve essere tra 1 e 100")
    audit(opts.file, opts.limit, opts.online)
