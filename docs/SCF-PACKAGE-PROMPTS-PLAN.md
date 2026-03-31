# Piano Di Implementazione — Prompt SCF Per Gestione Pacchetti

Data: 30 marzo 2026
**Stato:** ✅ completato
Repo analizzato: `spark-framework-engine`
Ambito: progettazione dei prompt `.github/prompts/*.prompt.md` per il ciclo di vita dei pacchetti SCF

---

## Stato attuale del repo

### Cosa esiste già

Nel repo esiste il motore MCP con questi tool rilevanti per i pacchetti:

- `scf_get_workspace_info`
- `scf_install_package(package_id)`
- `scf_update_packages()`
- `scf_remove_package(package_id)`

Esiste inoltre il supporto backend per:

- fetch del registry pubblico
- fetch del `package-manifest.json` del pacchetto
- installazione reale file-per-file con preservazione dei file utente modificati
- rimozione reale di un pacchetto tramite manifesto locale

### Cosa non esiste ancora

Nel repo attuale non esiste ancora la directory `.github/` del motore, quindi:

- `.github/prompts/` è assente
- non esiste nessun file `.prompt.md`
- nessun comando slash `/scf-*` del motore è ancora disponibile come interfaccia utente

### Gap funzionali nel backend MCP

Per coprire bene tutti gli 8 prompt progettati, oggi mancano alcuni tool lato motore:

- un tool per elencare i pacchetti disponibili nel registry
- un tool per ottenere i dettagli di un singolo pacchetto dal registry
- un tool per elencare i pacchetti installati nel workspace
- un tool per applicare davvero un aggiornamento di pacchetto, non solo rilevarlo

Conclusione: i prompt possono essere progettati subito, ma non tutti avranno backend sufficiente per funzionare bene al 100% senza un successivo blocco di lavoro sul motore.

---

## Struttura da creare

Directory da creare:

- `.github/`
- `.github/prompts/`

File prompt da creare:

- `.github/prompts/scf-list-available.prompt.md`
- `.github/prompts/scf-package-info.prompt.md`
- `.github/prompts/scf-list-installed.prompt.md`
- `.github/prompts/scf-status.prompt.md`
- `.github/prompts/scf-install.prompt.md`
- `.github/prompts/scf-remove.prompt.md`
- `.github/prompts/scf-check-updates.prompt.md`
- `.github/prompts/scf-update.prompt.md`

Convenzione consigliata per tutti i prompt:

- frontmatter SCF con `type: prompt`
- `name` uguale al comando slash senza `/`
- `description` breve e orientata all'utente
- corpo del prompt che istruisce esplicitamente il modello su:
  - tool da usare
  - ordine delle operazioni
  - formato della risposta
  - obbligo di conferma prima di modificare file

---

## Contenuto logico dei file

### 1. `.github/prompts/scf-list-available.prompt.md`

Scopo:

- mostrare tutti i pacchetti disponibili nel registry pubblico
- risposta sola lettura

Contenuto logico:

- dire al modello di interrogare il registry pubblico tramite un tool dedicato
- ordinare i pacchetti per id o nome
- mostrare per ogni pacchetto:
  - id
  - descrizione
  - versione più recente
  - stato (`active` o `deprecated`)
- se il registry non è raggiungibile, riportare errore esplicito

Dipendenza backend:

- richiede un futuro tool tipo `scf_list_available_packages()`

### 2. `.github/prompts/scf-package-info.prompt.md`

Scopo:

- ottenere i dettagli completi di un singolo pacchetto prima dell'installazione

Contenuto logico:

- chiedere il nome/id del pacchetto se manca nel prompt utente
- recuperare dal registry i metadati del pacchetto
- recuperare anche il `package-manifest.json` del pacchetto
- mostrare:
  - id
  - descrizione
  - repo URL
  - versione corrente
  - stato
  - numero totale di file installati
  - elenco sintetico delle categorie contenute (`agents`, `skills`, `instructions`, `prompts`, file root `.github/`)
- se deprecato, evidenziarlo chiaramente

Dipendenza backend:

- richiede un futuro tool tipo `scf_get_package_info(package_id)`
- in alternativa il prompt potrebbe orchestrare due tool separati, ma oggi non esistono

### 3. `.github/prompts/scf-list-installed.prompt.md`

Scopo:

- mostrare cosa è già installato nel workspace attivo

Contenuto logico:

- leggere il manifesto locale delle installazioni tramite un tool dedicato
- raggruppare per pacchetto
- mostrare per ogni pacchetto:
  - nome pacchetto
  - versione installata
  - numero file tracciati
- se non c'è nulla installato, dichiararlo chiaramente

Dipendenza backend:

- richiede un futuro tool tipo `scf_list_installed_packages()`

### 4. `.github/prompts/scf-status.prompt.md`

Scopo:

- fornire una vista complessiva dello stato SCF del workspace

Contenuto logico:

- usare `scf_get_workspace_info()` per il riepilogo del workspace
- usare `scf_update_packages()` per sapere se ci sono update disponibili
- idealmente usare anche un tool di elenco pacchetti installati
- restituire un report compatto con:
  - root del workspace
  - stato inizializzazione
  - framework version
  - conteggi agenti/skill/instructions/prompt
  - pacchetti installati
  - pacchetti con update

Dipendenza backend:

- funziona parzialmente già oggi
- per la sezione “pacchetti installati” serve comunque `scf_list_installed_packages()`

### 5. `.github/prompts/scf-install.prompt.md`

Scopo:

- installare un pacchetto nel workspace in modo guidato e sicuro

Contenuto logico:

