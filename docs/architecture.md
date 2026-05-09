# Architettura — SPARK Framework Engine

> **Versione documentata:** 3.3.0  
> **Branch:** `feature/dual-mode-manifest-v3.1`  
> **Fonte:** `spark/core/constants.py:12` → `ENGINE_VERSION = "3.3.0"`

---

## 1. Panoramica

SPARK Framework Engine è un server MCP (Model Context Protocol) universale
scritto in Python 3.11+. Espone agenti, skill, instruction e prompt di qualsiasi
progetto SCF-compatibile come **Resources** e **Tools** consumabili da GitHub Copilot
in Agent mode.

Principi fondamentali verificati nel codice:

- **Nessun dato di dominio** — il motore legge `.github/` del progetto attivo dinamicamente.
- **Transport stdio** — il canale JSON-RPC è gestito interamente da FastMCP;
  nessuna scrittura su stdout è ammessa fuori dal canale (`spark/boot/sequence.py`).
- **Logging esclusivamente su stderr** — qualsiasi log del motore va su `sys.stderr`.
- **Idempotenza al bootstrap** — la sentinella `spark-assistant.agent.md` garantisce
  che il bootstrap non sovrascriva file utente già modificati
  (`spark/boot/engine.py` → `ensure_minimal_bootstrap()`).

---

## 2. Componenti Principali

| Modulo | Classe / File | Responsabilità |
|--------|---------------|----------------|
| **Entry point** | `spark-framework-engine.py` | Hub re-export + avvio stdio |
| **Builder** | `spark/boot/sequence.py` → `_build_app()` | Assembla tutti i sottosistemi |
| **Engine** | `spark/boot/engine.py` → `SparkFrameworkEngine` | Orchestratore centrale; registra resources e tools |
| **Costanti** | `spark/core/constants.py` | Tutte le costanti immutabili; zero logica |
| **Modelli** | `spark/core/models.py` | Dataclass immutabili (`WorkspaceContext`, `FrameworkFile`, `MergeResult`, …) |
| **Utility** | `spark/core/utils.py` | Helper condivisi senza effetti collaterali |
| **Inventory** | `spark/inventory/framework.py` → `FrameworkInventory` | Scoperta agenti/skill/instruction/prompt dal filesystem |
| **EngineInventory** | `spark/inventory/engine.py` → `EngineInventory` | Estende FrameworkInventory; carica `engine-manifest.json` |
| **Registry client** | `spark/registry/client.py` → `RegistryClient` | Accesso HTTP al registry pubblico SCF |
| **MCP registry** | `spark/registry/mcp.py` → `McpResourceRegistry` | Registro in-memory di resources engine + override |
| **Resource resolver** | `spark/registry/resolver.py` → `ResourceResolver` | Risoluzione URI `{type}://{name}` con fallback override → store |
| **Package store** | `spark/registry/store.py` → `PackageResourceStore` | Store engine-locale per pacchetti schema < 3.0 |
| **V3 store** | `spark/registry/v3_store.py` | Store engine-locale per pacchetti schema ≥ 3.0 |
| **Manifest** | `spark/manifest/manifest.py` → `ManifestManager` | CRUD su `.github/.scf-manifest.json`; cache mtime-based |
| **Gateway** | `spark/manifest/gateway.py` → `WorkspaceWriteGateway` | Scrittura atomica di file nel workspace utente con sha-sentinel |
| **Snapshots** | `spark/manifest/snapshots.py` → `SnapshotManager` | Backup/restore snapshot pre-update |
| **Diff** | `spark/manifest/diff.py` | Calcolo diff summary tra versioni di file |
| **Merge engine** | `spark/merge/engine.py` → `MergeEngine` | 3-way merge testuale con rilevamento marcatori conflitto |
| **Merge sessions** | `spark/merge/sessions.py` → `MergeSessionManager` | Sessioni interattive di merge su disco |
| **Merge sections** | `spark/merge/sections.py` | Merge per sezioni SCF (marcatori `SCF:BEGIN/END`) |
| **Merge validators** | `spark/merge/validators.py` | Validatori post-merge (frontmatter, struttura) |
| **Package lifecycle** | `spark/packages/lifecycle.py` | Download asincrono (ThreadPoolExecutor) + store install/remove |
| **Plugins** | `spark/plugins/facade.py` → `PluginManagerFacade` | Install/remove/update plugin via `.github/.spark-plugins` |
| **Onboarding** | `spark/boot/onboarding.py` → `OnboardingManager` | First-run automatico; idempotente, non-fatal |
| **Boot tools** | `spark/boot/tools_*.py` (10 file) | Factory function che registrano i 51 tool MCP |
| **Assets** | `spark/assets/phase6.py` | Bootstrap batch-write Cat. A con `write_many()` |
| **Workspace** | `spark/workspace/` | WorkspaceLocator e helper di risoluzione path |

