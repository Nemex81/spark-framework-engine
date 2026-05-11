# SPARK-REPORT: MCP Server Flow v1.0

**Data:** 2026-05-11
**Versione motore:** spark-framework-engine v3.4.0
**Branch:** workspace-slim-registry-sync-20260511
**Scope:** Documentazione tecnica — nessuna modifica al codice

---

## Indice

1. Flusso di avvio del server MCP
2. Architettura Dual-Universe
3. Bootstrap nuovo utente: scf_bootstrap_workspace
4. Gestione universi: avvio, riavvio e installazioni indipendenti
5. Riepilogo tool e resource esposti

---

## 1. Flusso di avvio del server MCP

Il server viene avviato dal file principale `spark-framework-engine.py` tramite il
punto di ingresso canonico:

```
_build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")
```

Il transport è esclusivamente stdio (JSON-RPC). Tutto il logging va su stderr. Mai
su stdout, che appartiene al canale JSON-RPC.

### 1.1 Sequenza di avvio in `_build_app` (spark/boot/sequence.py)

```
Passo 1 — FastMCP istanziato
  FastMCP("sparkFrameworkEngine")

Passo 2 — WorkspaceLocator.resolve()
  Determina engine_root e workspace_root.
  Emette log: "Workspace resolved: <path>"

Passo 3 — resolve_runtime_dir()
  Calcola la directory runtime isolata per workspace.
  Migrazione legacy: _migrate_runtime_to_engine_dir()
    spostamento .github/runtime/{snapshots,merge-sessions,backups}
    → engine_root/<hash-workspace>/{snapshots,merge-sessions,backups}
    Idempotente: marker .runtime-migrated controlla lo stato.

Passo 4 — FrameworkInventory(context)
  Enumera agenti, skill, instruction e prompt presenti nel workspace.
  Emette log: conteggio per categoria.

Passo 5 — validate_engine_manifest()
  Legge engine-manifest.json dalla root del motore.
  Non blocca l'avvio in caso di errore (SPARK_STRICT_BOOT=1 per comportamento fatale).

Passo 6 — inventory.populate_mcp_registry(engine_manifest)
  Popola McpResourceRegistry con risorse engine + override workspace.
  Emette log: "MCP resource registry: N URI registrati"

Passo 7 — SparkFrameworkEngine istanziato
  Riceve: mcp, context, inventory, runtime_dir
  Inizializza lazy (a None): manifest, registry_client, merge_engine, snapshots, sessions

Passo 8 — app.register_resources()
  Registra le resource MCP (URI agents://, skills://, prompts://, instructions://, scf://)

Passo 9 — app.register_tools()
  Chiama _init_runtime_objects() (inizializza ManifestManager, RegistryClient, ecc.)
  Delega la registrazione dei tool ai moduli factory:
    - tools_resources.py    → register_resource_tools()
    - tools_override.py     → register_override_tools()
    - tools_bootstrap.py    → register_bootstrap_tools()
    - tools_policy.py       → register_policy_tools()
    - tools_packages.py     → register_package_tools()
    - tools_plugins.py      → register_plugin_tools()

Passo 10 — app._v3_repopulate_registry()
  Ricarica la McpResourceRegistry includendo i pacchetti nel deposito packages/.
  Garantisce che dopo un riavvio del server i pacchetti installati siano visibili.
  Emette log: "MCP registry repopulated at boot: N URI totali"

Passo 11 — app.ensure_minimal_bootstrap()
  Sentinel gate: controlla la presenza simultanea di 5 file Cat. A:
    .github/agents/spark-assistant.agent.md
    .github/agents/spark-guide.agent.md
    .github/AGENTS.md
    .github/copilot-instructions.md
    .github/project-profile.md
  Se tutti presenti → status: "already_present"
  Se manca anche uno solo → esegue asyncio.run(_bootstrap_workspace_tool())
  Emette log: "Auto-bootstrap status: <status>"

Passo 12 — OnboardingManager.is_first_run() + run_onboarding()
  Primo avvio: installa spark-base, configura agenti e profilo progetto.
  Idempotente: salta se il workspace è già configurato.
  Emette log: "Onboarding completato: <status>"

Passo 13 — Output su stderr
  "[SPARK] Inizializzazione completata."
  "[SPARK] Prossimo passo: apri VS Code e di' a Copilot 'inizializza il workspace SPARK'"
```

