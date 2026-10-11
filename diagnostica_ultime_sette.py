"""Audit in sola lettura delle sette ricette ancora senza galleria.

Distingue immagini numerate, strisce e altri tag immagine; NON certifica
l'assenza di fotografie da un semplice parser che non le riconosce.
"""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlparse
from app.public_catalog import public_catalog
from importa_foto_passaggi import ImagesHTML, fetch_html, robots_policy, UA
from app.catalog import parse_recipe
from controlla_integrita_catalogo import image_id

class ImagesSeen(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images=[]
        self.containers=[]
        self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag in ('img','source'):
            self.images.append((a.get('alt',''),a.get('src',''),a.get('data-src',''),a.get('srcset','')[:150]))
        if tag=='a' and a.get('href'):
            self.links.append((a.get('class',''),a['href']))

def main():
    records=[r for r in public_catalog() if not r.get('needs_review') and
             not any(isinstance(g,list) and g for g in (r.get('step_images') or []))]
    print('SENZA FOTO: ',len(records),flush=True)
    policy=robots_policy()
    for rec in records:
        url=rec['url']
        print('\nSCHEDA',rec['id'],rec['name'],'STEPS',len(rec.get('steps',[])),'URL',url,flush=True)
        if urlparse(url).hostname != 'ricette.giallozafferano.it':
            print('BLOG: richiede scanner dedicato; nessuna inferenza di assenza',flush=True)
            continue
        if not policy.can_fetch(UA,url):
            print('BLOCCATA ROBOTS',flush=True)
            continue
        try:
            html=fetch_html(url)
            p=ImagesHTML(rec['name'],url);p.feed(html)
            allpics=ImagesSeen();allpics.feed(html)
            parsed=parse_recipe(html,url)
            print('FONTE',parsed['name'],'STEPS',len(parsed['steps']),
                  'NUMERATE',sorted(p.photos),
                  'STRIPS',sorted(set((a,b) for a,b,_ in p.strips)),
                  'TAG_FOTO',len(allpics.images),'BODY_BYTES',len(html),flush=True)
            for alt,src,lazy,srcset in allpics.images[:24]:
                print(' TAGIMG',alt[:95],(src or lazy or srcset)[:155],flush=True)
            print('IMG_MAIN',parsed.get('image_url'),'ID_COVER',image_id(rec.get('image_url')),flush=True)
        except Exception as exc:
            print('ERRORE',type(exc).__name__,str(exc)[:250],flush=True)
if __name__=='__main__':
    main()
