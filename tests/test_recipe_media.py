import json
from pathlib import Path

from app.recipe_media import extract_media, display_groups
from app.public_catalog import _refresh_photo_fields
from importa_foto_passaggi import run

URL = 'https://ricette.giallozafferano.it/Pasta.html'
COVER = 'https://www.giallozafferano.it/images/236-23641/cover.jpg'
PHOTO = 'https://www.giallozafferano.it/images/ricette/236/23641/photo.jpg'


def page(instructions, body='', title='Pasta'):
    return '<html><script type="application/ld+json">' + json.dumps({
        '@type': 'Recipe', 'name': title, 'image': COVER,
        'recipeIngredient': ['Pasta 100 g'], 'recipeInstructions': instructions,
    }) + '</script>' + body + '</html>'


def test_jsonld_images_with_sections_and_restarted_numbers():
    instructions = [{'@type': 'HowToSection', 'name': section, 'itemListElement': [
        {'@type': 'HowToStep', 'text': f'Cuoci {section}.', 'image': PHOTO.replace('photo', section+'_strip_1-3')}
    ]} for section in ('sugo', 'pasta')]
    result = extract_media(page(instructions), URL, 'Pasta', ['Cuoci sugo.', 'Cuoci pasta.'])
    assert result['status'] == 'complete'
    assert [b['section'] for b in result['blocks']] == ['sugo', 'pasta']
    assert result['groups'][0] != result['groups'][1]


def test_unnumbered_dom_photos_and_picture_choose_one_asset():
    body = f'<div class="gz-content-recipe-step"><picture><source srcset="{PHOTO} 400w, {PHOTO}?large 1000w"><img src="{PHOTO}"></picture><p>Cuoci.</p></div>'
    result = extract_media(page(['Cuoci.'], body), URL, 'Pasta', ['Cuoci.'])
    assert result['groups'] == [[PHOTO+'?large']]
    assert result['method'] == 'jsonld-dom-blocks'


def test_strip_kept_whole_without_filename_inference():
    photo = PHOTO.replace('photo', 'collage_no_numbers')
    result = extract_media(page([{'text': 'Cuoci.', 'image': photo}]), URL, 'Pasta', ['Cuoci.'])
    assert result['groups'] == [[photo]]


def test_partial_gallery_does_not_mean_absence_or_completeness():
    result = extract_media(page([{'text': 'Cuoci.', 'image': PHOTO}, {'text': 'Servi.'}]), URL, 'Pasta', ['Cuoci.', 'Servi.'])
    assert result['status'] == 'partial'
    assert result['groups'] == [[PHOTO], []]


def test_advertising_and_nearby_images_are_not_step_evidence():
    result = extract_media(page(['Cuoci.'], f'<article><p>Cuoci.</p><img src="{PHOTO}"></article>'), URL, 'Pasta', ['Cuoci.'])
    assert result['status'] == 'unknown'
    assert not any(result['groups'])


def test_mismatching_dom_order_is_not_assigned():
    body = ''.join(f'<div class="gz-content-recipe-step"><p>{text}</p><img src="{PHOTO}"></div>' for text in ('Servi.', 'Cuoci.'))
    result = extract_media(page(['Cuoci.', 'Servi.'], body), URL, 'Pasta', ['Cuoci.', 'Servi.'])
    assert not any(result['groups'])


def test_different_source_identity_and_changed_procedure():
    assert extract_media(page(['Cuoci.'], title='Altra'), URL, 'Pasta', ['Cuoci.'])['reason'] == 'source_identity_changed'
    assert extract_media(page(['Cuoci.']), URL, 'Pasta', ['Friggi le patate.'])['reason'] == 'procedure_changed_or_unmapped'


def test_foreign_recipe_photo_rejected():
    result = extract_media(page([{'text': 'Cuoci.', 'image': PHOTO.replace('236/23641', '222/22290')}]), URL, 'Pasta', ['Cuoci.'])
    assert result['reason'] == 'foreign_image'
    assert result['groups'] == []