- chiedere l'id del pacchetto se non fornito
- recuperare prima il riepilogo del pacchetto da installare
- mostrare sempre una preview con:
  - pacchetto
  - versione
  - numero file previsti
  - eventuali categorie contenute
- chiedere conferma esplicita prima della modifica
- solo dopo conferma invocare `scf_install_package(package_id)`
- al termine mostrare:
  - file installati
  - file preservati perché modificati dall'utente
  - eventuali errori per file

Dipendenza backend:

- può essere implementato quasi subito
- per una preview ricca conviene avere anche `scf_get_package_info(package_id)`

### 6. `.github/prompts/scf-remove.prompt.md`

Scopo:

- rimuovere un pacchetto già installato dal workspace

Contenuto logico:

- chiedere l'id del pacchetto se manca
- mostrare un riepilogo dell'operazione prima di agire
- ricordare esplicitamente che i file modificati dall'utente saranno preservati
- chiedere conferma obbligatoria
- invocare `scf_remove_package(package_id)` solo dopo conferma
- mostrare in uscita:
  - pacchetto rimosso
  - elenco file preservati perché user-modified

Dipendenza backend:

- backend già presente
- manca solo il prompt

### 7. `.github/prompts/scf-check-updates.prompt.md`

Scopo:

- controllare se i pacchetti installati hanno aggiornamenti disponibili

Contenuto logico:

- invocare `scf_update_packages()` in modalità report
- classificare i risultati in tre gruppi:
  - aggiornati
  - da aggiornare
  - non presenti nel registry
- non modificare mai il workspace
- se non c'è nulla installato, dirlo chiaramente

Dipendenza backend:

- backend già presente
- manca solo il prompt

### 8. `.github/prompts/scf-update.prompt.md`

Scopo:

- eseguire il flusso completo di aggiornamento pacchetti con conferma esplicita

Contenuto logico:

- controllare prima gli update disponibili
- mostrare un piano d'azione chiaro con:
  - pacchetto
  - versione installata
  - versione target
  - nota che i file modificati dall'utente saranno preservati
- chiedere conferma obbligatoria
- applicare gli aggiornamenti solo dopo conferma
- mostrare risultato finale con installati/preservati/errori

Dipendenza backend:

- oggi non implementabile davvero end-to-end
- manca un tool di aggiornamento applicativo, per esempio:
  - `scf_upgrade_package(package_id)`
  - oppure estensione di `scf_update_packages()` con modalità apply

---

## Ordine di implementazione consigliato

### Fase 1 — Interfaccia read-only a basso rischio

File target:

- `.github/prompts/scf-check-updates.prompt.md`
- `.github/prompts/scf-status.prompt.md`

Motivo:

- sono i prompt con maggiore copertura backend già disponibile
- permettono test rapidi della UX slash command del motore

Nota:

- `scf-status` sarà inizialmente parziale finché non esiste `scf_list_installed_packages()`

### Fase 2 — Prompt distruttivi con conferma esplicita

File target:

- `.github/prompts/scf-install.prompt.md`
- `.github/prompts/scf-remove.prompt.md`

Motivo:

- il backend per installare e rimuovere ora esiste
- la parte critica è definire bene il linguaggio di conferma e il riepilogo pre-azione

### Fase 3 — Prompt read-only che richiedono nuovi tool lato motore

File target:

- `.github/prompts/scf-list-available.prompt.md`
- `.github/prompts/scf-package-info.prompt.md`
- `.github/prompts/scf-list-installed.prompt.md`

Prerequisiti consigliati:

- `scf_list_available_packages()`
- `scf_get_package_info(package_id)`
- `scf_list_installed_packages()`

Motivo:

- senza questi tool i prompt avrebbero UX debole o costringerebbero il modello a inferenze non affidabili

### Fase 4 — Prompt di aggiornamento completo

File target:

- `.github/prompts/scf-update.prompt.md`

Prerequisito consigliato:

- nuovo tool di apply update, non solo di check

Motivo:

- è il comando più delicato del ciclo di vita
- dipende da installazione, rimozione e rilevamento update già stabilizzati

---

## Ordine pratico dei file da creare

Se si vuole procedere in sicurezza e ottenere valore subito, l'ordine pratico consigliato è:

1. `.github/prompts/scf-check-updates.prompt.md`
2. `.github/prompts/scf-status.prompt.md`
3. `.github/prompts/scf-install.prompt.md`
4. `.github/prompts/scf-remove.prompt.md`
5. estendere il motore con i tool mancanti read-only
6. `.github/prompts/scf-list-available.prompt.md`
7. `.github/prompts/scf-package-info.prompt.md`
8. `.github/prompts/scf-list-installed.prompt.md`
9. estendere il motore con il tool di update applicativo
10. `.github/prompts/scf-update.prompt.md`

---

## Raccomandazioni di implementazione

- Tutti i prompt che modificano il workspace devono imporre conferma esplicita con risposta sì/no chiara.
- I prompt non devono chiedere all'utente di ricordare nomi tool MCP.
- I prompt devono produrre sempre output orientato all'azione: riepilogo, conferma, esito.
- I prompt di installazione, rimozione e update devono riportare sempre i file preservati perché user-modified.
- Prima di creare i prompt conviene decidere se i gap backend mancanti verranno chiusi prima o dopo la prima tranche di prompt.

---

## Esito dell'analisi

Nel repo `spark-framework-engine` non esiste ancora nessuna infrastruttura prompt lato motore. La progettazione degli 8 comandi è coerente e utile, ma per coprire l'intero ciclo di vita in modo robusto servono ancora alcuni tool MCP read-only e un tool di update applicativo. I prompt che si possono implementare subito con maggiore sicurezza sono `scf-check-updates`, `scf-status` (parziale), `scf-install` e `scf-remove`.