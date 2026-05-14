> **STATO: COMPLETATO** — Archiviato il 2026-05-14 (ENGINE_VERSION 3.6.0).
> Documento di sola lettura. Non modificare.

***

---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Piano Tecnico Fase 0 — Modularizzazione SPARK Engine
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Piano Tecnico Fase 0 — Modularizzazione

## 1. Contesto

Il sorgente `spark-framework-engine.py` misura **8.386 righe / 369 KB** (verificato il 1 Maggio 2026). La Fase 0 trasforma il monolite in sistema modulare sotto `spark/` mantenendo l'entry point come **re-export hub**, senza alcuna modifica logica.

Riferimenti:
- Design: [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md)
- Prospetto integrativo: [REFACTORING-TECHNICAL-BRIEF.md](REFACTORING-TECHNICAL-BRIEF.md)

## 2. Tool diagnostico fisso (baseline)

**Tool scelto:** `scf_verify_workspace`

**Motivazione:**
- Output strutturato e deterministico (`{summary: {...}, files: [...], is_clean: bool}`).
- Attraversa più layer: `core` (hash SHA-256), `manifest` (lettura `.scf-manifest.json`), `workspace` (scan `.github/`).
- Non effettua chiamate di rete (a differenza di `scf_verify_system`, scartato).
- Sempre lanciabile in modo riproducibile, indipendente dal registry remoto.

**Comando esatto (baseline pre-Fase 0):**

```powershell
.venv\Scripts\python.exe -c "import asyncio, json, sys; sys.path.insert(0, '.'); from importlib import import_module; m = import_module('spark-framework-engine'.replace('-', '_'))" 
```

In alternativa, usare il client MCP via `mcp dev spark-framework-engine.py` e invocare il tool. Procedura riproducibile:

```powershell
# Da repo root, con .venv attivo
mcp dev .\spark-framework-engine.py
# Nel inspector: Tools -> scf_verify_workspace -> Run
# Salvare l'output JSON in docs/reports/baseline-verify-workspace.json
```

**Struttura output attesa (campi principali):**

- `summary.tracked_files` — int
- `summary.user_modified` — int
- `summary.missing` — int
- `summary.issue_count` — int
- `summary.is_clean` — bool
- `files[]` — lista record per file tracciato

**Procedura di confronto:** dopo ogni step, rilanciare il tool e fare diff testuale (es. `Compare-Object` PowerShell o `git diff --no-index`) tra baseline e nuovo output. Se differiscono anche per un solo campo, lo step ha introdotto modifiche logiche → applicare rollback.

## 3. Struttura cartelle da creare

```
spark-framework-engine/
├── spark-framework-engine.py    ← entry point + re-export hub durante Fase 0
└── spark/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   ├── models.py
    │   ├── constants.py
    │   └── utils.py
    ├── merge/
    │   ├── __init__.py
    │   ├── engine.py
    │   ├── validators.py
    │   ├── sections.py
    │   └── sessions.py
    ├── manifest/
    │   ├── __init__.py
    │   ├── manager.py
    │   └── snapshots.py
    ├── registry/
    │   ├── __init__.py
    │   ├── client.py
    │   ├── store.py
    │   └── mcp_registry.py
    ├── workspace/
    │   ├── __init__.py
    │   ├── locator.py
    │   ├── inventory.py
    │   └── update_policy.py
    ├── packages/
    │   ├── __init__.py
    │   ├── lifecycle.py
    │   ├── migration.py
    │   └── diff.py
    ├── assets/
    │   ├── __init__.py
    │   └── renderers.py
    └── boot/
        ├── __init__.py
        ├── sequence.py
        └── validation.py
```

## 4. Grafo delle dipendenze (validato sul codice reale)

```
core
 ├─► merge          (merge usa solo core)
 ├─► manifest       (manifest usa core + merge: _strip_package_section riga 1824)
 │   └─► registry   (registry usa core + manifest)
 │       └─► workspace (FrameworkInventory istanzia McpResourceRegistry/PackageResourceStore — riga 1267-1268)
 │           ├─► packages
 │           ├─► assets   (_apply_phase6_assets istanzia PackageResourceStore — riga 3346)
 │           └─► boot     (orchestra tutti)
```

