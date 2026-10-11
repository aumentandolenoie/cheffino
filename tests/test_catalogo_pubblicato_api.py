import json
from app import public_catalog as module


def test_snapshot_controls_visibility_and_keeps_total(tmp_path, monkeypatch):
    raw = tmp_path / "catalogo.json"
    snap = tmp_path / "pubblicato.json"
    entries = [
        {"id": 1, "name": "Disponibile", "url": "https://example.org/1",
         "source": "Giallozafferano", "needs_review": False},
        {"id": 2, "name": "Non pubblicata", "url": "https://example.org/2",
         "source": "Giallozafferano", "needs_review": False},
        {"id": 3, "name": "Nuova", "url": "https://example.org/3",
         "source": "Giallozafferano", "needs_review": True},
    ]
    raw.write_text(json.dumps(entries), encoding="utf-8")
    snap.write_text(json.dumps([entries[0]]), encoding="utf-8")
    monkeypatch.setattr(module, "CATALOG", raw)
    monkeypatch.setattr(module, "PUBLISHED", snap)
    rows = module.public_catalog()
    assert len(rows) == 3
    assert next(r for r in rows if r["id"] == 1)["needs_review"] is False
    assert next(r for r in rows if r["id"] == 2)["needs_review"] is True
    assert next(r for r in rows if r["id"] == 3)["needs_review"] is True


def test_no_snapshot_preserves_legacy_behavior(tmp_path, monkeypatch):
    raw = tmp_path / "catalogo.json"
    snap = tmp_path / "missing.json"
    raw.write_text(json.dumps([{"id": 5, "name": "Storica", "source": "Altro",
                               "needs_review": False}]), encoding="utf-8")
    monkeypatch.setattr(module, "CATALOG", raw)
    monkeypatch.setattr(module, "PUBLISHED", snap)
    assert module.public_catalog()[0]["needs_review"] is False


def test_snapshot_requires_same_source_url(tmp_path, monkeypatch):
    raw = tmp_path / "catalogo.json"
    snap = tmp_path / "pubblicato.json"
    raw.write_text(json.dumps([{"id": 1, "name": "A", "url": "https://example.org/a",
                                "needs_review": False}]), encoding="utf-8")
    snap.write_text(json.dumps([{"id": 1, "name": "B", "url": "https://example.org/b",
                                 "needs_review": False}]), encoding="utf-8")
    monkeypatch.setattr(module, "CATALOG", raw)
    monkeypatch.setattr(module, "PUBLISHED", snap)
    assert module.public_catalog()[0]["needs_review"] is True
