---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 08 — Estrazione boot/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 08 — `spark/boot/`

## Prerequisiti

- Step 01–07 completati.

## Nota di scope

Lo step 08 è il più rischioso. La classe `SparkFrameworkEngine` (riga 3882) contiene oltre 4400 righe di tool registration con inner async functions. La Fase 0 sposta la classe **alla lettera** in `spark/boot/sequence.py`. Nessuna inner function viene estratta. Le ri-assegnazioni avverranno in Fase 1.

## Azioni atomiche

1. Creare `spark/boot/__init__.py` vuoto.
2. Creare `spark/boot/sequence.py` con la classe `SparkFrameworkEngine` e la funzione `_build_app`.
   - Origine: `SparkFrameworkEngine` riga 3882–8347, `_build_app` riga 8348–8383.
   - Import richiesti (lista esaustiva, calcolata sui simboli usati nella classe):
     - `from spark.core.models import WorkspaceContext, FrameworkFile, MergeConflict, MergeResult`
     - `from spark.core.constants import (ENGINE_VERSION, _MANIFEST_FILENAME, _BOOTSTRAP_PACKAGE_ID, _RESOURCE_TYPES, _CHANGELOGS_SUBDIR, _SNAPSHOTS_SUBDIR, _MERGE_SESSIONS_SUBDIR, _BACKUPS_SUBDIR, _USER_PREFS_FILENAME, _ALLOWED_UPDATE_MODES)`
     - `from spark.core.utils import (_utc_now, _format_utc_timestamp, _parse_utc_timestamp, _sha256_text, _normalize_string_list, _parse_semver_triplet, _is_engine_version_compatible, parse_markdown_frontmatter, _extract_version_from_changelog, _is_v3_package, _resolve_dependency_update_order, _classify_v2_workspace_file, _normalize_manifest_relative_path, _infer_scf_file_role)`
     - `from spark.merge.engine import MergeEngine`
     - `from spark.merge.validators import run_post_merge_validators`
     - `from spark.merge.sections import _scf_section_merge, _scf_section_merge_text, _scf_strip_section, _strip_package_section, _classify_copilot_instructions_format, _prepare_copilot_instructions_migration`
     - `from spark.merge.sessions import MergeSessionManager`
     - `from spark.manifest.manager import ManifestManager`
     - `from spark.manifest.snapshots import SnapshotManager, _scf_diff_workspace, _scf_backup_workspace`
     - `from spark.registry.client import RegistryClient`
     - `from spark.registry.store import PackageResourceStore, _v3_store_sentinel_file, _build_package_raw_url_base`
     - `from spark.registry.mcp_registry import McpResourceRegistry`
     - `from spark.workspace.locator import WorkspaceLocator`
     - `from spark.workspace.inventory import FrameworkInventory, EngineInventory, build_workspace_info, _resolve_package_version, _get_registry_min_engine_version, _build_registry_package_summary`
     - `from spark.workspace.update_policy import _read_update_policy_payload, _write_update_policy_payload, _update_policy_path, _validate_update_mode, _default_update_policy_payload`
     - `from spark.packages.migration import MigrationPlan, MigrationPlanner`
     - `from spark.packages.lifecycle import _install_package_v3_into_store, _remove_package_v3_from_store, _list_orphan_overrides_for_package, _v3_overrides_blocking_update`
     - `from spark.assets.renderers import _apply_phase6_assets, _render_agents_md, _render_plugin_agents_md, _render_clinerules`
3. Creare `spark/boot/validation.py` come placeholder con docstring "Boot validation — popolato in Fase 2".
4. Aggiornare l'hub `spark-framework-engine.py`:

   ```python
   from spark.boot.sequence import SparkFrameworkEngine, _build_app  # noqa: F401
   ```
5. Rimuovere dall'hub la classe `SparkFrameworkEngine` e la funzione `_build_app`.
6. Mantenere nell'hub solo `if __name__ == "__main__": _build_app().run(transport="stdio")`.
7. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore con log completi (workspace, inventory, MCP registry, `Tools registered: 40 total`).

**Invariante 2:** `mcp dev` mostra esattamente 44 tool registrati e tutti i tool rispondono. Verificare almeno: `scf_verify_workspace`, `scf_list_installed_packages`, `scf_get_workspace_info`, `scf_get_runtime_state`, `scf_bootstrap_workspace` (su workspace già bootstrappato).

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-08"`. Step ad altissimo rischio. Probabili cause di failure:
- Import circolare scoperto: una inner function di `register_tools` usa un simbolo dell'hub che era ancora lì. Verificare con `python -c "import spark.boot.sequence"` per identificare l'errore.
- Riferimento a globals dell'hub originale (es. `_log`): in tal caso aggiungere `from logging import getLogger; _log = getLogger("spark-framework-engine")` in `boot/sequence.py`.

## Schema commit

```
refactor(boot): estrai SparkFrameworkEngine e _build_app — nessuna modifica logica

Sposta la classe SparkFrameworkEngine (4466 righe) e la funzione _build_app
da spark-framework-engine.py a spark/boot/sequence.py.
L'entry point conserva solo il blocco if __name__ e i re-export degli step
precedenti.
Invarianti verificati: 44 tool registrati, scf_verify_workspace identico
alla baseline.
```