### 1.2 _init_runtime_objects (lazy, idempotente)

Chiamato all'inizio di `register_tools()`. Inizializza una sola volta:

| Oggetto              | Classe                | Responsabilità                          |
|----------------------|-----------------------|-----------------------------------------|
| `_manifest`          | ManifestManager       | Stato installato, integrità workspace   |
| `_registry_client`   | RegistryClient        | Fetch registry remoto, cache locale     |
| `_merge_engine`      | MergeEngine           | Merge sezioni copilot-instructions.md   |
| `_snapshots`         | SnapshotManager       | Snapshot pre-install per rollback       |
| `_sessions`          | MergeSessionManager   | Sessioni merge in corso                 |
| `_plugin_manager`    | PluginManagerFacade   | Gestione plugin language-specific       |

Se `_manifest is not None` → cleanup sessioni scadute e ritorno immediato.

---

## 2. Architettura Dual-Universe

Il motore gestisce due universi di distribuzione per i pacchetti SCF.

### 2.1 Universe A — Deposito locale (delivery_mode: mcp_only)

Condizione di attivazione: il manifesto del pacchetto in `packages/<id>/package-manifest.json`
dichiara `"delivery_mode": "mcp_only"`.

Flusso:
```
1. _try_local_install_context(package_id) legge packages/<id>/package-manifest.json
2. Se delivery_mode == "mcp_only" e files non vuoto → contesto Universe A
3. I file vengono letti da packages/<id>/.github/<rel_path> (accesso locale su disco)
4. Nessuna chiamata HTTP. Nessuna dipendenza da rete.
5. Log: "[SPARK-ENGINE][INFO] Universe A: resolved '<id>' from local store (delivery_mode=mcp_only)."
```

Pacchetti in Universe A (questa versione del motore):

| Pacchetto    | Versione | Dipende da     | Descrizione                             |
|--------------|----------|----------------|-----------------------------------------|
| spark-base   | 2.1.0    | (nessuna)      | Layer fondazionale: agenti core, skill  |
| spark-ops    | 1.1.0    | spark-base 2.0 | Layer operativo: orchestrazione, release|

### 2.2 Universe B — Registry remoto

Condizione di attivazione: il pacchetto non è nel deposito locale, oppure non dichiara
`delivery_mode: mcp_only`.

Flusso:
```
1. RegistryClient.list_packages() → fetch da _REGISTRY_URL (con cache locale)
2. registry.fetch_package_manifest(repo_url) → legge package-manifest.json dal repo GitHub
3. File scaricati da URL raw (raw.githubusercontent.com/<repo>/…)
4. Timeout: _REGISTRY_TIMEOUT_SECONDS
5. Fallback su cache .scf-registry-cache.json se la rete non è raggiungibile
```

### 2.3 Router Universe A/B

`_get_package_install_context(package_id)` in `tools_bootstrap.py`:

```python
local_ctx = _try_local_install_context(package_id)
if local_ctx is not None:
    return local_ctx           # Universe A
return _ih._get_package_install_context(package_id, registry, manifest)  # Universe B
```

Universe A ha precedenza. Se il pacchetto non è nel deposito locale → Universe B.

### 2.4 Separazione spark-base / spark-ops

Con la versione spark-base 2.1.0 e spark-ops 1.1.0, le responsabilità sono distribuite:

#### spark-base (Universe A, v2.1.0)

Contenuto dichiarato in `mcp_resources`:

- Agenti (9): Agent-Analyze, Agent-Docs, Agent-Git, Agent-Helper, Agent-Orchestrator,
  Agent-Plan, Agent-Research, Agent-Validate, Agent-Welcome
- Prompt (26): framework-unlock, git-commit, git-merge, help, init, orchestrate, personality,
  project-setup, project-update, scf-check-updates, scf-install, scf-list-available,
  scf-list-installed, scf-migrate-workspace, scf-package-info, scf-pre-implementation-audit,
  scf-remove, scf-status, scf-update, scf-update-batch, scf-update-policy, scf-update-single,
  start, status, sync-docs, verbosity
