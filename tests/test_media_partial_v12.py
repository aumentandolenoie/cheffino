import json
from datetime import datetime, timedelta, timezone

from importa_foto_passaggi import IMAGE_VERSION, missing_photos, run, should_recheck

URL = "https://ricette.giallozafferano.it/Pasta.html"
COVER = "https://www.giallozafferano.it/images/236-23641/cover.jpg"
OLD = "https://www.giallozafferano.it/images/ricette/236/23641/old.jpg"
NEW = "https://www.giallozafferano.it/images/ricette/236/23641/new.jpg"
SECOND = "https://www.giallozafferano.it/images/ricette/236/23641/second.jpg"


class Permit:
    def can_fetch(self, *_args):
        return True


def html_page():
    return "<html><script type='application/ld+json'>" + json.dumps({
        "@type": "Recipe", "name": "Pasta", "image": COVER,
        "recipeIngredient": ["Pasta 100 g"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Cuoci.", "image": NEW},
            {"@type": "HowToStep", "text": "Servi.", "image": SECOND},
        ],
    }) + "</script></html>"


def rec(version=11):
    return {
        "id": 1, "name": "Pasta", "source": "GialloZafferano", "url": URL,
        "image_url": COVER, "steps": ["Cuoci.", "Servi."],
        "step_images": [[OLD], []],
        "images_import_version": version,
        "media_extraction_version": version,
        "step_images_checked_at": "2026-09-01T00:00:00+00:00",
    }


def test_partial_gallery_is_missing_and_retried_after_cooldown():
    original = rec(IMAGE_VERSION)
    assert missing_photos(original)
    recent = datetime(2026, 9, 2, tzinfo=timezone.utc)
    later = recent + timedelta(days=9)
    assert not should_recheck(original, now=recent)
    assert should_recheck(original, now=later)
    original["step_images"] = [[OLD], [SECOND]]
    assert not missing_photos(original)
    assert not should_recheck(original, now=later)


def test_only_empty_verified_blocks_are_filled(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([rec()]))
    report = tmp_path / "report.json"
    args = dict(catalog_path=path, limit=1, delay=0, policy=Permit(),
                fetcher=lambda _: html_page(), report_path=report)
    run(**args, dry_run=True)
    assert json.loads(path.read_text())[0]["step_images"] == [[OLD], []]
    assert json.loads(report.read_text())[0]["steps_filled"] == 1
    run(**args)
    result = json.loads(path.read_text())[0]
    assert result["step_images"] == [[OLD], [SECOND]]
    assert result["images_import_version"] == IMAGE_VERSION
    assert result["step_media_blocks"][0]["images"] == [OLD]
    assert json.loads(report.read_text())[0]["effective_status"] == "complete"


def test_legacy_associations_are_not_mixed_automatically(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps([rec(version=7)]))
    run(catalog_path=path, limit=1, delay=0, policy=Permit(),
        fetcher=lambda _: html_page())
    assert json.loads(path.read_text())[0]["step_images"] == [[OLD], []]
