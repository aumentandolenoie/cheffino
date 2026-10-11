from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("filename", ["index.html", "frontend/index.html"])
def test_catalog_search_available_and_javascript_valid(filename, tmp_path):
    html = (ROOT / filename).read_text(encoding="utf-8")
    for token in ("openRecipeSearch()", "catalogBrowse", "renderRecipeSearchResults",
                  "showRecipe(${r.id},true)", "Galleria parziale", "Senza foto passaggi"):
        assert token in html
    assert "let catalogTotal=0;" in html
    node = shutil.which("node")
    if node:
        js = html.split("<script>", 1)[1].split("</script>", 1)[0]
        script = tmp_path / "cheffino.js"
        script.write_text(js, encoding="utf-8")
        result = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
