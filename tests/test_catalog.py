from app.catalog import parse_recipe,validate_url
import pytest

def test_extract():
    html='''<script type="application/ld+json">{"@context":"https://schema.org","@type":"Recipe","name":"Test","recipeIngredient":["100 g elemento"],"recipeInstructions":[{"@type":"HowToStep","text":"Mescola."}],"nutrition":{"calories":"120 kcal"}}</script>'''
    r=parse_recipe(html,'https://ricette.giallozafferano.it/test.html')
    assert r['ingredients']==['100 g elemento']
    assert r['steps']==['Mescola.']
    assert r['nutrition']['calories']=='120 kcal'

def test_reject():
    with pytest.raises(ValueError): validate_url('http://evil.example/a')
    with pytest.raises(ValueError): validate_url('https://giallozafferano.it.evil.example/a')