**Anomalie rilevate vs grafo design (Sezione 6):**

| Freccia design | Stato | Note |
|---|---|---|
| `core → merge` | CONFERMATA | nessuna dep interna in merge oltre core |
| `core → manifest` | CONFERMATA | |
| `merge → manifest` | AGGIUNTIVA (mancante nel grafo visivo) | `ManifestManager.purge_owner_entry` chiama `_strip_package_section` riga 1824 |
| `manifest → registry` | CONFERMATA | RegistryClient indipendente, non usa manifest direttamente |
| `registry → workspace` | CONFERMATA | `FrameworkInventory.populate_mcp_registry` istanzia `McpResourceRegistry` e `PackageResourceStore` |
| `workspace → packages` | CONFERMATA | logica packages dentro `SparkFrameworkEngine` orchestra workspace |
| `workspace → assets` | AGGIUNTIVA | assets usa anche `registry` (PackageResourceStore) — freccia mancante: `registry → assets` |
| `assets → boot` | INVERTITA NEL DESIGN VISIVO | nel grafo design `assets └─► boot` indica boot dipende da assets, cosa già coerente con la realtà; il grafo è leggibile correttamente |

**Decisione operativa:** il grafo è coerente per l'ordine di estrazione canonico `core → merge → manifest → registry → workspace → packages → assets → boot`. La dipendenza implicita `merge → manifest` rafforza l'ordine. La dipendenza `registry → assets` è esplicitata in questo piano e segnalata in [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md) Sezione 6 come aggiornamento da effettuare. Confidence: 0.9.

## 5. Sequenza step di estrazione

| # | Modulo | File destinazione | Rischio | TODO operativo |
|---|---|---|---|---|
| 1 | `core` | `spark/core/{models,constants,utils}.py` | BASSO | [fase0-step-01-core.md](todolist/fase0-step-01-core.md) |
| 2 | `merge` | `spark/merge/{engine,validators,sections,sessions}.py` | MEDIO | [fase0-step-02-merge.md](todolist/fase0-step-02-merge.md) |
| 3 | `manifest` | `spark/manifest/{manager,snapshots}.py` | MEDIO | [fase0-step-03-manifest.md](todolist/fase0-step-03-manifest.md) |
| 4 | `registry` | `spark/registry/{client,store,mcp_registry}.py` | MEDIO | [fase0-step-04-registry.md](todolist/fase0-step-04-registry.md) |
| 5 | `workspace` | `spark/workspace/{locator,inventory,update_policy}.py` | ALTO | [fase0-step-05-workspace.md](todolist/fase0-step-05-workspace.md) |
| 6 | `packages` (helpers + MigrationPlanner) | `spark/packages/{migration,diff,lifecycle}.py` | MEDIO | [fase0-step-06-packages.md](todolist/fase0-step-06-packages.md) |
| 7 | `assets` | `spark/assets/renderers.py` | BASSO | [fase0-step-07-assets.md](todolist/fase0-step-07-assets.md) |
| 8 | `boot` (SparkFrameworkEngine + _build_app) | `spark/boot/{sequence,validation}.py` | ALTO | [fase0-step-08-boot.md](todolist/fase0-step-08-boot.md) |
| 9 | cleanup hub | `spark-framework-engine.py` ridotto a re-export + bootstrap | BASSO | [fase0-step-09-cleanup.md](todolist/fase0-step-09-cleanup.md) |

## 6. Dettaglio simboli per step (riferimenti al sorgente reale)

### Step 1 — core
- `core/models.py`: `WorkspaceContext` (riga 75), `FrameworkFile` (84), `MergeConflict` (100), `MergeResult` (111)
- `core/constants.py`: `ENGINE_VERSION` (44), `_CHANGELOGS_SUBDIR`, `_SNAPSHOTS_SUBDIR`, `_MERGE_SESSIONS_SUBDIR`, `_BACKUPS_SUBDIR`, `_USER_PREFS_FILENAME`, `_ALLOWED_UPDATE_MODES` (44–55), `_RESOURCE_TYPES`, `_MANIFEST_FILENAME`, `_BOOTSTRAP_PACKAGE_ID`
- `core/utils.py`: `_utc_now`, `_format_utc_timestamp`, `_parse_utc_timestamp`, `_sha256_text`, `_normalize_string_list`, `_parse_semver_triplet`, `_is_engine_version_compatible`, `parse_markdown_frontmatter`, `_extract_version_from_changelog`, `_is_v3_package`, `_resolve_dependency_update_order`, `_classify_v2_workspace_file`, `_normalize_manifest_relative_path`, `_infer_scf_file_role`

