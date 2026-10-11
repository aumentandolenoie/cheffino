import json
import pytest
from verifica_snapshot import compare


def test_previous_published_recipe_cannot_disappear(tmp_path):
    raw=tmp_path/"raw.json"
    new=tmp_path/"new.json"
    old=tmp_path/"old.json"
    def record(i):
        return {"id":i,"name":f"Ricetta {i}","url":f"https://example.org/{i}",
                "source":"Fonte","ingredients":[["Pasta",100,"g"]],"needs_review":False}
    raw.write_text(json.dumps([record(1)]),encoding="utf-8")
    new.write_text(json.dumps([record(1)]),encoding="utf-8")
    old.write_text(json.dumps([record(1),record(2)]),encoding="utf-8")
    with pytest.raises(ValueError,match="rimuove ricette"):
        compare(raw,new,old)


def test_same_previous_snapshot_is_allowed(tmp_path):
    raw=tmp_path/"raw.json"
    new=tmp_path/"new.json"
    old=tmp_path/"old.json"
    rec={"id":1,"name":"Pasta","url":"https://example.org/pasta",
         "source":"Fonte","ingredients":[["Pasta",100,"g"]],"needs_review":False}
    for path in (raw,new,old):
        path.write_text(json.dumps([rec]),encoding="utf-8")
    assert compare(raw,new,old)==(1,1)
