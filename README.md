# Cheffino — Render Free

Questa build pubblica la grafica attuale di Cheffino e le API Python su Render.

## Pubblicazione
1. Estrai lo ZIP. Su GitHub crea un repository privato e carica **i contenuti** della cartella `cheffino_render` alla radice del repository.
2. Render > New > Blueprint, connetti il repository e conferma il piano Free e il servizio `cheffino`.
3. In alternativa: New > Web Service, Python 3, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Free.
4. Apri l'indirizzo HTTPS `...onrender.com` assegnato e controlla anche `/api/health`.

## Stato reale
- `frontend/index.html`: app corrente; il catalogo visibile al momento è ancora incorporato nell'HTML.
- `/api/recipes`: lettura del catalogo SQLite separato; non ancora connesso all'interfaccia.
- `importa_ricetta.py`: importazione manuale sperimentale dai dati JSON-LD delle pagine, non aggiornamento automatico.
- In Render Free le modifiche fatte al database SQLite **durante l'esecuzione** non persistono dopo restart/redeploy: il database nel repository fa da snapshot iniziale. Nuovi dati andranno salvati nel repository e ridistribuiti oppure in un datastore persistente.
- Le preferenze salvate in `localStorage` si trovano soltanto nel browser dell'iPhone; usa il backup nelle Preferenze. Cambiare dominio, cancellare dati Safari o usare navigazione privata può comportare perdita dello stato.
- Questa versione non offre ancora autenticazione privata: chi conosce l'URL può aprire l'app. Evita dati personali sensibili.
