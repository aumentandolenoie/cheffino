import sys
from app.catalog import fetch_recipe,save

def main():
    if len(sys.argv)!=2:
        print('Uso: python importa_ricetta.py https://ricette.giallozafferano.it/...'); return 2
    try:
        recipe=fetch_recipe(sys.argv[1]);save(recipe)
        print(f"Importata: {recipe['name']} ({len(recipe['ingredients'])} ingredienti, {len(recipe['steps'])} passaggi)")
        if not recipe['nutrition']: print('Nota: valori nutrizionali non presenti nella pagina; nessun dato inventato.')
        return 0
    except Exception as e:
        print('Importazione non riuscita:',e);return 1
if __name__=='__main__': sys.exit(main())
