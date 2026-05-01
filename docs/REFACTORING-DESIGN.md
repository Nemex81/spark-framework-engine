# SPARK Framework Engine — Documento di Design: Refactoring Modulare

**Versione:** 1.1.0
**Autore:** Luca "Nemex" — SPARK Project
**Stato:** Validato dal Consiglio AI (GPT, Gemini, Claude)
**Data:** 01 Maggio 2026

---

## 1. Contesto e motivazione

Il motore SPARK (`spark-framework-engine.py`) è nato come script autonomo e nel tempo ha accumulato responsabilità crescenti senza una separazione fisica dei confini. Il risultato attuale è un singolo file di circa 361 KB che ospita al suo interno logica di data modeling, algoritmi di merge, gestione filesystem, comunicazione di rete, orchestrazione di pacchetti e boot sequence.

Questo stato non è un problema architetturale astratto: è un problema concreto e misurabile. Un file di quella dimensione non è navigabile con screen reader in modo efficace. I confini tra le classi sfumano perché non sono rinforzati da nessuna struttura fisica. I bug del tipo "metodo duplicato" o "logica replicata" nascono spontaneamente perché nessuno può tenere in testa l'intero file. La manutenzione di qualsiasi feature richiede una ricerca globale invece di una navigazione per responsabilità.

L'obiettivo di questo refactoring è trasformare il monolite in un sistema modulare dove ogni responsabilità ha un confine fisico preciso, senza alterare nessuna logica esistente durante la fase di ristrutturazione.

---

## 2. Principi guida del refactoring

**Separazione fisica come contratto.** Una responsabilità esiste come entità indipendente solo quando ha un modulo dedicato. Finché due responsabilità condividono lo stesso file, il loro confine è una convenzione, non un fatto.

**Nessuna modifica logica durante la ristrutturazione.** Le fasi di estrazione del codice e le fasi di correzione della logica sono operazioni separate e non si sovrappongono. Durante la Fase 0, il codice viene spostato esattamente come è, senza ottimizzazioni, correzioni o miglioramenti. Questa regola vale anche per la ri-assegnazione di responsabilità: se durante lo spostamento si individua codice che "appartiene" a un modulo diverso da quello attuale, lo si annota e lo si lascia dove si trova. Fase 0 = copia esatta. Fase 1 = pulizia.

**Transizione senza interruzione.** Il sistema deve continuare a funzionare correttamente dopo ogni singolo step di ristrutturazione. Non esiste uno stato intermedio in cui il motore è rotto. La tecnica del re-export hub garantisce questa continuità.

**Ordine determinato dalle dipendenze.** L'ordine di estrazione dei moduli non è arbitrario: è imposto dalla struttura delle dipendenze tra le classi. I moduli senza dipendenze interne vengono estratti per primi. I moduli che dipendono da altri vengono estratti solo dopo che i loro prerequisiti sono già stati isolati.

**Accessibilità come criterio tecnico.** La navigabilità con screen reader non è un requisito opzionale: è un vincolo di qualità alla pari della correttezza funzionale. Un file grande ha lo stesso status di un file con bug: è un problema da risolvere. Il refactoring è anche una fix ergonomica: in un file da 200 righe la ricerca di una funzione è istantanea, in un file da 10.000 righe è una battaglia che genera perdita di contesto e introduce errori.

**I layer alti orchestrano, i layer bassi implementano.** Un layer che dipende da tutti gli altri è il candidato naturale a diventare il nuovo monolite se non viene tenuto stretto al suo ruolo di coordinatore. La logica di basso livello (parsing, calcolo hash, validazione strutturale) appartiene ai layer bassi. I layer alti chiamano quella logica, non la reimplementano.

---

## 3. Mappa delle responsabilità

Il sistema SPARK Engine svolge le seguenti responsabilità distinte. Ognuna di esse diventa un modulo fisico separato nel sistema modulare.

### 3.1 Fondamenta (core)

Questa è la base dell'intero sistema. Contiene le strutture dati pure che descrivono le entità del dominio, le costanti globali che definiscono il comportamento del sistema, e le funzioni di utilità generali che non dipendono da nessuna altra parte del sistema.

