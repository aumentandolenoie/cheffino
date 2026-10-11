from datetime import datetime, timedelta, timezone
from ripara_catalogo import enrich, retry_due


def test_retry_old_incomplete_record():
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    rec = {"needs_review": True, "repaired_at": (now - timedelta(days=8)).isoformat(),
           "ingredients": [["Pinoli 15", None, "da verificare"]],
           "servings": 4, "steps": ["Cuoci"], "time": 20, "image_url": "https://example.org/img.jpg"}
    assert retry_due(rec, days=7, now=now) is True


def test_dont_retry_recent_record():
    now = datetime(2026, 10, 11, tzinfo=timezone.utc)
    rec = {"needs_review": True, "repaired_at": (now - timedelta(days=2)).isoformat(),
           "ingredients": [["Pinoli 15", None, "da verificare"]],
           "servings": 4, "steps": ["Cuoci"], "time": 20, "image_url": "https://example.org/img.jpg"}
    assert retry_due(rec, days=7, now=now) is False


def test_repair_preserves_verified_amount_for_same_source_label():
    old = {"needs_review": True, "name": "Pasta",
           "ingredients_display": ["Maggiorana 1 rametto", "Pomodoro 100 g"],
           "ingredients": [["Maggiorana", 1, "rametti"], ["Pomodoro", 100, "g"]],
           "steps": ["Taglia"], "servings": 4, "time": 20}
    raw = {"ingredients": ["Maggiorana 1 rametto", "Pomodoro 100 g"],
           "steps": ["Taglia"], "nutrition": {}}
    result = enrich(old, raw)
    assert result["ingredients"][0] == ["Maggiorana", 1, "rametti"]


def test_repair_doesnt_reuse_amount_when_source_changes():
    old = {"needs_review": True, "name": "Pasta",
           "ingredients_display": ["Maggiorana 1 rametto"],
           "ingredients": [["Maggiorana", 1, "rametti"]],
           "steps": ["Taglia"], "servings": 4, "time": 20}
    raw = {"ingredients": ["Maggiorana 3 rametti"], "steps": ["Taglia"], "nutrition": {}}
    result = enrich(old, raw)
    assert result["ingredients"][0][1] == 3
