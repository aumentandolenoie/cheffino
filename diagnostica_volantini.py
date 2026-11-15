"""Diagnostica temporanea 4."""
import re, subprocess, html as H
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
def curl(u,extra=()):
    p=subprocess.run(['curl','-sSL','--compressed','-m','25','-A',UA,'-H','Accept-Language: it-IT,it;q=0.9',*extra,'-w','\n@@%{http_code} %{url_effective}',u],capture_output=True,text=True,errors='replace')
    body,_,meta=p.stdout.rpartition('\n@@'); return meta.strip() or p.stderr.strip()[:150], body
def anchors(b):
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>',b,re.S|re.I):
        yield H.unescape(m.group(1)), re.sub(r'<[^>]+>|\s+',' ',H.unescape(m.group(2))).strip()
def ctx(b,pat,n=6,w=90):
    for m in list(re.finditer(pat,b,re.I))[:n]: print('        ~',re.sub(r'\s+',' ',b[max(0,m.start()-w):m.end()+w]))
print('##### Sole365'); m,b=curl('https://www.sole365.it/'); print(m)
for h,t in anchors(b):
    if re.search(r'volant|offert|promo|sfoglia|flyer',h+t,re.I): print('     ',h[:150],'|',t[:60])
ctx(b,r'volantin',8)
print('##### PAM'); m,j=curl('https://www.pampanorama.it/main.3ceb1b0996b280b7b1ef.chunk.js'); print(m,len(j)); ctx(j,r'volantin',12,70)
print('##### Famila'); m,b=curl('https://www.famila.it/'); 
for h,t in anchors(b):
    if re.search(r'volant|offert|promo|sfoglia|negoz|punti-vendita|famila\.it/[a-z-]+$',h+' '+t,re.I): print('     ',h[:150],'|',t[:60])
m,b=curl('https://www.famila.it/faq/faq-famila-nazionale/promo-volantini'); ctx(b,r'promozioni sono uguali',2,400)
print('##### Decò multicedi'); m,b=curl('https://supermercatideco.multicedi.it/web/volantini.aspx'); print(m,len(b))
for h,t in anchors(b):
    if re.search(r'volantin',h,re.I): print('     ',h[:150],'|',t[:80])
ctx(b,r'valid[oi]',4)
print('##### Decò .it'); m,b=curl('https://supermercatideco.it/'); print(m,len(b))
for h,t in anchors(b): print('     ',h[:150],'|',t[:60])
print('##### Esselunga'); m,b=curl('https://www.esselunga.it/it-it/promozioni/volantini.html'); ctx(b,r'volantin',10,80)
print('##### Lidl ESI'); m,b=curl('https://www.lidl.it/c/volantino-lidl/s10018048')
for u in sorted(set(re.findall(r'https://esi\.leaflets\.schwarz/[^"\'\s<>]+',b)))[:10]: print('     ',u[:200])
ctx(b,r'dal \d{1,2}/\d{1,2} al',3,300)
print('##### Alì/Coop alternative')
for u in ['https://www.alisupermercati.it/','https://alisupermercati.it/volantini','https://www.coop.it/volantini','https://www.coopalleanza3-0.it/','https://www.e-coop.it/']:
    print('  ',u,curl(u,('--http1.1',))[0])
