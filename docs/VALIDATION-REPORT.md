# SPARK Refactoring v1.2 — Validation Report

- Data: 2026-04-28
- Engine analizzato: spark-framework-engine 2.4.0
- Design analizzato: SPARK-REFACTORING-DESIGN-v1.2 (patch v1.2.1 applicata)
- Esecutore validazione: spark-engine-maintainer (autonomous)
- Iterazioni: 2 (Fase 2 → Decision Gate → patch design → Fase 2 → PASS)

## Verdetto

VALIDAZIONE SUPERATA dopo 1 ciclo correttivo.
Procedere con il piano implementativo (`SPARK-IMPLEMENTATION-PLAN.md`).

## Check superati

### Coerenza classi engine vs design

- `WorkspaceLocator` presente alla riga 458 di `spark-framework-engine.py`.
- `FrameworkInventory` presente alla riga 1144.
- `EngineInventory(FrameworkInventory)` presente alla riga 1308.
  Questa classe è il punto naturale di estensione per
  `engine-manifest.json` (Fase 1).
- `ManifestManager` presente alla riga 1391.
- `RegistryClient` presente alla riga 2277.
- `MergeEngine` (riga 118), `SnapshotManager` (riga 1839),
  `MergeSessionManager` (riga 2075) sono già disponibili e verranno
  riusati nei flussi di override-aware update e di migrazione.

### Coerenza schemi URI MCP

- URI `agents://`, `skills://`, `instructions://`, `prompts://`,
  `scf://` già registrati dinamicamente via helper
  `_register_resource()` (riga 2417). Il pattern dei "decorator
  dinamici" della Fase 4 è quindi un'estensione, non un'introduzione.
- URI `engine-skills://` (riga 2474) e `engine-instructions://`
  (riga 2489) presenti in v2.4.0. Strategia adottata: alias
  retrocompatibile (W3 fix).

### Coerenza schema manifest pacchetti

- `scf-master-codecrafter/package-manifest.json`: schema_version 2.1,
  min_engine_version 2.4.0, contiene `engine_provided_skills`.
- `scf-pycode-crafter/package-manifest.json`: schema_version 2.1,
  min_engine_version 2.4.0.
- `spark-base/package-manifest.json`: schema_version 2.1,
  min_engine_version 2.4.0, contiene `engine_provided_skills`.
- Migrazione additiva v2.1 → v3.0 applicabile su tutti e tre.
- Nessun manifest contiene già `workspace_files[]` o
  `mcp_resources{}`: nessun conflitto di nome.

### Invarianti critici

- `print(` su `spark-framework-engine.py`: 0 occorrenze. Stdio puro
  rispettato.
- Logging su stderr già attivo via prefisso `[SPARK-ENGINE]`.
- `ManifestManager` unico punto di scrittura sotto `.github/`
  (verificato a livello strutturale: tutti i write passano da metodi
  della classe).
- Gestione errori MCP via dict di ritorno: nessuna eccezione su
  stdout dal codice esaminato.

## Discrepanze risolte (patch v1.2.1 al design)

### D1 — Tool count corretto (CRITICO → RISOLTO)

- Conteggio reale: 35 funzioni `async def scf_*` registrate via
  `@_register_tool` in v2.4.0.
- Nuovi tool v3.0: 5 (`scf_list_resources`, `scf_read_resource`,
  `scf_override_resource`, `scf_drop_override`,
  `scf_migrate_workspace`).
- Totale post-refactor: 40 tool.
- `scf_update_profile` rimosso dallo scope v3.0 (rimandato a v3.1).
- Patch: §5.3 e §15 del design aggiornate al numero reale.

### D2 — engine-manifest.json deliverable Fase 1 (CRITICO → RISOLTO)

- File assente in repo (`file_search **/engine-manifest.json` → 0).
- Patch: §5.4 dichiara esplicitamente il file come deliverable Fase 1.
- Loader: `EngineInventory` esistente esteso per leggerlo prima del
  bootstrap pacchetti.

### D3 — Conteggio instruction (MAJOR → RISOLTO)

- Instruction reali: 9 file in `.github/instructions/`.
  Workspace (6): framework-guard, personality, verbosity,
  workflow-standard, git-policy, model-policy.
  MCP (3): spark-assistant-guide, spark-engine-maintenance,
  project-reset.
- Patch: §3.5 corretta.

### D4 — spark-welcome inesistente (MAJOR → RISOLTO)

- Agenti reali in `.github/agents/`: spark-assistant,
  spark-engine-maintainer, spark-guide. spark-welcome assente.
- Patch: §5.4 dichiara la creazione del file
  `.github/agents/spark-welcome.agent.md` come deliverable Fase 1.

### W3 — Schema URI ibrido (WARNING → RISOLTO)

- Mismatch tra `agents://` (proposto unificato) e
  `engine-skills://`/`engine-instructions://` (esistenti).
- Decisione: schema unificato `agents://`, `skills://`,
  `instructions://`, `prompts://` per tutte le risorse.
- `engine-skills://` e `engine-instructions://` mantenuti come
  alias retrocompatibili con warning su stderr alla prima
  invocazione. Rimozione pianificata in v4.0.
- Patch: §5.5 aggiornata.

### W4 — Errore RESOURCE_READONLY non implementabile (WARNING → RISOLTO)

- FastMCP non espone primitive di scrittura su Resource.
- Patch: §13.1 riformulata. Il vincolo "sola lettura" si esprime come
  proibizione di tool di scrittura diversi da `scf_override_resource`.

## Warning non bloccanti residui

- W1 — `.scf-registry-cache.json` già presente in repo engine in dev:
  per gli utenti finali può essere assente al momento della
  migrazione. `scf_migrate_workspace` deve gestirlo come "best effort
  move".
- W2 — `AGENTS.md` esiste già in `.github/` dell'engine. La
  generazione dinamica al bootstrap deve fare safe-merge (preservare
  testo utente fuori dai marker `SCF:BEGIN/END`), non sostituzione
  cieca.
- W5 — `MergeSessionManager` deve essere riusato nel flusso §13.5
  (override-aware update) per consistency con il sistema di conflict
  resolution esistente.
- W6 — Cline/Roo MCP Prompts: il client supporta MCP Prompts solo da
  versioni recenti. Documentare la versione minima richiesta nella
  guida utente prodotta in Fase 8.
- W7 — `scf_migrate_workspace` deve usare lo stesso pattern
  session-based di update (`session_id` + commit/rollback) per
  reversibilità tramite `SnapshotManager`.

## Prossima azione consigliata

Iniziare implementazione da `docs/todolist/PHASE-0-migrate-workspace.todo.md`
in modalità semi-autonoma con checkpoint obbligatorio prima di ogni
modifica a `spark-framework-engine.py`.
