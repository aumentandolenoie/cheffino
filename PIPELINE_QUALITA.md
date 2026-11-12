# Cheffino — pipeline catalogo e immagini

## Quattro workflow

1. `01-raccolta.yml`: acquisizione manuale di nuove ricette, sempre in revisione.
2. `02-arricchimento.yml`: recupero fotografico e audit giornalieri delle ricette
   già pubblicate; completamento degli altri dati solo con l'opzione manuale
   `completa_dati`. Nessuna approvazione automatica aggiuntiva.
3. `03-pubblicazione.yml`: validazione, test e creazione dello snapshot; non
   effettua una seconda estrazione né una seconda certificazione delle foto.
4. `test-qualita.yml`: test e audit locali su PR/push; confronto con fonti reali
   in sola lettura sulle PR e quando eseguito manualmente. Il report è un artifact Actions.

Le scritture operative condividono il gruppo di concorrenza
`cheffino-catalogo-scrittura`. Lo snapshot è prodotto dal solo workflow 03.
Gli script monouso delle riparazioni concluse sono recuperabili nella storia Git;
le foto già recuperate restano nei cataloghi. `ripristina_passaggi_storici.py`
rimane disponibile come migrazione esplicita, con i relativi test, e non viene
eseguito periodicamente.

## Motore immagini

`app/recipe_media.py` legge immagini associate a `HowToStep` e conserva le sezioni
`HowToSection`. Per HTML supportato integra le immagini dei contenitori espliciti
`gz-content-recipe-step`, `wprm-recipe-instruction` o `HowToStep`, solo quando il
loro testo corrisponde ai blocchi della ricetta nello stesso ordine. Non associa
immagini semplicemente perché vicine al testo. `<picture>`, lazy loading e
`srcset` sono normalizzati a un URL per elemento. Le strisce restano intere;
nessuna suddivisione in tre pannelli è presunta dal frontend.

`importa_foto_passaggi.py` è l'unico comando periodico per copertine, gallerie,
confronto e certificazione. Usa un solo HTML per ricetta e una cache delle regole
robots per origine. Il precedente riconoscimento numerato/strip è conservato
come fallback controllato, non come prima scelta. I blog senza dati Recipe o
senza associazione esplicita restano non verificati: non esiste un parser
universale garantito.

L'estrazione annota stato, URL fonte, hash HTML, metodo, data e differenze rispetto
alla galleria esistente. Gli stati sono `complete`, `partial`, `unknown`,
`verified_absent`; gli errori di acquisizione sono `fetch_failed` nel report.
`partial` indica che solo alcuni blocchi hanno immagini, non necessariamente
che la fonte debba averne altre. Il report non sostituisce le regole editoriali.

Una galleria esistente non viene sostituita automaticamente. La versione della
vecchia associazione rimane intatta; `media_extraction_version` identifica il
nuovo controllo. La compatibilità delle strisce precedenti alla V10 è applicata
nell'API (`step_images_display`), mantenendo la precedente posizione visibile.
Il frontend mostra gruppi già pronti senza interpretare i nomi dei file.

L'API aggiorna le fotografie dallo staging soltanto se il procedimento coincide
con quello dello snapshot pubblicato e il numero dei gruppi è coerente.
Ingredienti, approvazioni e testi pubblicati restano autoritativi nello snapshot.

## Assenza verificata

Nessun risultato del parser, errore HTTP, pagina incompleta o formato sconosciuto
può certificare assenza. Il controllo richiede una pagina completa, una ricetta
identificata e blocchi riconosciuti corrispondenti al testo, senza media nei
blocchi, immagini strutturate o segnali delle gallerie originali. Le attestazioni
esistenti restano valide secondo `app/photo_policy.py`. L'audit distingue queste
assenze dalle foto da recuperare.

## Comandi

```bash
# Confronto limitato, nessuna scrittura nei cataloghi
python importa_foto_passaggi.py --published-only --limit 35 --dry-run --report /tmp/confronto-media.json

# Recupero ordinario delle ricette già pubblicate
python importa_foto_passaggi.py --published-only --limit 35 --report /tmp/media.json

# Test e controllo locale
python -m pytest -q
python controlla_integrita_catalogo.py
python diagnostica_foto_api.py
```

