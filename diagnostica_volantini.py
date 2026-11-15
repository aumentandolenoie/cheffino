"""Diagnostica temporanea: dove pubblicano i volantini i siti ufficiali."""
import re, json, sys
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
SITES={'Aldi':'https://www.aldi.it/','Alì':'https://www.alisupermercati.it/','Bennet':'https://www.bennet.com/','Carrefour':'https://www.carrefour.it/','Conad':'https://www.conad.it/','Coop':'https://www.coop.it/','Dec':'https://www.dec.it/','Despar':'https://www.despar.it/','Dodecà':'https://www.dodeca.it/','Esselunga':'https://www.esselunga.it/','Eurospin':'https://www.eurospin.it/','Famila':'https://www.famila.it/','Il Gigante':'https://www.ilgigante.net/','Lidl':'https://www.lidl.it/','MD':'https://www.mdspa.it/','PAM':'https://www.pampanorama.it/','Penny':'https://www.penny.it/','Sole365':'https://www.sole365.it/','Tigros':'https://www.tigros.it/'}
def get(url):
    r=urlopen(Request(url,headers={'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9','Accept':'text/html,*/*'}),timeout=25)
    return r.geturl(), r.status, r.read(3_000_000).decode('utf-8','replace')
def links(html,base):
    out=[]
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',html,re.S|re.I):
        href=urljoin(base,m.group(1)); text=re.sub(r'<[^>]+>|\s+',' ',m.group(2)).strip()[:80]
        out.append((href,text))
    return out
for name,home in SITES.items():
    print('\n#####',name,home)
    try:
        final,st,html=get(home)
    except Exception as e:
        print('  HOME ERRORE',e); continue
    print('  HOME',st,final,len(html))
    cands=[(h,t) for h,t in links(html,final) if re.search(r'volantin|offert|promo|flyer|catalog',h+' '+t,re.I)]
    seen=[]
    for h,t in cands:
        if h not in [x[0] for x in seen]: seen.append((h,t))
    for h,t in seen[:12]: print('   LINK',h,'|',t)
    vol=[h for h,t in seen if re.search(r'volantin',h+' '+t,re.I)][:2]
    for v in vol:
        try:
            f2,s2,h2=get(v)
            print('   >> PAGINA',s2,f2,len(h2))
            for h,t in links(h2,f2):
                if re.search(r'\.pdf|volantin|flyer|sfoglia|viewer|publitas|issuu|ipaper|leaflet|catalogo',h+' '+t,re.I) and urlparse(h).netloc:
                    print('      ',h[:180],'|',t[:60])
            for m in list(re.finditer(r'(?:valid[oa]|dal)\s+\d{1,2}[/ .-]\w+[^<]{0,40}',h2,re.I))[:3]: print('      DATE',m.group(0)[:80])
            for m in list(re.finditer(r'https?://[^"\'\s<>]+(?:\.pdf|publitas[^"\'\s<>]*|issuu[^"\'\s<>]*|leaflets?[^"\'\s<>]*)',h2,re.I))[:8]: print('      URL',m.group(0)[:180])
        except Exception as e:
            print('   >> ERRORE',v,e)
