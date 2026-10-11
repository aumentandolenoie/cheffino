import json
from certifica_assenza_foto_fonte import absence_verified, VERSION


URL="https://ricette.giallozafferano.it/Insalata-di-farro-alla-greca.html"
ID="22290"
HEAD='''<script type="application/ld+json">{
"@type":"Recipe","name":"Insalata di farro alla greca",
"recipeIngredient":["Farro 120 g"],
"recipeInstructions":[{"@type":"HowToStep","text":"Mescola il farro."}]
}</script>'''

HEAD='<html>'+HEAD+'<div class="gz-content-recipe-step"><p>Mescola il farro.</p></div></html>'

def test_real_absence_needs_actual_page_and_no_step_photos():
    assert absence_verified(HEAD,URL,"Insalata di farro alla greca",ID)
    assert VERSION.startswith("gz-full-html")

def test_refuse_source_with_photo_identified_even_when_parser_does_not_map():
    page=HEAD+'<img alt="altra immagine" src="/images/ricette/222/22290/step_x.jpg">'
    assert not absence_verified(page,URL,"Insalata di farro alla greca",ID)

def test_refuse_source_with_jsonld_photographed_step():
    page=HEAD.replace('{"@type":"HowToStep","text":"Mescola il farro."}',
                     '{"@type":"HowToStep","text":"Mescola il farro.","image":"https://www.giallozafferano.it/x.jpg"}')
    assert not absence_verified(page,URL,"Insalata di farro alla greca",ID)

def test_refuse_source_with_wrong_recipe():
    assert not absence_verified(HEAD,URL,"Pasta al limone",ID)

def test_refuse_numbered_gallery():
    page=HEAD+'<img alt="Insalata di farro alla greca - 1" src="/images/ricette/222/22290/a_1.jpg">'
    assert not absence_verified(page,URL,"Insalata di farro alla greca",ID)