---

## 3. Architettura Dual-Universe

Il motore gestisce due categorie distinte di componenti, definite in `README.md`
sezione "Architettura — Pacchetti interni vs Plugin Workspace":

### Universo A — MCP-Only

I pacchetti `spark-base`, `scf-master-codecrafter` e `scf-pycode-crafter` sono
serviti esclusivamente via MCP dallo store engine centralizzato.

- **Non generano file nel workspace utente.**
- Accesso tramite URI resource: `agents://`, `skills://`, `instructions://`, `prompts://`.
- `delivery_mode: "mcp_only"` nel `package-manifest.json`
  (`packages/spark-base/package-manifest.json:12`).
- `schema_version: "3.1"` richiesto per dichiarare `mcp_resources`.

### Universo B — Plugin Workspace

Plugin esterni e pacchetti con `delivery_mode: "file"` installano file fisici
nel workspace utente tramite `scf_plugin_install()` o `scf_install_package()`.

- Il file editing avviene direttamente nel filesystem di VS Code.
- Tracciamento in `.github/.scf-manifest.json` (ManifestManager).
- Preservation gate attivo: i file modificati dall'utente non vengono sovrascritti
  senza conferma esplicita (`force=True` o `conflict_mode` diverso da `abort`).

---

## 4. Ciclo di Bootstrap

Sequenza verificata in `spark/boot/sequence.py` (funzione `_build_app()`, righe 116-232):

```
1.  FastMCP("sparkFrameworkEngine")
2.  WorkspaceLocator(engine_root).resolve()  →  WorkspaceContext
3.  resolve_runtime_dir(engine_root, workspace_root)  →  runtime_dir
4.  _migrate_runtime_to_engine_dir(github_root, runtime_dir)   [idempotente]
5.  FrameworkInventory(context)
6.  validate_engine_manifest(engine_root) + inventory.populate_mcp_registry(engine_manifest)
7.  SparkFrameworkEngine(mcp, context, inventory, runtime_dir=runtime_dir)
8.  app.register_resources()
9.  app.register_tools()
10. app._v3_repopulate_registry()   ← boot-time: registra pacchetti installati dallo store
11. app.ensure_minimal_bootstrap()  ← auto Cat.A bootstrap
12. OnboardingManager(context, inventory, app).is_first_run()
    └─ se True: run_onboarding()
13. sys.stderr.write("[SPARK] Inizializzazione completata.\n")
```

**Passo 4 — migrazione runtime:** sposta `snapshots/`, `merge-sessions/`, `backups/`
da `.github/runtime/` alla directory locale del motore (idempotente).

**Passo 10 — `_v3_repopulate_registry()`:** garantisce che i pacchetti già
installati nello store vengano registrati nelle risorse MCP al boot, senza
aspettare la prossima operazione di install/remove.

**Passo 11 — `ensure_minimal_bootstrap()`:** copia i file Cat. A (definiti come
`workspace_files` nel manifest di `spark-base`) nel workspace utente se assenti.
La sentinella `spark-assistant.agent.md` è scritta per ultima per garantire
crash-safety idempotente.

---

## 5. Flusso di Installazione Pacchetti

### Percorso v3 (schema ≥ 3.0)

Gestito in `spark/boot/engine.py` → `_install_package_v3()` con supporto
`_install_workspace_files_v3()` (batch write + SHA sentinel skip).

```
1. Preflight (compatibilità motore, dipendenze, conflitti, ownership)
2. Download asincrono via ThreadPoolExecutor (spark/packages/lifecycle.py)
3. Install nello store engine-locale (packages/<pkg>/)
4. Salvataggio sentinel manifest
5. Scrittura workspace_files nel workspace utente  [con rollback su errore]
6. Aggiornamento registry MCP (_v3_repopulate_registry)
```

Rollback atomico: se la scrittura workspace fallisce, viene eseguito
`_remove_package_v3_from_store()` e le entry manifest vengono ripristinate.

### Percorso v2 (schema < 3.0 / legacy)

Scrittura diretta in `.github/` tramite `WorkspaceWriteGateway`.
Supporta `conflict_mode: abort | replace | manual | auto | assisted`.
Gestione merge sezioni via `MergeEngine` + `MergeSessionManager`.

### Schemi manifest supportati

```python
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {"1.0", "2.0", "2.1", "3.0"}
# Fonte: spark/core/constants.py
```

---

## 6. Onboarding Automatico

Verificato in `spark/boot/onboarding.py` → `OnboardingManager`.