**Re-export aggiunti all'hub:**
```python
from spark.core.models import WorkspaceContext, FrameworkFile, MergeConflict, MergeResult
from spark.core.constants import (
    ENGINE_VERSION, _CHANGELOGS_SUBDIR, _SNAPSHOTS_SUBDIR,
    _MERGE_SESSIONS_SUBDIR, _BACKUPS_SUBDIR, _USER_PREFS_FILENAME,
    _ALLOWED_UPDATE_MODES, _RESOURCE_TYPES, _MANIFEST_FILENAME,
    _BOOTSTRAP_PACKAGE_ID,
)
from spark.core.utils import (  # noqa: F401
    _utc_now, _format_utc_timestamp, _parse_utc_timestamp, _sha256_text,
    _normalize_string_list, _parse_semver_triplet, _is_engine_version_compatible,
    parse_markdown_frontmatter, _extract_version_from_changelog, _is_v3_package,
    _resolve_dependency_update_order, _classify_v2_workspace_file,
    _normalize_manifest_relative_path, _infer_scf_file_role,
)
```

### Step 2 — merge
- `merge/engine.py`: `MergeEngine` (120)
- `merge/validators.py`: `_normalize_merge_text` (814), `_extract_frontmatter_block` (819), `_extract_markdown_headings` (835), `validate_structural` (841), `validate_completeness` (863), `validate_tool_coherence` (876), `run_post_merge_validators` (896), `_resolve_disjoint_line_additions` (944)
- `merge/sections.py`: `_section_markers_for_package` (975), `_scf_section_markers` (992), `_scf_split_frontmatter` (1000), `_scf_extract_merge_priority` (1019), `_scf_iter_section_blocks` (1029), `_scf_render_section` (1079), `_classify_copilot_instructions_format` (1086), `_prepare_copilot_instructions_migration` (1101), `_scf_section_merge_text` (1114), `_scf_strip_section` (1185), `_scf_section_merge` (1201), `_strip_package_section` (1229)
- `merge/sessions.py`: `MergeSessionManager` (2480)

### Step 3 — manifest
- `manifest/manager.py`: `ManifestManager` (1689)
- `manifest/snapshots.py`: `SnapshotManager` (2244), `_normalize_remote_file_record` (2368), `_scf_diff_workspace` (2403), `_scf_backup_workspace` (2446)

### Step 4 — registry
- `registry/client.py`: `RegistryClient` (2682)
- `registry/store.py`: `PackageResourceStore` (3609), `_v3_store_sentinel_file` (3399), `_build_package_raw_url_base` (3409), `_resource_filename_candidates` (3595)
- `registry/mcp_registry.py`: `McpResourceRegistry` (3751)

### Step 5 — workspace
- `workspace/locator.py`: `WorkspaceLocator` (460)
- `workspace/inventory.py`: `FrameworkInventory` (1239), `EngineInventory` (1548), `build_workspace_info` (1629), `_resolve_package_version` (1659), `_get_registry_min_engine_version` (1670), `_build_registry_package_summary` (1677)
- `workspace/update_policy.py`: `_default_update_policy` (316), `_default_update_policy_payload` (328), `_update_policy_path` (333), `_normalize_update_mode` (338), `_validate_update_mode` (343), `_read_update_policy_payload` (384), `_write_update_policy_payload` (444)

### Step 6 — packages
- `packages/migration.py`: `MigrationPlan` (2862), `MigrationPlanner` (2897)
- `packages/diff.py`: helper di basso livello già presenti (riferimento simbolico — molti diff helper sono inner functions di `register_tools`; durante Fase 0 restano lì e si annotano con `# FASE1-RIASSEGNA`)
- `packages/lifecycle.py`: `_install_package_v3_into_store` (3421), `_remove_package_v3_from_store` (3514), `_list_orphan_overrides_for_package` (3540), `_v3_overrides_blocking_update` (3566)

