"""Diagnostica temporanea 3 (curl)."""
import re, subprocess, html as H
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
def curl(u):
    p=subprocess.run(['curl','-sSL','--compressed','-m','25','-A',UA,'-H','Accept-Language: it-IT,it;q=0.9','-w','\n@@%{http_code} %{url_effective}',u],capture_output=True,text=True,errors='replace')
    body,_,meta=p.stdout.rpartition('\n@@')
    return meta.strip() or p.stderr.strip()[:120], body
def show(u, pat=r'volantin|flyer|leaflet|sfoglia|viewer|offert', n=15, ctx=False):
    meta,b=curl(u); t=re.search(r'<title[^>]*>(.*?)</title>',b,re.S|re.I)
    print('  ',u,'->',meta,len(b),'|',(H.unescape(t.group(1)).strip()[:60] if t else ''))
    hs=[]
    for m in re.finditer(r'href=["\']([^"\'#]+)["\']',b):
        h=H.unescape(m.group(1))
        if re.search(pat,h,re.I) and h not in hs: hs.append(h)
    for h in hs[:n]: print('      href',h[:170])
    return b
print('##### Alì');[show(u) for u in ['https://www.alisupermercati.it/','https://www.alisupermercati.it/volantini']]
print('##### Coop');[show(u) for u in ['https://www.coop.it/','https://www.e-coop.it/','https://www.e-coop.it/volantini']]
print('##### Decò');[show(u) for u in ['https://www.supermercatideco.it/','https://supermercatideco.multicedi.it/','https://www.decoitalia.it/','https://www.dec.it/']]
print('##### Famila');b=show('https://www.famila.it/',r'promo|volant|offert|negoz|punti',25)
print('##### PAM')
b=show('https://www.pampanorama.it/')
for s in re.findall(r'src=["\']([^"\']+\.js)["\']',b)[:6]:
    u=s if s.startswith('http') else 'https://www.pampanorama.it'+('' if s.startswith('/') else '/')+s
    m,j=curl(u); print('    js',u,m,len(j)); print('      routes',sorted(set(re.findall(r'["\'](/[a-z0-9\-/]*(?:volantin|offert|promo)[a-z0-9\-/]*)["\']',j)))[:15]); print('      hosts',sorted(set(re.findall(r'https://[a-z0-9.\-]+(?:/[a-z0-9\-]*volantin[^"\']*)?',j)))[:15])
print('##### Tigros')
b=show('https://www.tigros.it/')
for s in re.findall(r'src=["\']([^"\']+\.js)["\']',b)[:6]:
    u=s if s.startswith('http') else 'https://www.tigros.it'+('' if s.startswith('/') else '/')+s
    m,j=curl(u); print('    js',u,m,len(j)); print('      routes',sorted(set(re.findall(r'["\'](/[a-z0-9\-/]*(?:volantin|offert|promo)[a-z0-9\-/]*)["\']',j)))[:15])
print('##### Sole365');[show(u) for u in ['https://www.sole365.it/','https://www.sole365.it/volantino/']]
print('##### MD');b=show('https://www.mdspa.it/volantino/'); print('     date',re.findall(r'[Dd]al \d{1,2}[^<]{0,30}20\d\d',b)[:4]); print('     viewer',sorted(set(re.findall(r'https?://[^"\'\s<>]*(?:shopfully|volantinopiu|publitas|flipp|issuu|\.pdf)[^"\'\s<>]*',b)))[:6])
print('##### Esselunga');b=show('https://www.esselunga.it/it-it/promozioni/volantini.html',n=25)
print('##### Carrefour');b=show('https://www.carrefour.it/volantino',n=25); print('     ',re.findall(r'data-[a-z\-]*flyer[a-z\-]*=["\'][^"\']{0,80}',b)[:8])
print('##### Lidl')
meta,b=curl('https://www.lidl.it/c/volantino-lidl/s10018048')
for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.{0,600}?)</a>',b,re.S):
    t=re.sub(r'<[^>]+>|\s+',' ',m.group(2)).strip()
    if re.search(r'\d{1,2}/\d{1,2}',t) or 'volantin' in m.group(1): print('      ',H.unescape(m.group(1))[:150],'|',t[:110])
print('     data-urls',sorted(set(re.findall(r'https://www\.lidl\.it/l/it/volantini/[^"\'\s<>]+',b)))[:12])
print('##### Eurospin');meta,b=curl('https://www.eurospin.com/it-it/volantino/'); print('     ',[re.sub(r'\s+',' ',x)[:90] for x in re.findall(r'[Dd]al \d{1,2}[^<]{0,40}20\d\d',b)][:5]); print('     ',sorted(set(re.findall(r'https://flyer\.eurospin\.com/[^"\'\s<>]+',b)))[:8])
print('##### Dodecà');b=show('https://www.dodeca.it/',r'volantin|flyer|viewer|catalog|offert|promo',20)
print('##### Penny');b=show('https://www.penny.it/sfoglia-il-volantino-mobile',n=10);print('     ',sorted(set(re.findall(r'data-[a-z\-]+=["\'][^"\']*(?:flyer|volantin)[^"\']*',b)))[:8]);print('     ',re.findall(r'[Dd]al \d{1,2}[^<]{0,40}',b)[:4])
print('##### Il Gigante');b=show('https://ilgigante.net/volantini/',n=5);print('     ',sorted(set(re.findall(r'data-[a-z\-]+=["\'][^"\']{0,120}',b)))[:0]);print('     ',re.findall(r'(?:flyer|retailer|store)[_-]?(?:id|Id|slug)["\']?\s*[:=]\s*["\']?[\w\-]+',b)[:8])
print('##### Conad');b=show('https://www.conad.it/ricerca-negozi',n=5)
print('##### Despar');b=show('https://www.despar.it/it/offerte-per-te/',r'volantin|flyer|offert|promo|negoz',20)
print('##### Bennet');meta,b=curl('https://www.bennet.com/flyer')
for m in re.finditer(r'(nativa\.bennet\.volantinopiu\.com/volantino\d+\.html)',b): pass
blocks=re.split(r'Visualizza volantino',b)
for bl in blocks[:-1]:
    u=re.findall(r'nativa\.bennet\.volantinopiu\.com/volantino\d+\.html',bl); d=re.findall(r'Dal \d{1,2}/\d{1,2} al \d{1,2}/\d{1,2}',bl); t=re.findall(r'<h\d[^>]*>([^<]{3,80})</h\d>',bl)
    print('     ',u[-1:] ,d[-1:], t[-2:])
print('##### Aldi');meta,b=curl('https://www.aldi.it/volantino-online');print('     ',sorted(set(re.findall(r'https://volantino\.aldi\.it/[^"\'\s<>]+',b))))
