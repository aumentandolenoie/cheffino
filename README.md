# Pepito (ex Cheffino)

Web app per organizzare i pasti della settimana: onboarding con le tue
preferenze, proposte da valutare, piano settimanale, lista della spesa e
volantini dei supermercati. Le ricette provengono solo da fonti pubblicate
(GialloZafferano); nulla viene inventato.

## Dove gira

- **App**: Vercel, progetto `pepito` (preset FastAPI, funzioni a Francoforte).
  `app/main.py` serve la pagina (`frontend/index.html`), le icone e le API
  `/api/recipes` e `/api/volantini`. Ogni commit su `main` fa un nuovo deploy.
- **Dati**: file in `data/`, aggiornati dalle automazioni GitHub (sotto) con
  un commit; la CDN di Vercel li tiene in cache fino al deploy successivo.
- **Sul telefono**: un service worker (`frontend/sw.js`) salva pagina e ricette,
  così l'app si apre subito e funziona anche senza rete. Preferenze, piano e
  spunte della spesa restano sul dispositivo (backup dalle Preferenze).
- `index.html` nella radice è una copia identica di `frontend/index.html`
  (verificata dai test; si riallinea con `python sincronizza_index.py`).

## Automazioni (GitHub Actions)

| Workflow | Quando | Cosa fa |
|---|---|---|
| 01 Raccolta | lunedì e giovedì | 10 ricette nuove, validazione, foto dei passaggi |
| 02 Arricchimento | ogni giorno | ricontrolla le schede con la fonte, foto e copertine |
| 03 Pubblicazione | mercoledì e venerdì | test e pubblicazione delle ricette complete |
| 04 Audit / 05 Copertine | a mano | confronto completo con la fonte, copertine segnaposto |
| 06 Volantini | ogni 6 ore | volantino in corso di ogni supermercato |
| Test qualità | a ogni modifica | tutti i test |

GitHub avvia gli orari pianificati anche con diverse ore di ritardo: è normale.
Dettagli dei controlli in `PIPELINE_QUALITA.md`.

## Come l'app usa le tue scelte

- **Esigenze alimentari** (`app/diete.py`): entrano solo ricette compatibili.
- **Stili** (`app/stili.py`): calcolati da tempo, costo, calorie e ingredienti
  della fonte; il piano usa solo ricette con gli stili scelti quando ce ne sono
  abbastanza.
- **Budget**: euro a porzione = budget ÷ pasti ÷ persone; orienta verso ricette
  dal costo basso secondo la fonte (i prezzi reali non sono disponibili).
- **Tempo**: pranzi feriali veloci, preparazioni lunghe nel fine settimana.
- **Strumenti, tipi di piatto, ingredienti esclusi**: filtri sempre rispettati.

## Volantini

Premendo «Volantino» l'app apre subito l'ultimo volantino ufficiale del
supermercato scelto (con più supermercati compare prima la scelta).
`aggiorna_volantini.py` legge solo le pagine ufficiali dei marchi elencate in
`app/volantini.py` e scrive `data/volantini.json`:

- catene con volantino nazionale (Aldi, Bennet, Dodecà, Eurospin, Lidl, MD):
  link diretto al volantino in corso con le date di validità, più il prossimo
  se è già pubblicato; quando inizia, l'app apre quello nuovo anche prima del
  controllo successivo. Lidl chiede di scegliere il punto vendita sul suo sito;
- catene con offerte per zona o negozio (Conad, Coop, Esselunga, Carrefour,
  Despar, Famila, PAM, Tigros, Penny, Il Gigante, Alì, Decò, Sole365): si apre la
  pagina ufficiale dei volantini, dove si sceglie il proprio punto vendita;
- volantino scaduto o pagina non leggibile: si apre la pagina ufficiale dei
  volantini, che mostra sempre l'ultimo pubblicato. Nessun aggregatore.

## Provare in locale

`bash AVVIO_LINUX.sh` e poi http://127.0.0.1:8000. Test: `python -m pytest`.
Una ricetta singola si importa con
`python importa_ricetta.py "https://ricette.giallozafferano.it/..."`
(resta in revisione finché non supera i controlli).

## Limiti

- I prezzi dei supermercati non sono disponibili: il budget usa il costo
  indicativo della fonte.
- GialloZafferano non pubblica le proteine per le ricette recenti.
- Le preferenze non si sincronizzano tra dispositivi (usa il backup).
