"""Diagnostica temporanea: verifica pagine volantino candidate."""
import re
from urllib.request import Request, urlopen
UA='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
C={'Alì':['https://www.alisupermercati.it/volantini','https://www.alisupermercati.it/volantino','https://alisupermercati.it/'],
'Carrefour':['https://volantino.carrefour.it/','https://www.carrefour.it/volantino'],
'Conad':['https://www.conad.it/volantini','https://www.conad.it/ricerca-negozi'],
'Coop':['https://www.coop.it/volantini','https://www.e-coop.it/volantini','https://www.coop.it/'],
'Dec':['https://www.dec.it/volantini','https://www.dec.it/volantino','https://www.dec.it/'],
'Despar':['https://www.despar.it/it/offerte-per-te/','https://www.despar.it/it/volantini/'],
'Esselunga':['https://www.esselunga.it/it-it/promozioni/volantini.html','https://www.esselunga.it/it-it/promozioni.html'],
'Famila':['https://www.famila.it/volantini','https://www.famila.it/volantino','https://www.famila.it/offerte'],
'Il Gigante':['https://ilgigante.net/volantini/'],
'PAM':['https://www.pampanorama.it/volantini','https://www.pampanorama.it/volantino','https://www.pampanorama.it/offerte'],
'Penny':['https://www.penny.it/volantino','https://www.penny.it/sfoglia-il-volantino-mobile','https://www.penny.it/offerte'],
'Sole365':['https://www.sole365.it/volantino/','https://www.sole365.it/volantini/','https://www.sole365.it/offerte/'],
'Tigros':['https://www.tigros.it/volantini','https://www.tigros.it/volantino','https://www.tigros.it/offerte'],
'MD':['https://www.mdspa.it/volantino/'],
'Eurospin':['https://flyer.eurospin.com/it-it/volantino','https://www.eurospin.com/it-it/volantino/'],
'Lidl':['https://www.lidl.it/c/volantino-lidl/s10018048'],
'Dodecà':['https://www.dodeca.it/volantini','https://viewer.flyer.volantinopiu.ai/preview-dodeca-1?mode=scroll'],
}
for name,urls in C.items():
    print('\n#####',name)
    for u in urls:
        try:
            r=urlopen(Request(u,headers={'User-Agent':UA,'Accept-Language':'it-IT,it;q=0.9','Accept':'text/html,*/*'}),timeout=25)
            h=r.read(2_000_000).decode('utf-8','replace')
            t=re.search(r'<title[^>]*>(.*?)</title>',h,re.S|re.I)
            dates=[m.group(0) for m in re.finditer(r'(?:[Dd]al|[Vv]alid[oa][^<]{0,15}?)\s+\d{1,2}(?:/\d{1,2}|\s+(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre))[^<]{0,40}',h)][:3]
            hrefs=sorted(set(re.findall(r'https?://[^"\'\s<>]*(?:volantin|flyer|leaflet|sfoglia|publitas|viewer)[^"\'\s<>]*',h,re.I)))[:8]
            print('  OK',r.status,r.geturl(),'|',(t.group(1).strip()[:70] if t else ''),'| volantin x',len(re.findall('volantin',h,re.I)),'| date',dates)
            for x in hrefs: print('     ',x[:170])
        except Exception as e:
            print('  NO',u,e)
