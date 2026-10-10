import json
from xml.etree import ElementTree as ET
from aggiorna_catalogo import discover_urls, run, AllowAll


def test_discovery_filters_and_orders():
    def get(url):
        if 'ricette-new' in url:
            return ET.fromstring('''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
              <url><loc>https://ricette.giallozafferano.it/A.html</loc><lastmod>2026-10-09</lastmod></url>
              <url><loc>https://ricette.giallozafferano.it/foto.jpg</loc></url></urlset>''')
        return ET.fromstring('''<urlset><url><loc>https://ricette.giallozafferano.it/B.html</loc><lastmod>2026-10-10</lastmod></url></urlset>''')
    assert discover_urls(fetcher=get) == [
        'https://ricette.giallozafferano.it/B.html',
        'https://ricette.giallozafferano.it/A.html']


def test_import_is_incremental_and_preserves_original(tmp_path):
    path = tmp_path / 'catalogo.json'
    old = [{'id': 1, 'url': 'https://ricette.giallozafferano.it/A.html', 'name': 'Existing', 'needs_review': False}]
    path.write_text(json.dumps(old), encoding='utf-8')
    calls=[]
    def fetcher(url):
        calls.append(url)
        return {'url': url, 'name': 'Nuova', 'ingredients': ['Pasta 200g','Acqua 1l'],
                'steps': ['Cuoci.'], 'nutrition': {}, 'image_url': None}
    discover = lambda: [old[0]['url'], 'https://ricette.giallozafferano.it/B.html']
    assert run(20, 0, discover, fetcher, path, AllowAll()) == 1
    assert run(20, 0, discover, fetcher, path, AllowAll()) == 0
    data=json.loads(path.read_text(encoding='utf-8'))
    assert len(data)==2 and data[0]==old[0] and data[1]['needs_review'] is True
    assert len(calls)==1
