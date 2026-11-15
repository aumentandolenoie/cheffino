import re,html
from app.rete import fetch_text
b=fetch_text('https://www.lidl.it/c/volantino-lidl/s10018048',user_agent='Mozilla/5.0 (compatible; PepitoPersonalProject/0.2; volantini dai siti ufficiali)',same_host=False)
for m in list(re.finditer(r'flyer__name',b))[:3]:
    print('=====');print(re.sub(r'\s+',' ',b[max(0,m.start()-2500):m.start()+400]))
print(sorted(set(re.findall(r'(?:href|data-[a-z-]+)=["\']([^"\']*(?:volantin|flyer|leaflet)[^"\']*)',b)))[:40])