- Skill (19): accessibility-output, agent-selector, changelog-entry, conventional-commit,
  document-template, error-recovery, file-deletion-guard, framework-guard, framework-index,
  framework-query, framework-scope-guard, git-execution, personality, project-doc-bootstrap,
  project-profile, project-reset, rollback-procedure, semantic-gate, semver-bump,
  style-setup, task-scope-guard, validate-accessibility, verbosity
- Instruction (8): framework-guard, git-policy, model-policy, personality, project-reset,
  spark-assistant-guide, verbosity, workflow-standard
- `workspace_files` (10): copilot-instructions.md, 8 instruction files, project-profile.md

Nota: spark-base non esporta più Agent-FrameworkDocs, Agent-Release, spark-assistant,
spark-guide, né i prompt framework-changelog, framework-release, framework-update, release.
Questi sono stati migrati a spark-ops nella versione 2.1.0.

#### spark-ops (Universe A, v1.1.0)

Contenuto dichiarato in `mcp_resources`:

- Agenti (4): Agent-FrameworkDocs, Agent-Release, spark-assistant, spark-guide
- Prompt (4): framework-changelog, framework-release, framework-update, release
- Skill: (nessuna dichiarata in mcp_resources)
- Instruction: (nessuna dichiarata in mcp_resources)
- `workspace_files`: [] (nessun file workspace; erogazione solo MCP)
- `files` (10 file fisici): AGENTS.md, Agent-FrameworkDocs.md, Agent-Release.md,
  spark-assistant.agent.md, spark-guide.agent.md, changelogs/spark-ops.md,
  4 prompt files
- Dipende da: spark-base >= 2.0.0

---

## 3. Bootstrap nuovo utente: scf_bootstrap_workspace

`scf_bootstrap_workspace` è registrato in `tools_bootstrap.py` come tool MCP.
È anche il tool a cui `ensure_minimal_bootstrap()` delega al Passo 11 dell'avvio.

### 3.1 Parametri

| Parametro       | Tipo    | Default   | Descrizione                                         |
|-----------------|---------|-----------|-----------------------------------------------------|
| `install_base`  | bool    | True      | Installa spark-base se non già installato           |
| `conflict_mode` | str     | "auto"    | Gestione conflitti: abort, replace, manual, auto, assisted |
| `update_mode`   | str     | ""        | Politica update: ask, integrative, conservative, ask_later |

### 3.2 Validazione input

Prima di procedere, il tool valida:
- `conflict_mode` deve essere in: abort, replace, manual, auto, assisted
- `update_mode` deve essere in: "", ask, integrative, conservative, ask_later

In caso di valore non valido → ritorna immediatamente con `status: "error"`.

### 3.3 Flusso principale

```
Passo A — Risoluzione source root
  bootstrap_source_root = engine_root/packages/spark-base/.github
  Fallback: engine_root/.github (retro-compat)

Passo B — Sentinel check
  sentinel = .github/agents/Agent-Welcome.md
  Se presente: workspace già bootstrapped in precedenza.

Passo C — Stato migrazione workspace
  _detect_workspace_migration_state()
  Rileva se il workspace è in formato legacy (v2) o v3.

Passo D — Configurazione policy update (se update_mode != "")
  Se nessun file policy presente (.github/scf-update-policy.json):
    Crea policy con _configure_initial_bootstrap_policy(selected_mode)
  Se policy già presente: usa quella esistente.
  update_mode = "ask_later" → policy creata con default, update rinviato.

Passo E — Installazione spark-base (se install_base=True)
  Passa per il router Universe A/B via scf_install_package("spark-base")
  Universe A: legge file da packages/spark-base/
  Applica file in .github/ rispettando scf_merge_strategy per file di sistema

Passo F — Phase 6 assets
  _apply_phase6_assets(): genera/aggiorna AGENTS.md e .clinerules
  con gli agenti effettivamente installati

Passo G — Risposta
  Ritorna dict con: success, status, files_written, files_skipped,
  files_protected, diff_summary, sentinel_present, workspace
```