Il confronto rispetta versione e intervallo dei tentativi. `--force` insieme a
`--published-only` ritenta immediatamente le sole schede incomplete. I casi
ambigui sono segnalati; la correzione delle associazioni esistenti richiede un
confronto con la fonte, non un semplice cambio della versione.

## Validazione della migrazione

I test coprono immagini strutturate, sezioni con numeri ripetuti, immagini HTML
senza numerazione, picture/srcset, gallerie parziali, collage interi, identità
errata, ordine diverso, fonti non leggibili, assenza certificata e conservazione
delle foto del catalogo pubblicato. I cataloghi non sono modificati dal refactor.
I test sintetici non dimostrano da soli la copertura di ogni template reale:
prima di applicare nuove associazioni va esaminato anche il confronto Actions
con le fonti live. Usare `--recipe-id ID` (ripetibile, solo con `--dry-run`)
per confrontare anche ricette già controllate. Un report vuoto o composto da errori non prova equivalenza.

## Affidabilità v13 (novembre 2026)

- **Un solo parser ingredienti** (`app/ingredienti.py`), usato da importazione,
  riparazione e normalizzazione: entità HTML decodificate (`&frac12;` → `½`),
  unità normalizzate, conteggi senza unità accettati solo se plausibili (< 20)
  e non derivati (succo, scorza, farina...). Nessuna quantità inventata.
- **Un solo costruttore di schede** (`app.catalog.build_record`): le ricette
  importate hanno subito porzioni, tempi, quantità e passaggi puliti, invece di
  restare «da fonte» fino a una riparazione manuale.
- **Parser JSON-LD robusto**: sezioni `HowToSection` con `@type` in lista,
  istruzioni in un'unica stringa, immagini `ImageObject`, JSON con virgole
  finali o caratteri di controllo, alias dei valori nutrizionali.
- **Rete** (`app/rete.py`): charset dalla risposta, nuovi tentativi con attesa
  crescente su 429/5xx/timeout, nessun nuovo tentativo su 403/404 o redirect
  esterni. Gli errori temporanei non lasciano modifiche parziali e, se ripetuti,
  fermano il lotto.
- **Pulizia passaggi v2** (`pulisci_procedimenti.py`): i numeri delle foto sono
  riconosciuti dai nomi file delle immagini del blocco (`_7.jpg`, `strip_7-9`) o
  da catene crescenti con buchi; gestisce `(8.` e `(5-6)`. Dosi, tempi e misure
  restano intatti. La v1 lasciava riferimenti come «l'acqua 12 .» in 49 ricette
  pubblicate.
- **Recupero foto**: con `--published-only` include anche le schede già
  approvate ma non pubblicate, che altrimenti non potevano mai ricevere le foto
  richieste per la pubblicazione.
- `normalizza_catalogo.py`: correzioni offline e idempotenti su catalogo e
  snapshot insieme. `audit_ricette.py`: controllo completo, anche `--online`
  per confrontare le schede con la pagina originale.
- Workflow: il salvataggio dei dati avviene prima del caricamento dei report;
  un errore di quota degli artifact non blocca più il commit.

## Esigenze alimentari

`app/diete.py` valuta ogni ricetta per Vegetariano, Vegano, Senza Glutine e
Senza Lattosio a partire dagli ingredienti della fonte (più un controllo sul
titolo e sul procedimento, per ingredienti citati solo nel testo). Esiti:
`si`, `no`, `incerto` (prodotti la cui composizione dipende dalla marca: brodo
pronto, salumi, cioccolato, pasta sfoglia...). L'API li espone nel campo
`diete`; il piano include solo le ricette `si` per tutte le esigenze scelte.
Scelte prudenti: Parmigiano e Grana contano come latticini; l'avena come
glutine; i formaggi stagionati sono considerati vegetariani.
