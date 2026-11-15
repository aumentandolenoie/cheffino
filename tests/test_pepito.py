"""Nome e icona dell'app: Pepito con il trita pepe."""
import json
from pathlib import Path


def test_nome_e_icone():
    for path in ('frontend/index.html', 'index.html'):
        html = Path(path).read_text(encoding='utf-8')
        assert '<title>Pepito' in html and 'content="Pepito"' in html and '</div>Pepito</div>' in html
        assert 'href="/icons/apple-touch-icon.png"' in html and 'href="/manifest.webmanifest"' in html
        import re
        visible = re.sub(r'(?:import|export)CheffinoBackup', '', html)  # nomi interni delle funzioni
        assert 'Cheffino' not in visible and '👨‍🍳' not in html
        # dati salvati e vecchi backup restano validi
        assert "localStorage.getItem('cheffinoState')" in html
        assert "['pepito','cheffino'].includes(payload.application)" in html
    manifest = json.loads(Path('manifest.webmanifest').read_text(encoding='utf-8'))
    assert manifest['short_name'] == 'Pepito'
    for icon in manifest['icons']:
        assert Path(icon['src'].lstrip('/')).exists()
    assert Path('icons/apple-touch-icon.png').read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'


def test_server_espone_solo_le_icone():
    import pytest
    pytest.importorskip('fastapi')
    from fastapi import HTTPException
    from app import main
    assert str(main.icon('apple-touch-icon.png').path).endswith('icons/apple-touch-icon.png')
    with pytest.raises(HTTPException):
        main.icon('../data/catalogo.json')