### 3.4 Classificazione file durante il bootstrap

Ogni file nel pacchetto viene classificato prima della scrittura:

| Tipo file            | Condizione                          | Comportamento                          |
|----------------------|-------------------------------------|----------------------------------------|
| `spark_outdated`     | frontmatter `spark: true` presente  | Aggiorna solo frontmatter (body utente preservato) |
| `non_spark`          | nessun frontmatter spark            | Dipende da conflict_mode               |
| Nuovo (non esiste)   | dest_path non esiste                | Scritto direttamente                   |

Logica di classificazione (`_classify_bootstrap_conflict`):
- Solo file `.md` vengono ispezionati.
- File non `.md` → sempre `"non_spark"`.
- File `.md` con `spark: true` nel frontmatter → `"spark_outdated"`.

### 3.5 Scrittura file: WorkspaceWriteGateway

Tutte le scritture su `.github/` passano per `WorkspaceWriteGateway`. Questo garantisce:
1. Aggiornamento del manifest entry corrispondente (INVARIANTE-4).
2. Tracciamento owner, versione e merge_strategy per ogni file.

---

## 4. Gestione universi: avvio, riavvio e installazioni indipendenti

### 4.1 Avvio iniziale

Al primo avvio in un workspace senza `.github/`:
1. `ensure_minimal_bootstrap()` → sentinel assente → esegue bootstrap automatico
2. `OnboardingManager.is_first_run()` → `True` → esegue `run_onboarding()`
3. spark-base viene installato da Universe A (locale)
4. Phase 6 assets generati (AGENTS.md, .clinerules)
5. Messaggio finale su stderr con istruzioni per l'utente

### 4.2 Riavvio del server (workspace già configurato)

1. `ensure_minimal_bootstrap()` → tutti i 5 file Cat. A presenti → `status: "already_present"`
2. `OnboardingManager.is_first_run()` → `False` → onboarding saltato
3. `_v3_repopulate_registry()` → ricarica pacchetti installati nel McpResourceRegistry
4. Tool e resource disponibili immediatamente al client

Il Passo 10 (`_v3_repopulate_registry`) è critico per il riavvio: senza di esso i
pacchetti installati nel deposito `packages/` non sarebbero visibili via
`scf_get_agent`, `scf_get_skill`, ecc. fino alla prima operazione install/remove.

### 4.3 Installazione pacchetto aggiuntivo (es. spark-ops)

```
1. Copilot invoca scf_install_package("spark-ops")
2. _get_package_install_context("spark-ops")
   → _try_local_install_context() trova packages/spark-ops/package-manifest.json
   → delivery_mode = "mcp_only" → Universe A
3. Verifica dipendenze: spark-base >= 2.0.0 deve essere già installato
4. _build_local_file_records(): legge file da packages/spark-ops/
5. File scritti in .github/ tramite WorkspaceWriteGateway
6. Snapshot pre-install salvato in runtime_dir/snapshots/
7. ManifestManager aggiornato (versione installata)
8. _v3_repopulate_registry() chiamato → nuovi agenti/prompt spark-ops visibili
```

### 4.4 Installazione indipendente dei due layer

spark-base e spark-ops si installano in modo indipendente:
- spark-base non dipende da altri pacchetti SCF.
- spark-ops dipende solo da spark-base >= 2.0.0.
- Non vi sono dipendenze circolari.
- Un workspace può avere solo spark-base (senza spark-ops) in modo stabile.
- spark-ops non può essere installato senza spark-base.

### 4.5 Coerenza registry

`scf_verify_system()` esegue la verifica cross-component:
1. Legge le versioni installate dal ManifestManager
2. Confronta con il registry remoto via RegistryClient
3. Segnala discrepanze tra versione manifest del pacchetto e latest_version nel registry
4. Segnala pacchetti installati ma assenti nel registry (warning, non errore)

---

## 5. Riepilogo tool e resource esposti

### 5.1 URI Schema resource

