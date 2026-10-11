import json
from app.photo_policy import certified_source_absence,has_step_gallery,publishable_step_photos
from app import public_catalog as module
from pubblica_catalogo import eligible


def record():
    return {
        "id":211658408928202,"name":"Insalata di farro alla greca",
        "url":"https://ricette.giallozafferano.it/Insalata-di-farro-alla-greca.html",
        "image_url":"https://www.giallozafferano.it/images/222-22290/Insalata-di-farro-alla-greca_780x520_wm.jpg",
        "steps":["Cuoci il farro"],"ingredients":[["Farro",120,"g"]],
        "validazione_automatica":{"approved":True},
        "source":"GialloZafferano",
        "needs_review":False,"step_images":[]}


def proof():
    return {
        "status":"verified_absent",
        "source_url":"https://ricette.giallozafferano.it/Insalata-di-farro-alla-greca.html",
        "recipe_image_id":"22290",
        "verified_at":"2026-10-11T13:39:00+00:00",
        "method":"gz-full-html-article-no-steps-v1"}


def test_missing_photos_no_proof_is_not_publishable():
    r=record()
    assert not publishable_step_photos(r)
    assert eligible(r)==(False,"foto_passaggi_non_verificate")


def test_absent_gallery_with_proof_remains_publishable():
    r=record();r["step_photo_source_evidence"]=proof()
    assert certified_source_absence(r)
    assert eligible(r)==(True,"ok")


def test_fake_or_stale_proof_does_not_allow_publication():
    for field,value in (("source_url","https://example.org/other"),
                        ("recipe_image_id","99999"),
                        ("method","guess_from_parser"),
                        ("status","unknown")):
        r=record()
        r["step_photo_source_evidence"]=dict(proof(),**{field:value})
        assert not certified_source_absence(r)


def test_photo_always_allows_gallery():
    r=record()
    r["step_images"]=[["https://www.giallozafferano.it/images/ricette/222/22290/1.jpg"]]
    assert has_step_gallery(r)
    assert eligible(r)==(True,"ok")


def test_api_shows_approved_no_gallery_only_with_proof(tmp_path,monkeypatch):
    raw=tmp_path/"catalogo.json";pub=tmp_path/"snapshot.json"
    r=record()
    raw.write_text(json.dumps([r]),encoding="utf-8")
    pub.write_text(json.dumps([r]),encoding="utf-8")
    monkeypatch.setattr(module,"CATALOG",raw)
    monkeypatch.setattr(module,"PUBLISHED",pub)
    assert module.public_catalog()[0]["needs_review"] is True
    r["step_photo_source_evidence"]=proof()
    raw.write_text(json.dumps([r]),encoding="utf-8")
    assert module.public_catalog()[0]["needs_review"] is False
