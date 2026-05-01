# SPARK Framework Engine — Prospetto Tecnico Integrativo

**Versione:** 1.0.0  
**Stato:** Supporto tecnico al design di refactoring modulare  
**Scopo:** fornire a Copilot un documento ponte tra il design concettuale e il piano implementativo basato sul codice reale.

## 1. Ruolo del documento

Questo documento non sostituisce `REFACTORING-DESIGN.md`.
Lo integra con un livello tecnico preliminare utile a trasformare il design in un piano esecutivo dettagliato.

Il suo scopo è:
- rendere esplicite le osservazioni tecniche emerse durante la validazione del design;
- evidenziare i rischi operativi più probabili durante la Fase 0;
- fissare i vincoli di transizione che Copilot dovrà rispettare nella pianificazione implementativa;
- offrire una pre-mappatura delle aree del monolite da verificare nel codice reale.

## 2. Ambito

Il documento copre solo il refactoring strutturale del motore SPARK.
Non definisce il codice finale né sostituisce il piano implementativo dettagliato.

Sono inclusi:
- vincoli tecnici di estrazione;
- criteri di verifica;
- rischi di dipendenza e circolarità;
- contratti di responsabilità per i moduli più sensibili;
- aspettative sul piano tecnico che Copilot dovrà generare.

Non sono inclusi:
- snippet di implementazione;
- refactor logici di Fase 1;
- modifiche funzionali;
- nuove feature.

## 3. Osservazioni tecniche consolidate

### 3.1 Monolite come problema fisico

Il file principale del motore è sufficientemente grande da rendere fragile la navigazione, la localizzazione del contesto e la verifica delle dipendenze.
Questo aumenta il rischio di duplicazioni involontarie, errori di import e bug da perdita di contesto.

### 3.2 Fase 0 come estrazione, non correzione

Durante la Fase 0 il codice va spostato senza essere migliorato.
Ogni tentativo di correggere, rinominare, ripulire o redistribuire responsabilità nello stesso step rende ambigua la diagnosi di eventuali regressioni.

### 3.3 Re-export hub come strato di compatibilità

La transizione deve essere incrementale.
Il file originario resta temporaneamente uno strato di compatibilità che riesporta ciò che viene già estratto nei nuovi moduli.

### 3.4 Packages come area ad alto rischio

Il dominio `packages/` è il candidato naturale a diventare il nuovo contenitore caotico.
Per questo motivo il suo contratto va controllato in modo attivo: deve orchestrare, non implementare logica di basso livello.

## 4. Contratti tecnici da far rispettare a Copilot

### 4.1 Contratto di `core/`

- Nessuna dipendenza da altri moduli interni.
- Solo modelli dati, costanti e utility pure.
- Nessuna logica di orchestrazione.

### 4.2 Contratto di `merge/`

- Contiene algoritmo, validatori, gestione sezioni e sessioni di merge.
- Non dipende da rete o lifecycle pacchetti.
- Le trasformazioni testuali restano isolate qui.

### 4.3 Contratto di `manifest/`

- Gestisce persistenza di manifest e snapshot.
- Non decide policy di installazione o aggiornamento.
- Non ingloba logica di boot.

### 4.4 Contratto di `registry/`

- Gestisce registry remoto, store locale e indice URI.
- Rappresenta la fonte tecnica delle risorse MCP.
- Non deve assorbire responsabilità di workspace discovery.

### 4.5 Contratto di `workspace/`

- Legge, scopre e descrive.
- Non orchestra installazioni.
- Non diventa un layer di scrittura generalista.

### 4.6 Contratto di `packages/`

- Coordina installazione, update, remove, migrazione e diff ad alto livello.
- Non implementa parsing, hashing, validazioni strutturali o gestione diretta di file di basso livello.
- Se contiene logica troppo dettagliata, quella logica va candidata a migrazione in Fase 1.

### 4.7 Contratto di `boot/`

