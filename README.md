# Cheffino — Catalogo collegato a Render

Questa release collega davvero `/api/recipes` al piano settimanale e alle schede ricetta.
Il catalogo `data/catalogo.json` è versionato su GitHub e sopravvive ai riavvii di Render Free.

## Installazione

Carica **tutto il contenuto** di questa cartella nella radice del repository GitHub
`cheffino`, sostituendo i file con lo stesso nome. Non modificare Render: il
commit farà partire il deploy automatico se abilitato.

Verifica su `https://TUO-SITO.onrender.com/api/health` e poi `/api/recipes`.

## Aggiungere ricette

`python importa_ricetta.py "https://ricette.giallozafferano.it/..."` aggiorna
`data/catalogo.json` sul PC, non sul server Render. Le nuove schede sono
`needs_review: true` per evitare ingredienti o quantità mal interpretate.
Solo dopo controllo umano e classificazione (porzioni, allergeni,
strumenti, tipo di pasto) rimuovere quel flag e fare commit del file.

## Limiti

- Il catalogo iniziale contiene le schede già presenti nella versione HTML,
  non l'intero catalogo di GialloZafferano.
- La provenienza e la correttezza delle schede ereditate dalla demo richiedono
  ancora una verifica editoriale indipendente. Non sono state scaricate o
  verificate dal vivo durante questo aggiornamento.
- Render Free non deve salvare aggiunte permanenti nel suo filesystem.
- I dati personali restano nel localStorage di Safari, con backup nelle Preferenze.
- L'importatore richiede disponibilità del JSON-LD e rispetto delle condizioni del sito.
