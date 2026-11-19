from app.public_catalog import public_catalog
from app.main import health, recipes

def test_bundle_api():
    rows=public_catalog()
    assert len(rows)>=10
    assert all(r.get('url') and r.get('id') is not None for r in rows)
    # l'app riceve tutto tranne le ricette escluse per scelta
    assert recipes()['count']==len([r for r in rows if not r.get('esclusa_dal_piano')])
    assert health()['catalog_count']==len(rows)
