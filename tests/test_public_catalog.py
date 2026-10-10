from app.public_catalog import public_catalog
from app.main import health, recipes

def test_bundle_api():
    rows=public_catalog()
    assert len(rows)>=10
    assert all(r.get('url') and r.get('id') is not None for r in rows)
    assert recipes()['count']==len(rows)
    assert health()['catalog_count']==len(rows)