Nulla in questo livello può importare da nessun altro modulo interno. Se qualcosa in `core` inizia a dipendere da qualcos'altro, il contratto del sistema è violato. Questo livello è il DNA: immutabile nelle sue dipendenze, stabile nella sua interfaccia.

Le entità principali che appartengono a questo livello sono: le strutture dati che descrivono il workspace, i file del framework, i risultati del merge e i conflitti di merge. Le costanti che definiscono la versione dell'engine, i nomi delle sottodirectory di runtime, i nomi dei file speciali. Le funzioni che calcolano hash, gestiscono timestamp, normalizzano path e confrontano versioni semantiche.

### 3.2 Algoritmo di merge (merge)

Questo livello contiene l'algoritmo di merge a tre vie e tutto il codice associato alla gestione dei conflitti, alla validazione del risultato del merge, alla manipolazione delle sezioni SCF nei file markdown e alla gestione delle sessioni di merge persistite.

L'algoritmo di merge è progettato senza dipendenze da MCP, da rete o da filesystem. È un pezzo di logica pura che trasforma testo in testo. I validatori post-merge verificano la correttezza strutturale del risultato. Il gestore delle sezioni SCF si occupa dei marker `<!-- SCF:BEGIN -->` e `<!-- SCF:END -->`. Il gestore delle sessioni persiste lo stato delle operazioni di merge in corso.

Questo livello dipende solo da `core`. Può essere sviluppato, testato e ragionato in completo isolamento dal resto del sistema.

### 3.3 Manifest e snapshot (manifest)

Questo livello gestisce la persistenza dello stato dei pacchetti installati. Il manifest manager legge e scrive il file `.scf-manifest.json`, tiene traccia degli hash SHA-256 dei file installati, rileva modifiche manuali ai file protetti e gestisce i record di override. Il gestore degli snapshot crea e legge le copie dello stato dei file in un momento preciso nel tempo.

Questo livello dipende da `core` e utilizza alcune funzioni del livello `merge` per le operazioni di strip sulle sezioni. Non ha dipendenze da rete.

### 3.4 Registro e store (registry)

Questo livello è il cuore della gestione dei pacchetti. Contiene il client per il registro remoto dei pacchetti, che si occupa di scaricare e mantenere in cache il `registry.json` dal repository `scf-registry` su GitHub. Contiene lo store centralizzato dei pacchetti, che gestisce il filesystem fisico dove i pacchetti vengono archiviati nella directory dell'engine. Contiene il registro MCP delle risorse, che è l'indice in memoria che mappa gli URI (`agents://`, `skills://`, `instructions://`, `prompts://`) ai path fisici corrispondenti.

Questo livello dipende da `core` e `manifest`. È il confine tra la logica locale e il mondo esterno.

### 3.5 Workspace (workspace)

Questo livello si occupa di capire dove si trova il workspace attivo e di descriverne il contenuto. Il localizzatore risolve il path del workspace usando variabili d'ambiente, marker di file e configurazioni VS Code. L'inventory scopre i file SCF presenti sotto `.github/` e li cataloga. Il gestore delle preferenze legge e scrive la politica di aggiornamento dell'utente.

Questo livello legge e descrive. Non decide, non orchestra. Se inizia a contenere logica decisionale, il confine è stato violato. Dipende da `core`, `manifest` e `registry`.

### 3.6 Ciclo di vita dei pacchetti (packages)

Questo livello gestisce tutte le operazioni sui pacchetti: installazione, aggiornamento, rimozione. Contiene la logica del ciclo di vita per i pacchetti v3 (store-based), la logica di migrazione dai pacchetti v2 ai pacchetti v3, e le funzioni di diff che confrontano lo stato del workspace con lo stato atteso.

Questo livello orchestra i layer sottostanti. È il layer più complesso del sistema e dipende da tutti i layer precedenti.

