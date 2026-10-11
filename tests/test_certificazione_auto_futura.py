import json
from certifica_assenza_foto_fonte import plan
from app.photo_policy import certified_source_absence


class Permit:
    def can_fetch(self,agent,url):
        return True

def recipe(id,approved=True,has_photos=False):
    return {
        "id":id,"name":"Pasta di prova",
        "url":"https://ricette.giallozafferano.it/Pasta-di-prova.html",
        "image_url":"https://www.giallozafferano.it/images/236-23641/Pasta-di-prova_780x520_wm.jpg",
        "steps":["Mescola"],"source":"GialloZafferano",
        "validazione_automatica":{"approved":approved},
        "needs_review":not approved,
        "step_images":[["https://www.giallozafferano.it/images/ricette/236/23641/step_1.jpg"]] if has_photos else [],
    }

HTML='''<script type="application/ld+json">{
"@type":"Recipe","name":"Pasta di prova","image":"https://www.giallozafferano.it/images/236-23641/Pasta-di-prova_780x520_wm.jpg",
"recipeIngredient":["Pasta 120 g"],
"recipeInstructions":[{"@type":"HowToStep","text":"Mescola"}]
}</script>'''

HTML='<html>'+HTML+'<div class="gz-content-recipe-step"><p>Mescola</p></div></html>'

def test_auto_certifies_only_approved_without_real_step_photos(tmp_path):
    raw=tmp_path/"raw.json";pub=tmp_path/"pub.json"
    raw.write_text(json.dumps([recipe(1),recipe(2,False),recipe(3,True,True)]),encoding="utf-8")
    pub.write_text("[]",encoding="utf-8")
    calls=[]
    def fake_fetch(url):
        calls.append(url)
        return HTML
    data,_,ids=plan(raw,pub,fetcher=fake_fetch,policy=Permit(),auto=True,delay=0)
    assert ids==[1]
    assert len(calls)==1
    assert certified_source_absence(data[0])
    assert "step_photo_source_evidence" not in data[1]
    assert "step_photo_source_evidence" not in data[2]

def test_auto_rejects_mismatched_cover_identity(tmp_path):
    raw=tmp_path/"raw.json";pub=tmp_path/"pub.json"
    rec=recipe(1)
    rec["image_url"]="https://www.giallozafferano.it/images/555-55555/sbagliata.jpg"
    raw.write_text(json.dumps([rec]),encoding="utf-8")
    pub.write_text("[]",encoding="utf-8")
    rows,_,ids=plan(raw,pub,fetcher=lambda url:HTML,policy=Permit(),auto=True,delay=0)
    assert ids==[]
    assert not certified_source_absence(rows[0])

