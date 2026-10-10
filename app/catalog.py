import json, sqlite3, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from datetime import datetime, timezone

DB = Path(__file__).resolve().parent.parent / 'data' / 'ricette.sqlite3'
ALLOWED = ('giallozafferano.it', 'cucchiaio.it', 'tavolartegusto.it', 'cucinabotanica.it', 'cookist.it')

class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_script=False; self.parts=[]; self.scripts=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type','').lower() == 'application/ld+json':
            self.in_script=True; self.parts=[]
    def handle_data(self,data):
        if self.in_script: self.parts.append(data)
    def handle_endtag(self,tag):
        if tag == 'script' and self.in_script:
            self.scripts.append(''.join(self.parts)); self.in_script=False

def recipe_nodes(item):
    if isinstance(item,list):
        for sub in item: yield from recipe_nodes(sub)
    elif isinstance(item,dict):
        typ=item.get('@type',[])
        if isinstance(typ,str): typ=[typ]
        if 'Recipe' in typ or any(str(t).endswith('/Recipe') for t in typ): yield item
        for child in item.get('@graph',[]): yield from recipe_nodes(child)

def text_value(v):
    if isinstance(v,str): return v.strip()
    if isinstance(v,dict): return str(v.get('text') or v.get('name') or '').strip()
    return ''

def parse_recipe(html,url):
    p=JsonLdParser(); p.feed(html)
    for script in p.scripts:
        try: roots=json.loads(script)
        except json.JSONDecodeError: continue
        for node in recipe_nodes(roots):
            name=text_value(node.get('name'))
            ingredients=[text_value(x) for x in node.get('recipeIngredient',[]) if text_value(x)]
            if not name or not ingredients: continue
            steps=[]
            def add_step(v):
                if isinstance(v,list):
                    for x in v: add_step(x)
                elif isinstance(v,dict):
                    typ=v.get('@type','')
                    if typ=='HowToSection': add_step(v.get('itemListElement',[]))
                    else:
                        s=text_value(v)
                        if s: steps.append(s)
                elif isinstance(v,str) and v.strip(): steps.append(v.strip())
            add_step(node.get('recipeInstructions',[]))
            img=node.get('image'); img=img[0] if isinstance(img,list) and img else img
            if isinstance(img,dict): img=img.get('url') or img.get('contentUrl')
            nutrition=node.get('nutrition') if isinstance(node.get('nutrition'),dict) else {}
            yield_info=node.get('recipeYield')
            return {'name':name,'url':url,'source':urlparse(url).hostname,'image_url':img if isinstance(img,str) else None,
                    'ingredients':ingredients,'steps':steps,'yield_text':str(yield_info) if yield_info else None,
                    'prep_time':node.get('prepTime'),'cook_time':node.get('cookTime'),'total_time':node.get('totalTime'),
                    'nutrition':{k:nutrition.get(k) for k in ('calories','proteinContent','carbohydrateContent','fatContent') if nutrition.get(k)},
                    'imported_at':datetime.now(timezone.utc).isoformat()}
    raise ValueError('Nessuna ricetta completa in formato JSON-LD: nessun dato inserito.')

def validate_url(url):
    p=urlparse(url)
    if p.scheme!='https' or not p.hostname or not any(p.hostname==d or p.hostname.endswith('.'+d) for d in ALLOWED):
        raise ValueError('URL non consentito: usare una pagina HTTPS dei siti supportati.')

def fetch_recipe(url):
    validate_url(url)
    req=Request(url,headers={'User-Agent':'CheffinoPersonalProject/0.1 (manual import; contact owner for requests)','Accept':'text/html'})
    with urlopen(req,timeout=18) as response:
        if urlparse(response.geturl()).hostname != urlparse(url).hostname:
            validate_url(response.geturl())
        html=response.read(3_000_000).decode('utf-8','replace')
    return parse_recipe(html,url)

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(DB); con.row_factory=sqlite3.Row
    con.execute('''CREATE TABLE IF NOT EXISTS recipes (id INTEGER PRIMARY KEY, url TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
       source TEXT NOT NULL, image_url TEXT, ingredients_json TEXT NOT NULL, steps_json TEXT NOT NULL,
       nutrition_json TEXT NOT NULL, yield_text TEXT, prep_time TEXT, cook_time TEXT, total_time TEXT, imported_at TEXT NOT NULL)''')
    con.commit(); return con

def save(recipe):
    with connect() as con:
        con.execute('''INSERT INTO recipes (url,name,source,image_url,ingredients_json,steps_json,nutrition_json,yield_text,prep_time,cook_time,total_time,imported_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
          name=excluded.name,source=excluded.source,image_url=excluded.image_url,ingredients_json=excluded.ingredients_json,
          steps_json=excluded.steps_json,nutrition_json=excluded.nutrition_json,yield_text=excluded.yield_text,
          prep_time=excluded.prep_time,cook_time=excluded.cook_time,total_time=excluded.total_time,imported_at=excluded.imported_at''',
          (recipe['url'],recipe['name'],recipe['source'],recipe['image_url'],json.dumps(recipe['ingredients'],ensure_ascii=False),
           json.dumps(recipe['steps'],ensure_ascii=False),json.dumps(recipe['nutrition'],ensure_ascii=False),recipe['yield_text'],
           recipe['prep_time'],recipe['cook_time'],recipe['total_time'],recipe['imported_at']))

def list_recipes():
    with connect() as con:
        rows=con.execute('SELECT * FROM recipes ORDER BY CASE WHEN source LIKE "%giallozafferano.it%" THEN 0 ELSE 1 END,name').fetchall()
    return [{**dict(r),'ingredients':json.loads(r['ingredients_json']),'steps':json.loads(r['steps_json']),
             'nutrition':json.loads(r['nutrition_json'])} for r in rows]
