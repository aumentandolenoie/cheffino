import json
from importa_foto_passaggi import run


class PermitAll:
    def can_fetch(self, agent, url):
        return True


def test_forced_mode_visits_only_incomplete_published(tmp_path):
    source=tmp_path/"catalog.json"
    published=tmp_path/"published.json"
    def rec(i, steps=None):
        return {
            "id": i, "name": f"Ricetta {i}", "source": "GialloZafferano",
            "url": f"https://ricette.giallozafferano.it/Ricetta-{i}.html",
            "steps": steps or ["Mescola"],
            "image_url": "https://www.giallozafferano.it/images/236-23641/cover.jpg",
            "step_images": [], "images_import_version": 8,
            "step_images_checked_at": "2026-10-11T11:00:00+00:00",
        }
    source.write_text(json.dumps([rec(1),rec(2),rec(3)]),encoding="utf-8")
    published.write_text(json.dumps([rec(2)]),encoding="utf-8")
    attempted=[]
    def fake_fetch(url):
        attempted.append(url)
        return "<html><head></head><body></body></html>"
    run(catalog_path=source,published_path=published,limit=35,delay=0,
        fetcher=fake_fetch,policy=PermitAll(),published_only=True,force=True)
    assert attempted==["https://ricette.giallozafferano.it/Ricetta-2.html"]


def test_published_only_requires_snapshot(tmp_path):
    source=tmp_path/"catalog.json"
    source.write_text("[]",encoding="utf-8")
    import pytest
    with pytest.raises(ValueError, match="pubblicato assente"):
        run(catalog_path=source,published_path=tmp_path/"missing.json",
            limit=1,delay=0,policy=PermitAll(),published_only=True,force=True)
