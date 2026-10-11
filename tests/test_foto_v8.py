from datetime import datetime, timedelta, timezone
from importa_foto_passaggi import (
    IMAGE_VERSION, ImagesHTML, missing_photos, should_recheck, valid_image
)


def test_missing_cover_even_when_nonempty_invalid_url():
    rec = {"url": "https://ricette.giallozafferano.it/Pasta.html",
           "image_url": "https://bad.example/image.jpg",
           "step_images": [["https://www.giallozafferano.it/images/a.jpg"]]}
    assert missing_photos(rec)


def test_missing_steps_with_cover():
    rec = {"url": "https://ricette.giallozafferano.it/Pasta.html",
           "image_url": "https://www.giallozafferano.it/images/236-23641/cover.jpg",
           "step_images": []}
    assert missing_photos(rec)


def test_recheck_expired_missing_cover():
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    rec = {"images_import_version": IMAGE_VERSION,
           "url": "https://ricette.giallozafferano.it/Pasta.html",
           "image_url": "https://bad.example/cover.jpg",
           "step_images": [["https://www.giallozafferano.it/images/a.jpg"]],
           "step_images_checked_at": (now - timedelta(days=8)).isoformat()}
    assert should_recheck(rec, now=now)


def test_source_strip_and_numbered_recognition():
    page = "https://ricette.giallozafferano.it/Pasta.html"
    html = """<img alt="Pasta" data-src="https://www.giallozafferano.it/images/236-23641/pasta_strip_1-3.jpg">
    <img alt="Pasta - 4" src="https://www.giallozafferano.it/images/236-23641/pasta_4.jpg">"""
    p = ImagesHTML("Pasta", page)
    p.feed(html)
    assert len(p.strips) == 1
    assert 4 in p.photos


def test_no_external_cover_accepted():
    assert valid_image("https://evil.example.com/cover.jpg",
                       "https://ricette.giallozafferano.it/Pasta.html") is None
