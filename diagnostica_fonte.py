"""Diagnostica in sola lettura: come la fonte espone ingredienti, categorie, tempi."""
import json, re, sys
from app.rete import fetch_text
from app.catalog import JsonLdParser, load_json_ld, recipe_nodes

for url in sys.argv[1:]:
    print('\n########', url)
    try:
        html = fetch_text(url)
    except Exception as exc:
        print('ERRORE', exc); continue
    p = JsonLdParser(); p.feed(html)
    for s in p.scripts:
        for node in recipe_nodes(load_json_ld(s) or []):
            for k in ('recipeCategory', 'recipeCuisine', 'keywords', 'recipeYield', 'prepTime', 'cookTime',
                      'totalTime', 'nutrition', 'recipeIngredient'):
                print(k, '=', json.dumps(node.get(k), ensure_ascii=False)[:600])
    for m in list(re.finditer(r'gz-ingredient', html))[:4]:
        print('HTML-ING:', re.sub(r'\s+', ' ', html[m.start()-80:m.start()+420]))
    for kw in ('gz-name-featured-data', 'gz-list-featured-data', 'Preparazione:', 'Cottura:', 'Dosi per', 'gz-breadcrumb', 'Costo'):
        m = re.search(re.escape(kw), html)
        if m: print('HTML', kw, ':', re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html[m.start()-50:m.start()+500]))[:400])
