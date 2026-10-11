# Cheffino: revisione del flusso dati (ramo sperimentale)

## Stato e sicurezza
Questa modifica viene realizzata su un ramo separato e non modifica il deploy corrente.
La versione di produzione legge ancora `data/catalogo.json` attraverso
`app/public_catalog.py`. Il nuovo file `data/catalogo_pubblicato.json`
è uno snapshot separato: NON diventa il catalogo live finché il backend
non viene migrato e testato esplicitamente.

## Tre workflow
- **01 Raccolta**: scopre 10 nuove fonti alla settimana, salva in revisione.
- **02 Arricchimento**: due volte a settimana tenta riparazioni e recupero immagini,
  esegue due volte il controllo integrità (prima e dopo l'importazione).
- **03 Verifica/pubblicazione**: due volte a settimana esegue pytest,
  riclassifica, valida, ricontrolla identità fotografica e genera snapshot separato.

Tutti usano lo stesso gruppo di concorrenza per evitare scritture simultanee.
Le pianificazioni sono sfalsate. Nessun workflow è sicuro contro una modifica
concorrente effettuata manualmente durante l'esecuzione: valutare protezione branch.

## Limiti ancora aperti (non dichiarare risolti)
- `ripara_catalogo.py` ora ritenta dopo sette giorni le schede incomplete e
  preserva le quantità già normalizzate se il testo della fonte non cambia.
- `valida_catalogo.py` non controlla HTTP 200 delle copertine.
- `controlla_integrita_catalogo.py` riconosce soltanto alcuni URL foto:
  ID sconosciuto non implica corrispondenza verificata.
- `importa_foto_passaggi.py` ora ritenta dopo sette giorni le immagini mancanti,
  e non associa gallerie ai procedimenti che divergono dalla fonte.
- `audit_immagini.py` esamina problemi di copertina/galleria e può verificare un
  campione limitato di URL HTTP (`--online --limit 12`). Non modifica schede;
  un errore HTTP potrebbe dipendere da anti-hotlink o altri limiti di rete.
- Per la pubblicazione definitiva servono ancora controlli più completi sulle
  immagini e una prova end-to-end dei workflow.
- Non si certificano allergie/intolleranze, calorie o costi.
- Non serve trasferire immagini di GialloZafferano nel repository.
- `aggiorna-catalogo.yml` alla radice è un duplicato NON eseguito da Actions.
- `index.html` alla radice NON è servito da `app/main.py`.
- `data/ricette.sqlite3` è usato dagli import manuali, non dalla API live.

## Passaggio successivo prima del merge
Disattivare la schedulazione del vecchio workflow `aggiorna-catalogo.yml`
nella cartella `.github/workflows/`; eseguire la prova completa dei tre
workflow e confrontare lo snapshot con il catalogo corrente; solo dopo
migrare il backend allo snapshot verificato. Non eliminare i dati storici.