| Prefisso URI              | Contenuto                                      |
|---------------------------|------------------------------------------------|
| `agents://<nome>`         | File agente (engine + packages installati)     |
| `skills://<nome>`         | File skill                                     |
| `prompts://<nome>`        | File prompt                                    |
| `instructions://<nome>`   | File instruction                               |
| `scf://agents-index`      | Indice AGENTS.md + AGENTS-*.md                 |
| `scf://runtime-state`     | Stato runtime orchestratore                    |
| `scf://packages`          | Pacchetti installati                           |
| `scf://registry`          | Pacchetti disponibili nel registry             |

### 5.2 Tool MCP bootstrap e verifica

| Tool                    | Modulo factory          | Descrizione                                       |
|-------------------------|-------------------------|---------------------------------------------------|
| `scf_bootstrap_workspace` | tools_bootstrap.py    | Bootstrap workspace nuovo utente                  |
| `scf_verify_workspace`  | tools_bootstrap.py      | Verifica integrità manifest vs workspace fisico   |
| `scf_verify_system`     | tools_bootstrap.py      | Verifica coerenza engine/pacchetti/registry       |
| `scf_migrate_workspace` | tools_bootstrap.py      | Migrazione workspace da formato v2 a v3           |

### 5.3 Tool MCP pacchetti

| Tool                    | Modulo factory          | Descrizione                                       |
|-------------------------|-------------------------|---------------------------------------------------|
| `scf_install_package`   | tools_packages.py       | Installa pacchetto (Universe A/B)                 |
| `scf_update_package`    | tools_packages.py       | Aggiorna pacchetto installato                     |
| `scf_remove_package`    | tools_packages.py       | Rimuove pacchetto installato                      |
| `scf_list_installed_packages` | tools_packages.py | Elenca pacchetti installati con versioni          |
| `scf_list_available_packages` | tools_packages.py | Elenca pacchetti disponibili nel registry         |
| `scf_check_updates`     | tools_packages.py       | Verifica aggiornamenti disponibili                |

### 5.4 Tool MCP policy

| Tool                    | Modulo factory          | Descrizione                                       |
|-------------------------|-------------------------|---------------------------------------------------|
| `scf_get_update_policy` | tools_policy.py         | Legge politica di aggiornamento corrente          |
| `scf_set_update_policy` | tools_policy.py         | Imposta modalità update (auto/confirm/manual)     |

### 5.5 Tool MCP resource (lettura)

| Tool                    | Modulo factory          | Descrizione                                       |
|-------------------------|-------------------------|---------------------------------------------------|
| `scf_get_agent`         | tools_resources.py      | Recupera agente per nome                          |
| `scf_get_skill`         | tools_resources.py      | Recupera skill per nome                           |
| `scf_get_prompt`        | tools_resources.py      | Recupera prompt per nome                          |
| `scf_get_instruction`   | tools_resources.py      | Recupera instruction per nome                     |
| `scf_get_runtime_state` | tools_resources.py      | Legge orchestrator-state.json                     |
| `scf_update_runtime_state` | tools_resources.py   | Aggiorna patch in orchestrator-state.json         |
| `scf_list_agents`       | tools_resources.py      | Elenca agenti disponibili                         |
| `scf_list_skills`       | tools_resources.py      | Elenca skill disponibili                          |
| `scf_list_prompts`      | tools_resources.py      | Elenca prompt disponibili                         |
| `scf_list_instructions` | tools_resources.py      | Elenca instruction disponibili                    |

---

## Note operative

- Logging esclusivamente su `stderr`. Mai su `stdout` (canale JSON-RPC).
- Prefisso `[SPARK-ENGINE][INFO]` per messaggi informativi.
- Prefisso `[SPARK-ENGINE][WARNING]` per condizioni non fatali.
- ERRORE: il prefisso `ERRORE:` è riservato ai blocchi critici nella risposta testuale.
- Il file `spark-framework-engine.py` (root) è solo hub di re-export e punto di ingresso.
  Nessuna logica applicativa risiede direttamente in quel file dalla Fase 0 del refactoring.
- I test si trovano in `tests/`. Eseguire con:
  `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_integration_live.py`

---

*Report generato da spark-engine-maintainer — documentazione interna, nessuna modifica al codice.*
