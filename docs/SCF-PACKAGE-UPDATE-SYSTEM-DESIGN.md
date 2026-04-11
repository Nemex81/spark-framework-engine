# SCF Package Update System Design

## Scopo

Definire il sistema framework-level per verifica, notifica e aggiornamento dei pacchetti SCF installati nei progetti utente, riusando i tool MCP gia esistenti del motore.

Vincoli di progetto:
- Nessun nuovo schema manifesto: il formato canonico resta `.github/.scf-manifest.json` con `schema_version: "1.0"` e `entries[]`.
- Nessun nuovo tool MCP in questa fase di design.
- Nessuna modifica al routing agenti oltre a quelle strettamente necessarie per il flusso update.
- Il problema del manifesto attuale in `tabboz-simulator-202` e di migrazione da schema legacy scritto a mano, non di assenza funzionale nel motore.

---

## Stato attuale

Il motore `spark-framework-engine` espone gia i componenti MCP necessari:
- `scf_update_packages()` per costruire la preview degli aggiornamenti disponibili.
- `scf_apply_updates(package_id | None)` per applicare gli update in ordine dependency-aware.
- `scf_list_installed_packages()` per leggere i pacchetti installati dal manifesto locale.
- `scf_get_package_info(package_id)` per dettaglio package e manifest remoto.
- `RegistryClient.fetch()` interno per leggere `registry.json` da GitHub raw.
- `ManifestManager` per gestire `.github/.scf-manifest.json` nel formato canonico `entries[]`.

Manca il livello framework user-facing:
- notifica one-shot a inizio sessione;
- slash command `/package-update`;
- migrazione del manifesto legacy `installed_packages[]` al formato canonico `entries[]`.

---

## Decisioni architetturali

### D1. Manifesto locale canonico

Il file canonico resta:
- percorso: `.github/.scf-manifest.json`
- schema: `schema_version: "1.0"`
- struttura: `entries[]`

Non viene introdotto `scf-installed.json`.

### D2. Migrazione del manifesto legacy

Se un progetto contiene un file `.github/.scf-manifest.json` con struttura legacy:
- top-level `installed_packages[]`
- opzionale `untracked_files[]`
- assenza di `entries[]`

il sistema deve eseguire una migrazione one-shot verso il formato canonico del motore.

La migrazione e logica framework, non del motore MCP.

### D3. Punto di aggancio della notifica sessione

La notifica one-shot vive in `Agent-Orchestrator`.

Motivazione:
- e l'agente che gia legge e aggiorna `orchestrator-state.json`;
- possiede gia il concetto di sessione, confidence e checkpoint;
- puo marcare lo stato `update_check_done` senza introdurre nuovi meccanismi paralleli.

`Agent-Welcome` resta focalizzato su setup e manutenzione del project profile, non sul lifecycle continuo dei pacchetti.

### D4. Nessun nuovo tool MCP

La fase update deve riusare solo tool esistenti:
- check update: `scf_update_packages()`
- apply update: `scf_apply_updates(package_id | None)`
- supporto dettaglio: `scf_list_installed_packages()`, `scf_get_package_info(package_id)`

Non servono in questa fase:
- `scf_fetch_url(url)`
- `scf_copy_package_files(package_id, target_path)`
- `scf_check_updates()`

La funzione di check e gia coperta semanticamente da `scf_update_packages()`.

---

## Architettura logica

```text
+---------------------------+
| User session starts       |
+-------------+-------------+
              |
              v
+---------------------------+
| Agent-Orchestrator        |
| check update_check_done   |
| in orchestrator-state     |
+-------------+-------------+
              |
              | no / false
              v
+---------------------------+
| Read local manifest       |
| .github/.scf-manifest.json|
+-------------+-------------+
              |
              | legacy schema?
      +-------+--------+
      |                |
     yes              no
      |                |
      v                v
+----------------+   +----------------------+
| migrate to     |   | call scf_update_     |
| entries[]      |   | packages()           |
+--------+-------+   +----------+-----------+
         |                      |
         +----------+-----------+
                    v
+-------------------------------------------+
| updates available?                         |
+-------------------+-----------------------+
                    | yes
                    v
+-------------------------------------------+
| Show one-shot banner                       |
| /package-update                            |
| /package-update --skip                     |
+-------------------+-----------------------+
                    |
                    v
+-------------------------------------------+
| mark update_check_done = true              |
| in .github/runtime/orchestrator-state.json |
+-------------------------------------------+


/package-update
      |
      v
+-------------------------------------------+
| Agent-Helper coordinates                   |
| 1. read manifest                           |
| 2. call scf_update_packages()              |
| 3. show delta table                        |
| 4. ask confirmation                        |
| 5. call scf_apply_updates()                |
| 6. delegate commit to Agent-Git            |
+-------------------------------------------+
```

---

## Specifica del manifesto locale

### Formato canonico

