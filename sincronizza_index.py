"""Copia frontend/index.html (la versione servita dall'app) in index.html nella radice."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
shutil.copyfile(ROOT / 'frontend' / 'index.html', ROOT / 'index.html')
print('index.html allineato a frontend/index.html')
