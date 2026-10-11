import json
from app import public_catalog as module


def test_updated_cover_and_step_photos_reach_public_api(tmp_path, monkeypatch):
    raw = tmp_path / "raw.json"
    snap = tmp_path / "published.json"
    old = {"id": 1, "name": "Pasta", "url": "https://ricette.giallozafferano.it/Pasta.html",
           "source": "GialloZafferano", "ingredients": [["Pasta", 100, "g"]],
           "steps": ["Cuoci"], "needs_review": False,
           "validazione_automatica": {"approved": True}, "image_url": None,
           "step_images": []}
    latest = dict(old, image_url="https://www.giallozafferano.it/images/236-23641/pasta.jpg",
                  step_images=[["https://ricette.giallozafferano.it/images/ricette/236/23641/step1.jpg"]],
                  ingredients=[["Pasta", None, "da verificare"]])
    snap.write_text(json.dumps([old]), encoding="utf-8")
    raw.write_text(json.dumps([latest]), encoding="utf-8")
    monkeypatch.setattr(module, "CATALOG", raw)
    monkeypatch.setattr(module, "PUBLISHED", snap)
    rec = module.public_catalog()[0]
    assert rec["image_url"] == latest["image_url"]
    assert rec["step_images"] == latest["step_images"]
    assert rec["ingredients"] == old["ingredients"]
    assert rec["needs_review"] is False


def test_reject_foreign_photo_in_working_catalog():
    base = {"image_url": "https://www.giallozafferano.it/images/236-23641/cover.jpg",
            "step_images": []}
    working = {"image_url": "https://evil.test/cover.jpg",
               "step_images": [["https://www.giallozafferano.it/images/ricette/222/22222/step.jpg"]]}
    merged = module._refresh_photo_fields(base, working)
    assert merged["image_url"] == base["image_url"]
    assert merged["step_images"] == []


def test_keep_legacy_photo_when_working_catalog_is_empty():
    old = {"image_url": "https://www.giallozafferano.it/images/236-23641/cover.jpg"}
    updated = module._refresh_photo_fields(old, {"image_url": None, "step_images": []})
    assert updated["image_url"] == old["image_url"]
