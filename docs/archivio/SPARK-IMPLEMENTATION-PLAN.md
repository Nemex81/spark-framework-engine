# SPARK Refactoring — Implementation Plan v3.0.0

- Versione engine target: 3.0.0
- Versione engine attuale: 2.4.0
- Data: 2026-04-28
- Numero totale fasi: 9 (Fase 0 + Fasi 1-8)
- Numero totale task atomici: 47
- Effort complessivo stimato: L (>4h cumulative)

## Riepilogo fasi e dipendenze

- Fase 0 — Migration tool standalone (priorità alta, pre-deploy)
  - Dipende da: nessuna
  - Effort: M
- Fase 1 — Schema manifest v3.0 + engine-manifest.json + spark-welcome
  - Dipende da: Fase 0
  - Effort: M
- Fase 2 — PackageResourceStore + McpResourceRegistry
  - Dipende da: Fase 1
  - Effort: L
- Fase 3 — Tool MCP override (4 nuovi tool)
  - Dipende da: Fase 2
  - Effort: M
- Fase 4 — Decorator FastMCP dinamici + alias retrocompatibili
  - Dipende da: Fase 3
  - Effort: S
- Fase 5 — WorkspaceLocator estensioni + cache relocation + CLI flag
  - Dipende da: Fase 2
  - Effort: S
- Fase 6 — scf_bootstrap_workspace aggiornato + AGENTS.md dinamico
  - Dipende da: Fasi 1, 2, 5
  - Effort: M
- Fase 7 — ManifestManager snellimento + smoke test Copilot
  - Dipende da: Fase 6
  - Effort: M
- Fase 8 — Deploy v3.0.0 + documentazione migrazione
  - Dipende da: tutte le precedenti
  - Effort: S

## Fase 0 — scf_migrate_workspace

### Obiettivo

Implementare il tool di migrazione workspace v2.x → v3.0 PRIMA del
rilascio dell'engine v3.0. Strumento di preparazione, attivabile
anche su engine v2.4.0 come patch backportata.

### File modificati

- `spark-framework-engine.py`: nuovo tool `scf_migrate_workspace`
  registrato via `@_register_tool`.
- `tests/test_migrate_workspace.py`: nuovo test suite.

### File creati