- Separa costruzione e validazione.
- È l'ultimo layer a nascere.
- Non deve nascondere fallback silenziosi durante la Fase 2.

## 5. Verifiche preliminari che Copilot deve fare sul codice reale

Prima di emettere il piano tecnico, Copilot deve controllare almeno questi punti:

1. Se `FrameworkInventory` o `EngineInventory` dipendono già da classi del dominio `registry/`.
2. Se esistono funzioni di supporto duplicate tra aree diverse del monolite.
3. Se `packages/` contiene già logiche che in realtà appartengono a `manifest/`, `merge/` o `registry/`.
4. Se il file entrypoint contiene costanti e dataclass che possono essere isolate immediatamente in `core/`.
5. Quale tool MCP restituisce l'output più stabile e più rappresentativo da usare come baseline diagnostica.

## 6. Baseline diagnostica

Il piano tecnico deve scegliere un solo tool MCP come riferimento fisso per la Fase 0.
Quel tool deve essere:
- stabile nell'output;
- abbastanza ricco da attraversare più layer del sistema;
- semplice da lanciare sempre nello stesso modo.

Copilot deve documentare:
- nome del tool scelto;
- comando o procedura esatta per lanciarlo;
- formato dell'output atteso;
- modalità di confronto con la baseline pre-refactor.

## 7. Procedura operativa attesa nei documenti tecnici

Per ogni fase, ma soprattutto per la Fase 0, il piano tecnico deve essere diviso in step piccoli e atomicamente verificabili.
Ogni step deve contenere:
- file sorgente coinvolti;
- file destinazione;
- classi/funzioni da estrarre;
- re-export da introdurre temporaneamente;
- verifiche obbligatorie post-step;
- criterio di rollback.

Per la Fase 0, è attesa una scomposizione almeno per dominio: core, merge, manifest, registry, workspace, packages, assets, boot, entrypoint finale.

## 8. Failure mode da anticipare

### 8.1 Import circolari

Sintomo: il sistema non parte dopo uno step apparentemente corretto.
Causa probabile: dipendenza non mappata tra moduli che il design aveva considerato lineari.
Risposta: rollback, aggiornamento del grafo dipendenze, ripetizione dello step.

### 8.2 Re-export incompleto

Sintomo: NameError o ImportError dopo l'estrazione di una classe.
Causa probabile: il file originale ha perso un simbolo prima che il re-export fosse attivato.
Risposta: reinserire compatibilità, poi ripetere l'estrazione.

### 8.3 Modifica logica travestita da pulizia

Sintomo: output del tool diagnostico diverso senza errori evidenti.
Causa probabile: durante lo spostamento è stata cambiata logica, naming operativo o flusso di dati.
Risposta: revert completo dello step, nuova estrazione senza modifiche semantiche.

### 8.4 Packages che assorbe troppo

Sintomo: il file `packages/*` continua a crescere mentre gli altri moduli restano sottili.
Causa probabile: stanno finendo lì responsabilità che non si è deciso dove mettere.
Risposta: annotare per Fase 1, non correggere durante Fase 0.

## 9. Aspettative sugli output di Copilot

A partire da questo documento e da `REFACTORING-DESIGN.md`, Copilot dovrebbe generare almeno:

- un piano tecnico generale della Fase 0;
- un file tecnico per ogni fase successiva;
- una serie di TODO operativi per ogni step della Fase 0 nella cartella `docs/todolist/`;
- eventuali note di dipendenza emerse dall'analisi del codice reale.

## 10. Criterio di successo del prospetto integrativo

Questo documento è utile solo se riduce l'ambiguità tra design e implementazione.
Se Copilot riesce a trasformarlo in piani tecnici più rapidi, più precisi e meno interpretativi, allora il documento ha fatto il suo lavoro.

Se invece introduce ridondanza o ripete il design senza aggiungere vincoli tecnici, allora va asciugato senza pietà. Come sempre: meno teatro, più struttura.
