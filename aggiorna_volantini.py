"""Aggiorna data/volantini.json con il volantino in corso di ogni supermercato.

Legge solo le pagine ufficiali dei marchi (app/volantini.py). Per le catene con
volantino nazionale ricava link diretto e date di validità; per le altre
registra la pagina ufficiale dei volantini, dove si sceglie il punto vendita.
Se una pagina non risponde si conserva il volantino già trovato finché è valido.

Uso: python aggiorna_volantini.py [--oggi AAAA-MM-GG] [--out data/volantini.json]
"""
import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

from app.rete import FetchError, fetch_text
from app.volantini import CATENE, voce

UA = 'Mozilla/5.0 (compatible; PepitoPersonalProject/0.2; volantini dai siti ufficiali)'


def leggi(url, fetch=fetch_text):
    try:
        return fetch(url, user_agent=UA, attempts=2, backoff=3.0, same_host=False), None
    except FetchError as exc:
        return None, str(exc)


def aggiorna(oggi, precedenti, fetch=fetch_text, pausa=1.0):
    adesso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    catene = {}
    for nome, info in CATENE.items():
        html = errore = None
        if info['estrattore']:
            html, errore = leggi(info['pagina'], fetch)
            if pausa:
                time.sleep(pausa)
        catene[nome] = voce(nome, html, oggi, adesso, (precedenti.get('catene') or {}).get(nome), errore)
    return {'aggiornato_il': adesso, 'data_riferimento': oggi.isoformat(), 'catene': catene}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--oggi', default=None)
    ap.add_argument('--out', default='data/volantini.json')
    args = ap.parse_args(argv)
    oggi = date.fromisoformat(args.oggi) if args.oggi else date.today()
    out = Path(args.out)
    precedenti = json.loads(out.read_text()) if out.exists() else {}
    dati = aggiorna(oggi, precedenti)
    out.write_text(json.dumps(dati, ensure_ascii=False, indent=1) + '\n')
    for nome, v in dati['catene'].items():
        vol = v.get('volantino') or {}
        print(f"{nome:11} {v['metodo']:24} {vol.get('valido_dal') or '-':10} → {vol.get('valido_al') or '-':10} "
              f"{vol.get('url') or v['pagina_ufficiale']}" + (f"  [errore: {v['errore']}]" if v.get('errore') else ''))
    attese = [n for n, i in CATENE.items() if i['estrattore']]
    trovate = [n for n in attese if dati['catene'][n]['volantino']]
    print(f'Link diretti: {len(trovate)}/{len(attese)} catene con volantino nazionale')
    return 0


if __name__ == '__main__':
    sys.exit(main())
