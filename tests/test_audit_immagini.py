from datetime import datetime, timedelta, timezone
from email.message import Message
from audit_immagini import inspect_record, safe_image_url, probe
from importa_foto_passaggi import should_recheck, IMAGE_VERSION


def test_missing_images_reported_without_data_mutation():
    rec = {"name": "Pasta", "image_url": None, "step_images": []}
    assert inspect_record(rec) == ["copertina_mancante", "foto_passaggi_mancanti"]


def test_wrong_recipe_id_is_flagged():
    rec = {"image_url": "https://www.giallozafferano.it/images/236-23641/cover.jpg",
           "step_images": [["https://www.giallozafferano.it/images/ricette/234/23442/step_1.jpg"]]}
    assert "id_foto_divergenti" in inspect_record(rec)


def test_unrecognized_url_id_is_not_treated_as_verified():
    rec = {"image_url": "https://www.giallozafferano.it/photos/cover.jpg",
           "step_images": [["https://www.giallozafferano.it/photos/step.jpg"]]}
    assert "identita_non_verificabile_da_url" in inspect_record(rec)


def test_reject_external_hosts():
    assert not safe_image_url("https://giallozafferano.it.evil.test/a.jpg")


def test_image_http_probe_verifies_content_type_and_redirect():
    class Response:
        status = 200
        headers = {"Content-Type": "image/jpeg"}
        def geturl(self):
            return "https://www.giallozafferano.it/images/a.jpg"
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
    assert probe("https://www.giallozafferano.it/images/a.jpg", opener=lambda *_a, **_kw: Response()) == "ok"


def test_image_retry_after_cooldown():
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    rec = {"images_import_version": IMAGE_VERSION, "image_url": "https://www.giallozafferano.it/a.jpg",
           "step_images": [], "step_images_checked_at": (now-timedelta(days=8)).isoformat()}
    assert should_recheck(rec, now=now) is True
    rec["step_images_checked_at"] = (now-timedelta(days=1)).isoformat()
    assert should_recheck(rec, now=now) is False