### Step 7 — assets
- `assets/renderers.py`: `_agents_index_section_text` (3113), `_render_agents_md` (3159), `_render_plugin_agents_md` (3191), `_render_clinerules` (3222), `_render_project_profile_template` (3238), `_extract_profile_summary` (3243), `_read_agent_summary` (3268), `_collect_engine_agents` (3286), `_collect_package_agents` (3302), `_apply_phase6_assets` (3320)

### Step 8 — boot
- `boot/sequence.py`: `SparkFrameworkEngine` (3882), `_build_app` (8348), blocco `if __name__ == "__main__"` (8385)
- `boot/validation.py`: validazioni interne ricavate dal corpo di `_build_app` (log inventory, log registry size, log tool count) — in Fase 0 restano nel costruttore; verranno isolate in Fase 2.

### Step 9 — cleanup
- `spark-framework-engine.py` ridotto a:
  - shebang/docstring/import minimali
  - re-export di simboli pubblici per backward compatibility con test e tool esterni
  - `from spark.boot.sequence import _build_app`
  - blocco `if __name__ == "__main__"`

## 7. Gate di verifica per ogni step

Ad ogni step, l'utente deve eseguire i seguenti tre invarianti:

**Invariante 1 — Avvio motore:**
> Lanciare `.venv\Scripts\python.exe spark-framework-engine.py` per 3 secondi (`Ctrl+C` per terminare). Verificare che su `stderr` compaiano solo i log INFO di startup (workspace resolved, inventory, MCP registry, tools registered) e nessuna eccezione non gestita.

**Invariante 2 — Wiring MCP:**
> Lanciare `mcp dev .\spark-framework-engine.py`. Verificare nell'inspector che siano elencati 44 tool e ~17 resource. Selezionare almeno un tool e verificare che la chiamata risponda senza errori di import o attributi.

**Invariante 3 — Output baseline identico:**
> Eseguire `scf_verify_workspace` e confrontare il JSON con la baseline `docs/reports/baseline-verify-workspace.json`. Differenza attesa: zero. Se differiscono, applicare rollback.

## 8. Procedura di rollback applicata allo step

1. `git stash push -m "rollback-step-N"` o `git checkout -- .` per ritornare allo stato pre-step.
2. Rilanciare i tre invarianti del paragrafo 7 per confermare il ripristino.
3. Analizzare il messaggio di import error o il diff di output.
4. Aggiornare il grafo dipendenze nella Sezione 6 di [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md) se è emersa una freccia mancante.
5. Ripetere lo step includendo la dipendenza scoperta.

## 9. Schema commit

**Per estrazione codice (un commit per step):**

```
refactor(<modulo>): estrai <ClasseOFunzione> — nessuna modifica logica

Sposta <classi/funzioni> da spark-framework-engine.py a spark/<modulo>/<file>.py.
Aggiunti re-export nell'hub per compatibilità.
Invarianti verificati: avvio motore, wiring MCP, output scf_verify_workspace identico alla baseline.
```

**Per aggiornamento documentazione (commit separato):**

```
docs(design): aggiorna grafo — dipendenza <A→B> rilevata step <N>

Aggiorna REFACTORING-DESIGN.md Sezione 6 con la dipendenza esplicita
<modulo-A> → <modulo-B> emersa durante l'estrazione dello step <N>.
```

**Vincolo:** mai mescolare estrazione e modifica logica nello stesso commit.

## 10. Vincoli ricorrenti su tutti gli step

- Mai scrivere su `stdout`. Logging esclusivo su `sys.stderr` o file.
- Errori MCP restituiti come dict strutturato, mai eccezione nuda.
- Re-export aggiunto **prima** della rimozione del codice originale dall'hub.
- Nessuna ri-assegnazione di responsabilità durante la Fase 0: codice fuori posto va annotato con `# FASE1-RIASSEGNA: <motivo>` e lasciato dove si trova.
- `packages/` non assorbe parsing/hashing/validazione di basso livello.
