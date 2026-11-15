"""Copertine segnaposto e foto dei passaggi leggibili."""
import json

import controlla_copertine as cc

OLD = 'https://www.giallozafferano.it/images/ricette/39/3981/foto_hd/hd650x433_wm.jpg'
OG = 'https://www.giallozafferano.it/images/39-3981/Insalata-di-farro-con-verdure_650x433_wm.jpg'
HI = OG.replace('_650x433_wm', '_780x520_wm')
PAGE = f'<meta property="og:image" content="{OG}" />'


def img(sha, w=650, h=433):
    return {'sha256': sha, 'width': w, 'height': h, 'bytes': 1000}


def test_image_size_jpeg_png():
    png = b'\x89PNG\r\n\x1a\n' + b'\x00\x00\x00\rIHDR' + (780).to_bytes(4, 'big') + (520).to_bytes(4, 'big')
    assert cc.image_size(png) == (780, 520)
    jpeg = b'\xff\xd8' + b'\xff\xe0\x00\x04\x00\x00' + b'\xff\xc0\x00\x11\x08' + (433).to_bytes(2, 'big') + (650).to_bytes(2, 'big') + b'\x00' * 10
    assert cc.image_size(jpeg) == (650, 433)


def test_page_candidates_og_image():
    assert cc.page_candidates(PAGE, 'https://ricette.giallozafferano.it/X.html')[0] == OG


def test_segnaposto_sostituito_dalla_foto_della_fonte(tmp_path, monkeypatch):
    known = tmp_path / 'k.json'
    known.write_text(json.dumps(['logo']))
    monkeypatch.setattr(cc, 'KNOWN_PLACEHOLDERS', known)
    images = {OLD: img('logo'), OG: img('piatto'), HI: img('piatto-hd', 780, 520)}
    rec = {'id': 1, 'name': 'Insalata di farro', 'url': 'https://ricette.giallozafferano.it/X.html', 'image_url': OLD}
    results, placeholders = cc.scan([rec], delay=0, fetch_page=lambda u: PAGE, fetch_img=lambda u: images[u])
    assert results[0]['esito'] == 'sostituibile' and results[0]['nuova_copertina']['url'] == HI
    cat, pub = tmp_path / 'c.json', tmp_path / 'p.json'
    cat.write_text(json.dumps([rec]))
    pub.write_text(json.dumps([rec]))
    assert cc.apply(results, placeholders, (cat, pub)) == 2
    for path in (cat, pub):
        saved = json.loads(path.read_text())[0]
        assert saved['image_url'] == HI and saved['copertina_verifica']['precedente'] == OLD


def test_foto_di_altra_ricetta_scartata_e_segnaposto_senza_alternativa(tmp_path, monkeypatch):
    known = tmp_path / 'k.json'
    known.write_text(json.dumps(['logo']))
    monkeypatch.setattr(cc, 'KNOWN_PLACEHOLDERS', known)
    other = 'https://www.giallozafferano.it/images/12-1234/Altro_650x433_wm.jpg'
    page = f'<meta property="og:image" content="{other}" />'
    rec = {'id': 1, 'name': 'X', 'url': 'https://ricette.giallozafferano.it/X.html', 'image_url': OLD}
    results, _ = cc.scan([rec], delay=0, fetch_page=lambda u: page, fetch_img=lambda u: img('logo') if u == OLD else img('altro'))
    assert results[0]['esito'] == 'segnaposto'


def test_copertina_gia_corretta_resta(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, 'KNOWN_PLACEHOLDERS', tmp_path / 'none.json')
    rec = {'id': 1, 'name': 'X', 'url': 'https://ricette.giallozafferano.it/X.html', 'image_url': HI}
    results, _ = cc.scan([rec], delay=0, fetch_page=lambda u: PAGE,
                         fetch_img=lambda u: img('piatto-hd', 780, 520) if u == HI else img('piatto'))
    assert results[0]['esito'] == 'ok'


def test_frontend_foto_passaggi_grandi_e_strip_divise():
    for path in ('frontend/index.html', 'index.html'):
        html = open(path, encoding='utf-8').read()
        assert 'function stepShots' in html and 'function openPhoto' in html
        assert 'grid-template-columns:repeat(3' not in html.split('.step-photos')[1][:400]
        assert "segnaposto_senza_alternativa" in html


def test_pagina_sotto_bloccata_con_ricetta_o_foto_aperta():
    for path in ('frontend/index.html', 'index.html'):
        html = open(path, encoding='utf-8').read()
        assert 'function syncScrollLock' in html and 'new MutationObserver(syncScrollLock)' in html
        assert "position:'fixed'" in html and 'overscroll-behavior:contain' in html
        assert "classList.add('open');syncScrollLock()" in html


def test_niente_zoom_accidentale():
    for path in ('frontend/index.html', 'index.html'):
        html = open(path, encoding='utf-8').read()
        assert 'maximum-scale=1' in html and 'touch-action:manipulation' in html
        assert 'font-size:16px!important' in html                  # niente zoom automatico sui campi
        assert "addEventListener('gesturestart',block" in html      # pizzico bloccato nell'app installata
        assert 'function togglePhotoZoom' in html                   # le foto restano ingrandibili