def test_malformed_or_blocked_source_never_certifies_absence():
    for html in ('', '<html>Access denied</html>', '<script type="application/ld+json">invalid</script>'):
        assert extract_media(html, URL, 'Pasta', ['Cuoci.'])['status'] == 'unknown'


def test_blog_structured_steps_use_same_pipeline():
    base = 'https://blog.giallozafferano.it/example/pasta/'
    photo = 'https://blog.giallozafferano.it/example/wp-content/uploads/pasta.jpg'
    result = extract_media(page([{'text': 'Cuoci.', 'image': photo}]), base, 'Pasta', ['Cuoci.'])
    assert result['groups'] == [[photo]]


def test_api_does_not_overlay_images_on_a_changed_procedure():
    old = {'steps': ['Cuoci.'], 'step_images': [[PHOTO]], 'image_url': COVER}
    new = dict(old, steps=['Friggi.'], step_images=[[PHOTO+'?new']])
    assert _refresh_photo_fields(old, new)['step_images'] == [[PHOTO]]


def test_existing_gallery_is_preserved_and_dry_run_is_read_only(tmp_path):
    path = tmp_path/'raw.json'
    rec = {'id': 1, 'name': 'Pasta', 'source': 'GialloZafferano', 'url': URL,
           'steps': ['Cuoci.'], 'image_url': COVER, 'step_images': [[PHOTO+'?old']], 'images_import_version': 0}
    path.write_text(json.dumps([rec])); original = path.read_bytes()
    class Permit:
        def can_fetch(self, *_): return True
    kwargs = dict(catalog_path=path, delay=0, policy=Permit(), fetcher=lambda _:page([{'text': 'Cuoci.', 'image': PHOTO}]))
    report = tmp_path/'report.json'
    run(**kwargs, dry_run=True, report_path=report)
    assert path.read_bytes() == original
    assert json.loads(report.read_text())[0]['candidate_differs'] is True
    run(**kwargs)
    assert json.loads(path.read_text())[0]['step_images'] == rec['step_images']


def test_legacy_display_preserves_old_mapping_and_new_sections_stay_local():
    strip = PHOTO.replace('photo', 'pasta_strip_1-3')
    rec = {'steps': ['A', 'B', 'C'], 'step_images': [[strip], [strip], [strip]], 'images_import_version': 7}
    assert display_groups(rec) == [[strip], [], []]
    rec['images_import_version'] = 11
    assert display_groups(rec) == [[strip], [strip], [strip]]


def test_published_catalog_media_projection_keeps_all_legacy_assets():
    rows = json.loads((Path(__file__).parents[1]/'data/catalogo_pubblicato.json').read_text())
    for rec in rows:
        before = {u for group in rec.get('step_images', []) for u in group}
        after = {u for group in display_groups(rec) for u in group}
        assert after == before, rec['name']


def test_absence_requires_complete_recognized_page_and_no_inline_media():
    from certifica_assenza_foto_fonte import absence_verified
    complete = page(['Cuoci.'], '<div class="gz-content-recipe-step"><p>Cuoci.</p></div>')
    assert absence_verified(complete, URL, 'Pasta', '23641')
    assert not absence_verified(complete.replace('</html>', ''), URL, 'Pasta', '23641')
    assert not absence_verified(page(['Cuoci.']), URL, 'Pasta', '23641')
    inline = complete.replace('</p>', '</p><img src="https://other.test/unrecognized.jpg">')
    assert not absence_verified(inline, URL, 'Pasta', '23641')


def test_audit_accepts_certified_absence():
    from audit_immagini import inspect_record
    rec = {'url': URL, 'image_url': COVER, 'step_images': [], 'step_photo_source_evidence': {
        'status': 'verified_absent', 'source_url': URL, 'recipe_image_id': '23641',
        'verified_at': '2026-10-11T15:00:00+00:00', 'method': 'gz-full-html-article-no-steps-v1'}}
    assert 'foto_passaggi_mancanti' not in inspect_record(rec)
