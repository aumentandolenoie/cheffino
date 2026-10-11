import json
import ripristina_passaggi_storici as repair
from ripristina_passaggi_storici import plan, run


class Permit:
    def can_fetch(self, user_agent, url):
        return True


def test_original_procedure_saved_in_both_catalogs_with_backup(tmp_path,monkeypatch):
    monkeypatch.setattr(repair, 'LEGACY_IDS', {4})
    a=tmp_path/"all.json"
    b=tmp_path/"published.json"
    rec={"id":4,"name":"Frittata di spinaci",
         "url":"https://ricette.giallozafferano.it/Frittata-di-spinaci.html",
         "steps":["Prepara e servi."],"step_images":[],
         "image_url":"https://www.giallozafferano.it/images/236-23641/cover.jpg"}
    for p in (a,b):
        p.write_text(json.dumps([rec]),encoding="utf-8")
    html='''<script type="application/ld+json">{
    "@type":"Recipe","name":"Frittata di spinaci",
    "recipeIngredient":["Spinaci 200 g"],
    "recipeInstructions":[
       {"@type":"HowToStep","text":"Lava gli spinaci."},
       {"@type":"HowToStep","text":"Cuoci gli spinaci."},
       {"@type":"HowToStep","text":"Servi la frittata."}]
    }</script>'''+''.join(f'<img alt="Frittata di spinaci - {n}" src="https://www.giallozafferano.it/images/236-23641/a{n}.jpg">' for n in range(1,4))
    changes=run(apply=False,source=a,published=b,fetcher=lambda _:html,policy=Permit())
    assert len(changes)==1
    assert json.loads(a.read_text())[0]["steps"]==["Prepara e servi."]
    changes=run(apply=True,source=a,published=b,fetcher=lambda _:html,policy=Permit())
    assert len(changes)==1
    assert json.loads(a.read_text())==json.loads(b.read_text())
    row=json.loads(a.read_text())[0]
    assert row["steps_precedenti"]==["Prepara e servi."]
    assert len(row["steps"])==3
    assert len(row["step_images"])==3
    assert row["images_import_version"]==10
