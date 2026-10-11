import json
from pubblica_catalogo import eligible, publish

def sample(**kwargs):
    rec = dict(id=1, name="Ricetta fonte", url="https://ricette.giallozafferano.it/a.html",
               image_url="https://www.giallozafferano.it/images/236-23641/a.jpg",
               steps=["Mescola"], needs_review=False,
               validazione_automatica={"approved": True})
    rec.update(kwargs)
    return rec

def test_reject_review():
    assert eligible(sample(needs_review=True))[0] is False

def test_reject_foreign_photo():
    rec=sample(step_images=[["https://www.giallozafferano.it/images/ricette/234/23442/a_1.jpg"]])
    assert eligible(rec)==(False, "foto_di_altra_ricetta")

def test_export_only_approved(tmp_path):
    source=tmp_path/"source.json"
    target=tmp_path/"published.json"
    source.write_text(json.dumps([sample(),sample(id=2,name="Da rivedere",url="https://ricette.giallozafferano.it/b.html",needs_review=True)]),encoding="utf-8")
    assert len(publish(source,target))==1
    assert len(json.loads(target.read_text()))==1

def test_prevent_empty_overwrite(tmp_path):
    source=tmp_path/"source.json"
    target=tmp_path/"published.json"
    target.write_text("previous",encoding="utf-8")
    source.write_text(json.dumps([sample(needs_review=True)]),encoding="utf-8")
    try:
        publish(source,target)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected ValueError")
    assert target.read_text()=="previous"