```json
{
  "schema_version": "1.0",
  "entries": [
    {
      "file": ".github/agents/Agent-Orchestrator.md",
      "package": "scf-master-codecrafter",
      "package_version": "1.0.0",
      "installed_at": "2026-04-11T00:00:00Z",
      "sha256": "<sha256>"
    }
  ]
}
```

### Regole

- Ogni file installato da un pacchetto produce una entry separata.
- `package_version` e la fonte di verita per il confronto locale vs registry.
- `sha256` serve per preservare file modificati dall'utente durante update/remove.
- `installed_at` e per entry, non per pacchetto aggregato.
- Il manifesto non conserva stato di sessione o stato notifica update.

### Migrazione da schema legacy

Input legacy tipico:
- `schema_version: "1.0"`
- `installed_packages[]`
- ogni package con `id`, `version`, `installed_at`, `files[]`

Output canonico:
- stesso file `.github/.scf-manifest.json`
- sostituzione completa del payload con `entries[]`

Algoritmo di migrazione:
1. Leggere il file legacy.
2. Per ogni package in `installed_packages[]`:
   - `package` = `id`
   - `package_version` = `version`
   - `installed_at` = valore del package, se presente
3. Per ogni file elencato in `files[]`:
   - verificare se il file esiste sul disco
   - se esiste, calcolare `sha256`
   - creare una entry per file
4. Scartare `untracked_files[]` dal nuovo manifesto canonico.
5. Scrivere il nuovo manifesto solo se la migrazione termina senza errori fatali.

Gestione edge case:
- file elencato ma mancante su disco: non creare la entry, aggiungere warning runtime al report update;
- package senza `version`: bloccare la migrazione e chiedere intervento manuale;
- file duplicato in piu package: bloccare la migrazione come conflitto di ownership.

---

## Specifica notifica sessione

### Agente responsabile

`Agent-Orchestrator`

### Trigger

Primo ingresso nel loop della sessione, prima di qualsiasi altra operazione delegata.

### Gate di esecuzione

Il controllo parte solo se in `orchestrator-state.json`:
- `update_check_done` e assente, oppure
- `update_check_done` e `false`

### Algoritmo

1. Leggi `.github/.scf-manifest.json`.
2. Se il file non esiste: nessun banner, imposta `update_check_done: true`, continua.
3. Se il file e legacy: migra a `entries[]` prima del check update.
4. Chiama `scf_update_packages()`.
5. Se il report non contiene update: nessun banner.
6. Se esiste almeno un update disponibile: mostra banner una sola volta.
7. Aggiorna `orchestrator-state.json` con:
   - `update_check_done: true`
   - opzionale `available_package_updates: <count>`
   - opzionale `last_update_check: <ISO8601>`

### Banner

```text
┌─────────────────────────────────────────────────────┐
│ AGGIORNAMENTO DISPONIBILE                          │
│ Il pacchetto [nome] ha una nuova versione:         │
│   installata: X.Y.Z -> disponibile: A.B.C          │
│                                                     │
│ Digita /package-update per aggiornare ora.         │
│ Digita /package-update --skip per ignorare.        │
└─────────────────────────────────────────────────────┘
```

### Silenziamento

Comandi supportati:
- `/package-update`
- `/package-update --skip`

Effetto di `--skip`:
- nessun update eseguito;
- il banner non viene riproposto nella stessa sessione;
- `update_check_done` resta `true`.

---

## Specifica prompt `/package-update`

### File

`.github/prompts/package-update.prompt.md`

### Ruolo

Prompt coordinato da `Agent-Helper`.

### Motivazione

`Agent-Helper` e l'agente piu adatto a:
- spiegare lo stato del framework;
- coordinare tool informativi e di update;
- delegare il commit ad `Agent-Git` senza mischiare responsabilita implementative.

### Sequenza tool

1. Leggi `.github/.scf-manifest.json`.
2. Se manifesto assente: rispondi `Nessun pacchetto SCF installato.`
3. Se manifesto legacy: esegui migrazione al formato canonico `entries[]`.
4. Chiama `scf_update_packages()`.
5. Se `updates[]` e vuoto: rispondi `Tutti i pacchetti sono aggiornati.`
6. Se `updates[]` non e vuoto:
   - mostra tabella delta
   - chiedi conferma: `Vuoi aggiornare tutti i pacchetti elencati? (si/no/seleziona)`
7. Se conferma positiva totale:
   - chiama `scf_apply_updates()`
8. Se conferma selettiva:
   - per ciascun package scelto chiama `scf_apply_updates(package_id)`
9. Al termine delega commit ad `Agent-Git`.
10. Mostra report finale con:
   - pacchetti aggiornati
   - file toccati
   - file preservati per modifica utente
   - SHA commit

### Tabella di preview