**Contratto esplicito di `packages/`.** Questo modulo deve esclusivamente orchestrare: chiama il registro per ottenere dati, chiama il merge engine per operare sul testo, chiama il manifest per registrare il risultato. Non deve mai contenere logica di parsing, calcolo di hash, validazioni strutturali o manipolazione diretta del filesystem. Se durante la Fase 0 si trova logica di questo tipo dentro le classi di `packages/`, la si sposta fisicamente dove si trova ora e la si annota per la Fase 1, dove verrà riassegnata al layer corretto. Un `packages/` che implementa invece di orchestrare è un monolite più piccolo, non una soluzione.

### 3.7 Renderer degli asset (assets)

Questo livello contiene le funzioni che generano i file che il sistema produce nel workspace: `AGENTS.md`, `AGENTS-plugin.md`, `.clinerules`, `project-profile.md`. Sono funzioni prevalentemente di trasformazione dati che producono contenuto testuale a partire dalle informazioni sui pacchetti installati.

Dipende da `workspace` e `registry`. Non ha stato proprio.

### 3.8 Boot e validazione (boot)

Questo livello è l'orchestratore dell'avvio. Contiene due responsabilità separate: la sequenza di costruzione del sistema (che inizializza tutti i layer nell'ordine corretto) e la validazione dello stato costruito (che verifica che ogni componente sia in uno stato valido prima che il server inizi ad accettare richieste).

La separazione tra costruzione e validazione è intenzionale: i failure mode sono diversi. Un errore in costruzione significa che il sistema non può essere assemblato. Un errore in validazione significa che il sistema è stato assemblato ma si trova in uno stato inconsistente. Questi due casi richiedono risposte diverse.

Questo livello dipende da tutti gli altri. È l'ultimo ad essere costruito nella sequenza di estrazione.

---

## 4. Struttura fisica del sistema modulare

```
spark-framework-engine/
│
├── spark-framework-engine.py       ← entry point (~80 righe a refactoring completato)
│
└── spark/
    ├── core/
    │   ├── models.py
    │   ├── constants.py
    │   └── utils.py
    │
    ├── merge/
    │   ├── engine.py
    │   ├── validators.py
    │   ├── sections.py
    │   └── sessions.py
    │
    ├── manifest/
    │   ├── manifest.py         ← nome effettivo (piano: manager.py)
    │   ├── diff.py
    │   └── snapshots.py
    │
    ├── registry/
    │   ├── client.py
    │   ├── store.py
    │   ├── mcp.py              ← nome effettivo (piano: mcp_registry.py)
    │   └── v3_store.py
    │
    ├── inventory/              ← package estratto da workspace/ in Fase 0
    │   ├── framework.py        ← FrameworkInventory
    │   └── engine.py           ← EngineInventory
    │
    ├── workspace/
    │   ├── locator.py
    │   ├── migration.py        ← MigrationPlan/MigrationPlanner (piano: packages/)
    │   └── policy.py           ← nome effettivo (piano: update_policy.py; Step 1.1)
    │
    ├── packages/
    │   ├── lifecycle.py
    │   └── registry_summary.py ← aggiunto in Fase 0
    │
    ├── assets/                 ← 4 file (piano: 1 file renderers.py)
    │   ├── collectors.py
    │   ├── phase6.py
    │   ├── rendering.py
    │   └── templates.py
    │
    └── boot/
        ├── engine.py           ← SparkFrameworkEngine (piano: in sequence.py)
        ├── sequence.py         ← _build_app
        └── [validation.py]     ← da creare in Fase 2
```

---

## 5. Strategia di transizione: il re-export hub

La transizione dal monolite al sistema modulare avviene usando una tecnica che garantisce continuità operativa in ogni momento: il re-export hub.

Il file `spark-framework-engine.py` non viene svuotato e riscritto in un colpo solo. Viene trasformato progressivamente: man mano che le classi vengono estratte nei nuovi moduli, il file originale aggiunge delle righe di re-export che re-importano le stesse classi dai nuovi moduli. Per tutto il codice che non è ancora stato spostato, il file originale continua a contenerlo.

In questo modo, dopo ogni singolo step di estrazione, il file originale è ancora un programma valido e funzionante. Nessun chiamante esterno si accorge che internamente la struttura sta cambiando.

L'eliminazione del re-export hub avviene solo all'ultimo step, quando tutto il codice è già stato estratto e il file originale non contiene più nulla al di fuori delle righe di re-export e del codice di bootstrap.

**Attenzione operativa:** se anche una sola classe viene rimossa dal file originale senza essere immediatamente aggiunta al re-export, il sistema si rompe con un errore di import. La regola è: prima si aggiunge il re-export, poi si rimuove il codice originale. Mai nell'ordine inverso.

---

## 6. Grafo delle dipendenze tra i moduli

```
core
 └─► merge
      └─► manifest
           └─► registry
                ├─► workspace
                ├─► inventory
                └─► packages
                      └─► assets
                           └─► boot
```

Questa direzione è unidirezionale e non ha cicli. Ogni modulo può importare solo da moduli che si trovano sopra di lui nel grafo. Un modulo non può mai importare da un modulo che si trova sotto di lui.

**Aggiornamento post-Fase 0 (2026-05-01):** la dipendenza `merge → manifest` è stata
confermata durante l'esecuzione di Fase 0 (Step 03): `ManifestManager` usa
`_strip_package_section` di `spark.merge.sections`. Il package `spark/inventory/`
(con `FrameworkInventory` ed `EngineInventory`) è stato estratto come package
autónomo invece di `workspace/inventory.py` come previsto nel piano originale;
entrambe le classi usano `McpResourceRegistry` e `PackageResourceStore`, pertanto
`registry/` è un prerequisito di `inventory/`. Il package `assets/` dipende sia
da `registry/` (via `PackageResourceStore`) che da `inventory/` (via `EngineInventory`).

---

## 6-bis. Tool diagnostico fisso (ancora di riferimento)

Prima di iniziare qualsiasi step della Fase 0, viene scelto e fissato un tool MCP specifico come strumento di verifica. Il suo output viene catturato e salvato come baseline di riferimento. Ogni verifica successiva confronta l'output del tool con quella baseline: se cambia anche di una sola riga, lo step corrente ha introdotto una modifica involontaria alla logica e va revertito.

La scelta del tool è una decisione da prendere una volta sola, prima di iniziare, e non viene cambiata per tutta la durata della Fase 0. Un tool adatto è uno che restituisce un payload strutturato e stabile, come `scf_get_status` o `scf_list_packages`. Il criterio di scelta: deve coprire il maggior numero possibile di layer del sistema con una singola chiamata.

Copilot, nella produzione del piano tecnico implementativo, fisserà il tool specifico basandosi sull'analisi del codice reale e documenterà il comando esatto per lanciarlo e il formato atteso dell'output di riferimento.

---

## 7. Fasi del piano di refactoring

### Fase 0 — Modularizzazione (nessuna modifica logica)

**Obiettivo:** trasformare il monolite in un sistema modulare senza alterare nessun comportamento.

**Descrizione:** ogni classe e ogni funzione viene spostata nel modulo corrispondente seguendo il grafo delle dipendenze. Il file originale diventa progressivamente un re-export hub. Al termine di questa fase, il file entry point contiene solo import e il codice di bootstrap FastMCP.

**Criterio di completamento:** il motore si avvia, risponde ai tool MCP base e produce output identico a prima dello spostamento.

**Vincolo assoluto:** nessuna logica viene modificata, corretta o migliorata durante questa fase. Nessuna responsabilità viene riassegnata a un modulo diverso da quello attuale. Se viene individuato un bug o un codice fuori posto, viene annotato con un commento nel codice e trattato nella fase successiva.

---

### Fase 1 — Stabilizzazione (correzione dei bug esistenti)

**Obiettivo:** eliminare i bug e le duplicazioni identificati nel codice ora che è leggibile per modulo.

**Descrizione:** con il codice suddiviso per responsabilità, i bug diventano localizzabili. I problemi noti (come il metodo duplicato P1) vengono corretti. Le logiche replicate in più punti vengono consolidate nella loro sede naturale. Le responsabilità mal assegnate durante la Fase 0 vengono spostate nel modulo corretto. Nessuna nuova feature viene introdotta.

**Criterio di completamento:** tutti i bug noti sono corretti e il comportamento del sistema è documentato e verificato per ogni modulo.

---

### Fase 2 — Boot deterministico

**Obiettivo:** rendere la sequenza di avvio del motore completamente deterministica e con comportamento esplicito su ogni possibile failure.

**Descrizione:** `boot/sequence.py` viene riscritto come sequenza lineare e ordinata di inizializzazioni. `boot/validation.py` verifica che ogni componente sia in stato valido dopo la costruzione. Il sistema non entra mai in modalità degradata silenziosa: se un componente non può essere inizializzato correttamente, il motore si ferma con un messaggio diagnostico preciso su stderr.

**Criterio di completamento:** è possibile leggere `boot/sequence.py` e capire esattamente in quale ordine si costruisce il sistema e quale componente può causare quale tipo di errore.

---

### Fase 3 — Separazione runtime

**Obiettivo:** separare nettamente la configurazione statica dallo stato dinamico di runtime.

**Descrizione:** tutti i file di stato temporaneo (snapshot, sessioni di merge, backup, log di runtime) vengono spostati in una directory dedicata fuori dal workspace dell'utente. La configurazione del sistema viene separata dallo stato che cambia durante l'esecuzione. I path di runtime diventano configurabili tramite una costante in `core/constants.py`.

**Criterio di completamento:** il workspace dell'utente non contiene file generati dal motore che non appartengano al framework SCF. La directory di runtime del motore è separata dal workspace.

---

### Fase 4 — Gateway e workspace minimale

**Obiettivo:** rendere il layer workspace un lettore puro e introdurre un gateway esplicito per tutte le operazioni che modificano il filesystem.

**Descrizione:** `workspace/` viene reso un layer di sola lettura. Tutte le operazioni di scrittura sul filesystem passano attraverso un gateway centralizzato che garantisce che ogni modifica sia tracciata dal `ManifestManager`. Il layer workspace descrive quello che trova, non decide quello che deve succedere.

**Criterio di completamento:** nessuna scrittura sul filesystem avviene al di fuori del gateway. Il layer workspace non contiene chiamate a operazioni di modifica.

---

## 8. Invarianti di verifica per ogni step della Fase 0

Dopo ogni singolo step di estrazione, prima di procedere al successivo, devono essere verificate le seguenti tre condizioni:

Prima condizione: il motore si avvia senza errori non gestiti. Gli unici messaggi su stderr sono quelli di logging attesi (INFO e DEBUG). Nessuna eccezione non catturata.

Seconda condizione: il server MCP risponde correttamente alle chiamate. Il wiring FastMCP è intatto e i tool registrati sono raggiungibili.

Terza condizione: l'output del tool diagnostico fisso (definito nella Sezione 6-bis) è identico alla baseline catturata prima di iniziare la Fase 0. Se l'output cambia, c'è stata una modifica involontaria alla logica durante lo spostamento.

Se una di queste tre condizioni non è soddisfatta, il problema è nello step corrente e solo in quello. Si applica la procedura di rollback descritta nella Sezione 9.

---

## 9. Regole operative e procedura di rollback

**Regole di commit:** ogni step della Fase 0 corrisponde a un commit separato. Il messaggio di commit segue questo schema:

`refactor(modulo): estrai NomeClasse e funzioni_associate — nessuna modifica logica`

Nessun commit mescola spostamento di codice e modifica di logica. Sono operazioni separate anche quando avvengono nella stessa sessione di lavoro.

**Procedura di rollback quando un invariante fallisce:**

1. Eseguire `git stash` o `git checkout -- .` per riportare il repository allo stato pre-step.
2. Verificare che il sistema torni allo stato funzionante eseguendo nuovamente i tre invarianti.
3. Analizzare la dipendenza nascosta o l'errore emerso leggendo il messaggio di eccezione o il diff di output.
4. Aggiornare il grafo delle dipendenze nella Sezione 6 se la dipendenza scoperta non era mappata.
5. Ripetere lo step con la dipendenza corretta inclusa nell'ordine di estrazione.

La procedura di rollback non è un'ammissione di fallimento: è la risposta corretta a informazioni nuove sul codice. Il suo scopo è localizzare il problema allo step corrente invece di lasciarlo propagare agli step successivi dove sarebbe molto più difficile da diagnosticare.

---

## 10. Documento prodotto da Copilot per ogni fase

Per ogni fase del piano, Copilot produrrà un documento tecnico di pianificazione basato sul codice reale del repository. Questi documenti verranno salvati nella cartella `docs/` del repository `spark-framework-engine`.

Il documento tecnico di ogni fase conterrà:

- l'elenco preciso dei file da creare o modificare
- le classi e le funzioni da spostare con i loro path di origine e destinazione
- le righe di re-export da aggiungere al file originale dopo ogni step
- i criteri di verifica specifici per quella fase basati sul codice reale
- il tool diagnostico fisso con il comando esatto per lanciarlo (solo per la Fase 0)

Per la Fase 0, il documento verrà ulteriormente suddiviso in un file TODO per ogni step di estrazione, salvati in `docs/todolist/`. Ogni file TODO conterrà le azioni atomiche necessarie per completare quel singolo step e i tre invarianti di verifica.

---

## 11. Rischi identificati e mitigazioni

**Rischio: import circolare tra `workspace/inventory.py` e `registry/`.**
Mitigazione: analisi esplicita delle dipendenze di `FrameworkInventory` ed `EngineInventory` prima di iniziare la Fase 0. Se la dipendenza esiste, `registry/` viene estratto prima di `workspace/` e l'ordine degli step viene aggiornato di conseguenza.

**Rischio: re-export hub incompleto che lascia chiamanti senza import validi.**
Mitigazione: ogni step di estrazione aggiorna immediatamente il re-export hub prima di verificare gli invarianti. Non si verifica mai lo stato in cui una classe è stata rimossa dal file originale senza essere riesportata. La regola è inderogabile: prima si aggiunge il re-export, poi si rimuove il codice originale.

**Rischio: modifica involontaria di logica durante lo spostamento (trappola del genio).**
Mitigazione: terzo invariante di verifica (output identico alla baseline). Questo è il pattern più insidioso: il codice viene "migliorato" mentre viene spostato, convinti che sia una piccola cosa. Non lo è. Se l'output cambia, il commit viene revertito e il codice viene spostato di nuovo senza modifiche. Nessuna eccezione.

**Rischio: ri-assegnazione di responsabilità durante la Fase 0.**
Mitigazione: se durante lo spostamento si individua codice che appartiene a un modulo diverso da quello attuale, lo si annota con un commento `# FASE1-RIASSEGNA: questa logica appartiene a registry/store.py` e lo si lascia dove si trova. La ri-assegnazione avviene in Fase 1, non in Fase 0. Mescolare le due operazioni rende impossibile isolare la causa di eventuali regressioni.

**Rischio: `packages/` diventa il nuovo monolite.**
Mitigazione: il contratto di `packages/` (Sezione 3.6) è esplicito e vincolante. Durante la review di ogni step che tocca `packages/`, verificare che nessuna funzione di basso livello (parsing, hash, validazione strutturale) sia stata introdotta. Se lo è, appartiene a un layer sottostante e va spostata lì.

**Rischio: dipendenze nascoste tra moduli che non emergono dall'analisi statica.**
Mitigazione: la tecnica del re-export hub garantisce che le dipendenze nascoste emergano come errori di import al momento dell'esecuzione, non come comportamenti silenziosi. Ogni errore è localizzato allo step corrente. Si applica la procedura di rollback e si aggiorna il grafo delle dipendenze.

**Rischio: stanchezza operativa durante la Fase 0.**
Mitigazione: la Fase 0 sarà più lenta del previsto perché gli import rompono le scatole e le dipendenze nascoste emergono durante l'esecuzione. È normale. La struttura in micro-step con commit separati permette di fermarsi in qualsiasi momento e riprendere da un punto stabile. Non accelerare.
