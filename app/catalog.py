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
        # Alcuni siti annidano la ricetta in mainEntity / mainEntityOfPage.
        for key in ('mainEntity','mainEntityOfPage'):
            if isinstance(item.get(key),(dict,list)): yield from recipe_nodes(item[key])


def _types(v):
    typ=v.get('@type',[]) if isinstance(v,dict) else []
    return [typ] if isinstance(typ,str) else [str(t) for t in typ or []]


def text_value(v):
    from app.ingredienti import clean_text
    if isinstance(v,str): return clean_text(v)
    if isinstance(v,dict): return clean_text(v.get('text') or v.get('name') or '')
    return ''


def load_json_ld(script):
    """JSON-LD tollerante: commenti HTML/CDATA, caratteri di controllo, virgole finali."""
    raw=script.strip()
    raw=re.sub(r'^\s*(?:<!--|<!\[CDATA\[)|(?:-->|\]\]>)\s*$','',raw)
    for candidate in (raw, re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',' ',raw)):
        try: return json.loads(candidate)
        except json.JSONDecodeError: pass
    try: return json.loads(re.sub(r',\s*([}\]])',r'\1',re.sub(r'[\x00-\x1f]',' ',raw)))
    except json.JSONDecodeError: return None


def _image(img):
    if isinstance(img,list):
        for x in img:
            if u:=_image(x): return u
        return None
    if isinstance(img,dict): img=img.get('url') or img.get('contentUrl')
    return img.strip() if isinstance(img,str) and img.strip() else None


def _steps(value):
    steps=[]
    def add(v):
        if isinstance(v,list):
            for x in v: add(x)
        elif isinstance(v,dict):
            if any(t.endswith('HowToSection') for t in _types(v)) or (
                    'itemListElement' in v and not v.get('text')):
                add(v.get('itemListElement',[]))
            else:
                s=text_value(v)
                if s: steps.append(s)
        elif isinstance(v,str):
            # Istruzioni in un'unica stringa: un paragrafo per riga.
            for line in re.split(r'(?:\r?\n)+|<br\s*/?>',v):
                s=text_value(line)
                if s: steps.append(s)
    add(value)
    return steps


NUTRITION_KEYS={'calories':('calories',),'proteinContent':('proteinContent','protein'),
                'carbohydrateContent':('carbohydrateContent','carbohydrate'),
                'fatContent':('fatContent','fat')}


def parse_recipe(html,url):
    p=JsonLdParser(); p.feed(html)
    for script in p.scripts:
        roots=load_json_ld(script)
        if roots is None: continue
        for node in recipe_nodes(roots):
            name=text_value(node.get('name'))
            raw_ing=node.get('recipeIngredient') or node.get('ingredients') or []
            if isinstance(raw_ing,str): raw_ing=[raw_ing]
            ingredients=[text_value(x) for x in raw_ing if text_value(x)]
            if not name or not ingredients: continue
            steps=_steps(node.get('recipeInstructions',[]))
            nutrition=node.get('nutrition') if isinstance(node.get('nutrition'),dict) else {}
            nut={}
            for key,aliases in NUTRITION_KEYS.items():
                for alias in aliases:
                    if nutrition.get(alias) not in (None,''):
                        nut[key]=nutrition[alias]; break
            yield_info=node.get('recipeYield')
            if isinstance(yield_info,list): yield_info=next((x for x in yield_info if x),None)
            return {'name':name,'url':url,'source':urlparse(url).hostname,'image_url':_image(node.get('image')),
                    'ingredients':ingredients,'steps':steps,'yield_text':str(yield_info) if yield_info else None,
                    'prep_time':node.get('prepTime'),'cook_time':node.get('cookTime'),'total_time':node.get('totalTime'),
                    'nutrition':nut,
                    'imported_at':datetime.now(timezone.utc).isoformat()}
    raise ValueError('Nessuna ricetta completa in formato JSON-LD: nessun dato inserito.')

def validate_url(url):
    p=urlparse(url)
    if p.scheme!='https' or not p.hostname or not any(p.hostname==d or p.hostname.endswith('.'+d) for d in ALLOWED):
        raise ValueError('URL non consentito: usare una pagina HTTPS dei siti supportati.')


def normalize_url(url):
    """Forma canonica per confronti: https, host minuscolo, niente query/frammento."""
    p=urlparse(str(url or '').strip())
    host=(p.hostname or '').lower()
    path=re.sub(r'/{2,}','/',p.path or '/')
    return f'https://{host}{path}' if host else str(url or '')


def fetch_recipe(url, fetcher=None):
    validate_url(url)
    from app.rete import fetch_text
    html=(fetcher or fetch_text)(url)
    return parse_recipe(html,url)


SOURCE_NAMES={'ricette.giallozafferano.it':'GialloZafferano','www.giallozafferano.it':'GialloZafferano',
              'blog.giallozafferano.it':'GialloZafferano Blog','cookist.it':'Cookist','www.cookist.it':'Cookist'}


def build_record(raw, existing=None):
    """Scheda di catalogo completa da una ricetta letta dalla fonte.

    Unico costruttore per importazione automatica (aggiorna_catalogo.py) e
    manuale (importa_ricetta.py): porzioni, tempi e quantità sono interpretati
    subito, senza inventare valori. La scheda resta sempre in revisione.
    """
    import hashlib
    from app.ingredienti import parse_ingredient
    from ripara_catalogo import parse_servings, parse_duration, numeric_nutrition
    from pulisci_procedimenti import clean_steps
    url=normalize_url(raw['url'])
    nut=raw.get('nutrition') or {}
    total=parse_duration(raw.get('total_time')) or (
        (parse_duration(raw.get('prep_time')) or 0)+(parse_duration(raw.get('cook_time')) or 0)) or None
    steps,_=clean_steps(list(raw.get('steps') or []))
    rec={'id':existing['id'] if existing else int(hashlib.sha256(url.encode()).hexdigest()[:12],16)+10000,
         'name':raw['name'],'emoji':'🍽️','style':'Da classificare','type':'Da classificare',
         'time':total,'ingredients_display':list(raw['ingredients']),
         'source':SOURCE_NAMES.get(urlparse(url).hostname or '', urlparse(url).hostname),
         'url':url,'image_url':raw.get('image_url'),'servings':parse_servings(raw.get('yield_text')),
         'kcal':numeric_nutrition(nut.get('calories')) if nut.get('calories') else None,
         'protein':numeric_nutrition(nut.get('proteinContent')) if nut.get('proteinContent') else None,
         'carbs':numeric_nutrition(nut.get('carbohydrateContent')) if nut.get('carbohydrateContent') else None,
         'fats':numeric_nutrition(nut.get('fatContent')) if nut.get('fatContent') else None,
         'cost':None,'ingredients':[parse_ingredient(x) for x in raw['ingredients']],
         'steps':steps,'steps_raw':list(raw.get('steps') or []),'needs_review':True,
         'imported_at':raw.get('imported_at') or datetime.now(timezone.utc).isoformat()}
    return rec

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