- Nessun file aggiuntivo (il tool è interno all'engine).

### Test di accettazione

- Workspace v2.x simulato con `agents/*.agent.md` modificati →
  spostati in `.github/overrides/agents/`.
- Workspace v2.x con `AGENTS.md` non modificato → eliminato.
- Workspace v2.x con `.scf-registry-cache.json` → spostato in
  `engine_dir/cache/`.
- Modalità `dry_run=True` → migration_plan ritornato senza
  side-effect su filesystem.
- Modalità `dry_run=False` con session-based commit/rollback via
  `SnapshotManager`: rollback funziona se test inietta errore.

## Fase 1 — Schema manifest v3.0 + engine-manifest.json + spark-welcome

### Obiettivo

Aggiornare lo schema dei manifest pacchetto a v3.0 in modo
additivo (zero breaking change). Creare il manifest interno
dell'engine. Creare l'agente engine `spark-welcome`.

### File modificati

- `spark-base/package-manifest.json`: schema_version → 3.0,
  aggiunti `workspace_files[]` e `mcp_resources{}`.
- `scf-master-codecrafter/package-manifest.json`: idem.
- `scf-pycode-crafter/package-manifest.json`: idem.

### File creati

- `spark-framework-engine/engine-manifest.json`.
- `spark-framework-engine/.github/agents/spark-welcome.agent.md`.

### Test di accettazione

- Engine v2.4.0 (in stage) legge manifest v3.0 senza errori (fallback
  su `files`).
- `EngineInventory` carica `engine-manifest.json` al boot e popola
  `mcp_resources` correttamente.
- `agents://spark-welcome` risolve al file engine-manifest dichiarato.

## Fase 2 — PackageResourceStore + McpResourceRegistry

### Obiettivo

Introdurre due nuove classi per il deposito centralizzato di risorse
e l'indice URI → path con supporto override.

### File modificati

- `spark-framework-engine.py`: nuove classi prima di
  `SparkFrameworkEngine`.
- `tests/test_resource_store.py`: nuova suite.
- `tests/test_resource_registry.py`: nuova suite.

### File creati

- Nessun file di asset (le classi sono interne all'engine).

### Test di accettazione

- `PackageResourceStore.resolve("scf-master-codecrafter", "agents",
  "code-Agent-Code")` ritorna Path corretto al file engine-store.
- `McpResourceRegistry.resolve("agents://code-Agent-Code")` ritorna
  override se esiste, altrimenti engine.
- `register_override` aggiorna correttamente l'entry.
- `verify_integrity(package_id)` rileva file modificati post-install.

## Fase 3 — Tool MCP override

### Obiettivo

Implementare i 4 tool di gestione override.

### File modificati

- `spark-framework-engine.py`: 4 nuovi `@_register_tool`.
- `tests/test_override_tools.py`: nuova suite.

### Test di accettazione

- `scf_list_resources("agents")` lista agenti con flag
  `has_override`.
- `scf_read_resource("agents://X", source="auto")` ritorna override
  se esiste.
- `scf_read_resource(..., source="engine")` ritorna sempre engine.
- `scf_override_resource("agents://X", content)` crea
  `.github/overrides/agents/X.md`.
- `scf_drop_override("agents://X")` rimuove file e aggiorna
  registry.

## Fase 4 — Decorator FastMCP dinamici + alias retrocompatibili

### Obiettivo

Estendere il sistema di decorator dinamici a tutti i tipi di
risorsa, mantenendo alias retrocompatibili per
`engine-skills://` e `engine-instructions://`.

### File modificati

- `spark-framework-engine.py`: handler URI unificati,
  alias logger su prima invocazione.

### Test di accettazione

- Copilot "Add Context > MCP Resources" mostra tutti gli agenti
  inclusi quelli engine.
- `engine-skills://name` ritorna stesso contenuto di
  `skills://name`, con warning loggato una volta su stderr.

## Fase 5 — WorkspaceLocator estensioni + cache + CLI

### Obiettivo

Aggiungere metodi di path resolution e supporto CLI per Cline/Roo.

### File modificati

- `spark-framework-engine.py`: metodi
  `get_engine_cache_dir()`, `get_override_dir()`, parsing
  argomento `--workspace`.
- `RegistryClient`: cache path → engine_dir/cache/.
- `tests/test_workspace_locator.py`: nuovi test.

### Test di accettazione

- `--workspace C:\path` valido → `WorkspaceLocator` usa quel path.
- Cache scritta in engine_dir/cache/registry-cache.json.
- `get_override_dir(ws, "agents")` crea directory se non esiste.

## Fase 6 — scf_bootstrap_workspace aggiornato

### Obiettivo

Aggiornare il bootstrap per generare AGENTS.md dinamicamente,
generare `.clinerules`, scansionare overrides, scrivere template
`project-profile.md`.

### File modificati

- `spark-framework-engine.py`: tool
  `scf_bootstrap_workspace` riscritto.
- `tests/test_bootstrap_workspace.py`: estensioni esistenti +
  nuovi test.

### Test di accettazione

- Bootstrap workspace vergine → `.github/copilot-instructions.md`,
  `.github/AGENTS.md`, `.github/project-profile.md` template,
  `.clinerules` generati.
- Bootstrap su workspace con `.github/overrides/` → registry
  popolata con override.
- Bootstrap idempotente: secondo run non sovrascrive
  `project-profile.md` modificato.

## Fase 7 — ManifestManager + smoke test Copilot

### Obiettivo

Snellire `ManifestManager` per tracciare SHA-256 solo su
workspace_files + overrides. Eseguire smoke test completo Copilot.

### File modificati

- `spark-framework-engine.py`: refactoring `ManifestManager`.
- `tests/test_manifest_manager.py`: aggiornamenti.

### Test di accettazione (smoke test Copilot manuale)

- Bootstrap workspace → AGENTS.md generato correttamente.
- Copilot riconosce agenti in copilot-instructions.md.
- Copilot accede a MCP Resources per agenti non nel workspace.
- `scf_override_resource` crea file in `.github/overrides/`.
- `scf_read_resource` ritorna override corretto.
- `scf_drop_override` ripristina engine.
- Install/remove pacchetto → AGENTS.md aggiornato automaticamente.

## Fase 8 — Deploy v3.0.0 + documentazione

### Obiettivo

Tag rilascio, CHANGELOG, README aggiornato, guida migrazione utenti.

### File modificati

- `spark-framework-engine.py`: `ENGINE_VERSION = "3.0.0"`.
- `CHANGELOG.md`: voce v3.0.0.
- `README.md`: sezione "Migrazione da v2.x".
- `docs/MIGRATION-GUIDE-v3.md`: nuovo file.

### Test di accettazione

- Tag git proposto: `v3.0.0` (l'esecuzione resta delegata
  all'utente o ad Agent-Git).
- Workspace v2.x reale di test → migrato senza perdita dati
  utente.

## Matrice rischi

### Fase 0

- Rischio: migrazione distruttiva su workspace utente.
  Mitigation: dry_run obbligatorio prima di esecuzione,
  `SnapshotManager` per rollback, modalità `force=False` di default.

### Fase 1

- Rischio: manifest v3.0 mal formattato rompe boot engine v2.4.0.
  Mitigation: fallback su campo `files` in v2.4.0 già esistente,
  test integrazione cross-version prima del merge.

### Fase 2

- Rischio: `McpResourceRegistry` non thread-safe in scenari
  concorrenti.
  Mitigation: scrittura registry solo al boot e su tool
  override/drop, lettura senza lock.

### Fase 3

- Rischio: `scf_override_resource` scrive fuori da `ManifestManager`.
  Mitigation: il tool delega a `ManifestManager.write_override()`,
  gate `github_write_authorized` rispettato.

### Fase 4

- Rischio: alias rompe client Cline/Roo che cachano URI.
  Mitigation: alias trasparente lato server, log su stderr ma
  risposta MCP identica.

### Fase 5

- Rischio: cache su engine_dir richiede write permission.
  Mitigation: fallback su `%APPDATA%\spark-engine\cache\` (Windows)
  o `~/.cache/spark-engine/` (Unix) se engine_dir read-only.

### Fase 6

- Rischio: AGENTS.md dinamico sovrascrive personalizzazioni.
  Mitigation: safe-merge tra marker SCF:BEGIN/END, testo utente
  preservato.

### Fase 7

- Rischio: smoke test Copilot trova regressione.
  Mitigation: rollback merge, fix mirato, retry. Non procedere a
  Fase 8 senza smoke test verde.

### Fase 8

- Rischio: utenti su engine v2.x non vedono prompt di migrazione.
  Mitigation: documentare in CHANGELOG e nella prima resource
  `scf://framework-version` la presenza di `scf_migrate_workspace`.