```text
| Pacchetto | Installata | Disponibile | Stato |
|-----------|------------|-------------|-------|
| scf-master-codecrafter | 1.0.0 | 1.1.0 | update disponibile |
| scf-pycode-crafter     | 2.0.0 | 2.0.0 | aggiornato |
```

### Messaggi di esito

Caso nessun update:
- `Tutti i pacchetti sono aggiornati.`

Caso update applicato:
- `Aggiornamento completato per N pacchetti.`

Caso piano bloccato:
- `ERRORE: impossibile applicare gli aggiornamenti. Il piano e bloccato.`
- mostra i motivi restituiti da `scf_update_packages()` / `scf_apply_updates()`.

### Commit

Per ogni pacchetto aggiornato:
- commit separato consigliato
- messaggio:
  - `chore(packages): update <package-id> to vX.Y.Z`

Se l'update coinvolge piu pacchetti in un solo batch:
- consentito un commit unico
- messaggio:
  - `chore(packages): update SCF packages`

---

## Modifiche necessarie ai file framework

### spark-framework-engine.py

Nessuna modifica necessaria per la prima implementazione.

Motivazione:
- il motore ha gia `ManifestManager`;
- il motore ha gia `RegistryClient`;
- il motore ha gia `scf_update_packages()` e `scf_apply_updates()`;
- il fetch di `registry.json` e gia risolto internamente;
- non serve introdurre nuovi tool MCP.

### Agent-Orchestrator

Modifiche necessarie:
- aggiungere nel body una fase iniziale `Session Update Check` prima della sequenza E2E;
- usare `scf_get_runtime_state` / `scf_update_runtime_state` per leggere e settare `update_check_done`;
- chiamare `scf_update_packages()` una sola volta per sessione;
- mostrare il banner se esistono update.

Nessuna modifica richiesta al frontmatter oltre agli eventuali tool gia presenti se il pilot `tools:` viene confermato sufficiente.

### Agent-Welcome

Nessuna modifica necessaria nella prima implementazione.

Ruolo futuro opzionale:
- supporto alla migrazione del manifesto legacy nei progetti appena inizializzati o riparati manualmente.

### package-update.prompt.md

Nuovo file necessario.

Contenuti minimi:
- slash command `/package-update`
- sequenza operativa esplicita con `scf_update_packages()` e `scf_apply_updates()`
- supporto opzione `--skip`
- delega commit ad `Agent-Git`

### AGENTS-python.md

Aggiornamento documentale necessario.

Riga da allineare:
- `py-Agent-Code` deve esporre anche `code-ui`, `ui`, `docs`.

---

## Piano implementativo

### P1 — Abilitazione minima user-facing

1. Aggiornare `AGENTS-python.md` alle capability reali.
2. Creare `package-update.prompt.md`.
3. Integrare in `Agent-Orchestrator` il controllo one-shot `update_check_done`.
4. Implementare la migrazione del manifesto legacy nel flusso del prompt e del controllo sessione.

Impatto:
- porta il sistema da tool MCP grezzi a feature navigabile.

### P2 — Robustezza operativa

5. Aggiungere report utente piu dettagliato nel prompt update:
   - file aggiornati
   - file preservati
   - pacchetti bloccati
6. Standardizzare il commit per update multipackage.
7. Aggiornare README/documentazione del motore e del framework master.

Impatto:
- migliora trasparenza e supportabilita.

### P3 — Hardening opzionale

8. Valutare una compatibilita read-only nel motore per riconoscere anche il manifesto legacy senza migrazione preventiva.
9. Valutare memorizzazione nel runtime state di un mini-summary update per evitare ricalcoli intra-sessione.

Impatto:
- migliora backward compatibility, ma non e necessario per il primo rilascio.

---

## Rischi e mitigazioni

### R1. Manifesto legacy non migrabile automaticamente

Rischio:
- file elencati nel legacy manifest mancanti o incoerenti.

Mitigazione:
- bloccare l'update e mostrare errore guidato;
- non sovrascrivere il file legacy se la migrazione e parziale.

### R2. Update check troppo invasivo a inizio sessione

Rischio:
- banner ripetitivo o rumoroso.

Mitigazione:
- gate `update_check_done: true` nel runtime state;
- opzione `--skip`.

### R3. Confusione tra manifest runtime e stato sessione

Rischio:
- scrivere dati di sessione nel file manifesto pacchetti.

Mitigazione:
- separazione stretta:
  - `.scf-manifest.json` = stato installazione pacchetti
  - `orchestrator-state.json` = stato sessione runtime

---

## Esito del design

Il sistema update puo essere implementato senza patchare il motore MCP.

La strada raccomandata e:
- riusare il manifesto canonico `entries[]` gia gestito dal motore;
- migrare il file legacy dei progetti esistenti;
- costruire il layer user-facing con `Agent-Orchestrator` + `/package-update`;
- riusare integralmente `scf_update_packages()` e `scf_apply_updates()`.