### `is_first_run()`

Legge `.github/spark-packages.json` e confronta i pacchetti dichiarati con
`ManifestManager.get_installed_versions()`. Ritorna `False` su qualsiasi
errore di lettura (evita loop di re-onboarding).

### `run_onboarding()` — 3 passi

| Passo | Metodo | Descrizione |
|-------|--------|-------------|
| 1 | `_ensure_bootstrap()` | Verifica sentinelle Cat. A; chiama `ensure_minimal_bootstrap()` se necessario |
| 2 | `_ensure_store_populated()` | Verifica che lo store engine contenga almeno un `package-manifest.json` |
| 3 | `_install_declared_packages()` | Legge `.github/spark-packages.json`, installa pacchetti mancanti via `asyncio.run(app.install_package_for_onboarding(pkg))` |

**Status possibili:** `"completed"` (nessun errore) · `"partial"` (errori non fatali) · `"skipped"` (nessuno step completato).

**Critico:** tutti gli errori vanno solo su `stderr` — non vengono restituiti
all'utente né superficializzati via MCP.

---

## 7. Invarianti del Sistema

| Invariante | Dove verificato |
|------------|----------------|
| Zero `print()` su stdout | Transport stdio FastMCP — tutto il log su `sys.stderr` |
| Manifest cache mtime-based | `ManifestManager.load()` in `spark/manifest/manifest.py` |
| Scritture `.github/` richiedono `github_write_authorized: true` | `tools_override.py`, `tools_bootstrap.py` |
| `spark-assistant.agent.md` scritta per ultima al bootstrap | `spark/assets/phase6.py` + `spark/boot/engine.py` |
| Rollback automatico su errore write workspace | `spark/boot/engine.py` → `_install_package_v3()` |
| File utente-modificati preservati (SHA mismatch gate) | `WorkspaceWriteGateway` in `spark/manifest/gateway.py` |
| Bootstrap è idempotente | Sentinella `spark-assistant.agent.md` + SHA-skip su file invariati |
| Tool pubblici richiedono decorator `@_register_tool("scf_*")` | Convention in tutti i `tools_*.py` |

---

## 8. File e Cartelle Chiave

```
spark-framework-engine/
├── spark-framework-engine.py      Entry point (hub re-export + stdio run)
├── engine-manifest.json           Risorse engine-owned (6 instruction, 4 agenti, 3 instruction MCP)
├── spark-init.py                  Script inizializzazione workspace utente
├── packages/
│   ├── spark-base/                Pacchetto fondazionale (mcp_only, schema 3.1)
│   ├── scf-master-codecrafter/   Layer master programmatico
│   └── scf-pycode-crafter/       Layer Python-specifico
├── spark/
│   ├── core/                      Costanti, modelli, utility (zero dipendenze interne)
│   ├── boot/                      Engine, sequence, onboarding, 10 factory di tool
│   ├── inventory/                 Discovery agenti/skill/instruction/prompt
│   ├── manifest/                  ManifestManager, Gateway, Snapshots, Diff
│   ├── registry/                  Client, McpResourceRegistry, Resolver, Store, V3Store
│   ├── merge/                     MergeEngine, Sessions, Sections, Validators
│   ├── packages/                  Package lifecycle (download asincrono)
│   ├── plugins/                   PluginManagerFacade (legacy plugin workspace)
│   ├── workspace/                 WorkspaceLocator e helper path
│   └── assets/                    Phase6 bootstrap batch assets
├── docs/                          Documentazione tecnica e piani
├── tests/                         Suite pytest (≥ 534 test, esclude test_integration_live.py)
└── runtime/                       Directory locale engine (snapshots, merge-sessions, backups)
```

---

## 9. Costanti di Riferimento

```python
# spark/core/constants.py

ENGINE_VERSION                 = "3.3.0"
_MANIFEST_FILENAME             = ".scf-manifest.json"
_MANIFEST_SCHEMA_VERSION       = "3.0"
_SUPPORTED_MANIFEST_SCHEMA_VERSIONS = {"1.0", "2.0", "2.1", "3.0"}
_BOOTSTRAP_PACKAGE_ID          = "scf-engine-bootstrap"   # owner placeholder Cat.A
_REGISTRY_URL                  = "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
_RESOURCE_TYPES                = ("agents", "prompts", "skills", "instructions")
_ALLOWED_UPDATE_MODES          = {"ask", "integrative", "replace", "conservative", "selective"}
_CHANGELOGS_SUBDIR             = "changelogs"
_SNAPSHOTS_SUBDIR              = "snapshots"
_MERGE_SESSIONS_SUBDIR         = "merge-sessions"
_BACKUPS_SUBDIR                = "backups"
```
