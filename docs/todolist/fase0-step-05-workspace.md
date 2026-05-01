---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 05 — Estrazione workspace/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 05 — `spark/workspace/`

## Prerequisiti

- Step 01, 02, 03, 04 completati.
- Verificato sul codice reale (riga 1267-1268) che `FrameworkInventory` istanzia `McpResourceRegistry` e `PackageResourceStore`. Pertanto `registry/` deve essere già estratto.

## Azioni atomiche

1. Creare `spark/workspace/__init__.py` vuoto.
2. Creare `spark/workspace/locator.py` con `WorkspaceLocator`.
   - Origine: riga 460 fino a 657.
   - Import richiesti: `from spark.core.models import WorkspaceContext`.
3. Creare `spark/workspace/inventory.py` con `FrameworkInventory`, `EngineInventory` e gli helper relativi.
   - Simboli: `FrameworkInventory` (1239), `EngineInventory` (1548), `build_workspace_info` (1629), `_resolve_package_version` (1659), `_get_registry_min_engine_version` (1670), `_build_registry_package_summary` (1677).
   - Import richiesti: `from spark.core.models import WorkspaceContext, FrameworkFile`, `from spark.core.constants import _RESOURCE_TYPES`, `from spark.core.utils import parse_markdown_frontmatter, _normalize_string_list`, `from spark.registry.store import PackageResourceStore`, `from spark.registry.mcp_registry import McpResourceRegistry`.
4. Creare `spark/workspace/update_policy.py` con le funzioni di policy aggiornamento.
   - Simboli: `_default_update_policy` (316), `_default_update_policy_payload` (328), `_update_policy_path` (333), `_normalize_update_mode` (338), `_validate_update_mode` (343), `_read_update_policy_payload` (384), `_write_update_policy_payload` (444).
   - Import richiesti: `from spark.core.constants import _USER_PREFS_FILENAME, _ALLOWED_UPDATE_MODES`, `from spark.core.utils import _format_utc_timestamp, _utc_now`.
5. Aggiungere re-export nell'hub:

   ```python
   from spark.workspace.locator import WorkspaceLocator  # noqa: F401
   from spark.workspace.inventory import (  # noqa: F401
       FrameworkInventory, EngineInventory, build_workspace_info,
       _resolve_package_version, _get_registry_min_engine_version,
       _build_registry_package_summary,
   )
   from spark.workspace.update_policy import (  # noqa: F401
       _default_update_policy, _default_update_policy_payload, _update_policy_path,
       _normalize_update_mode, _validate_update_mode,
       _read_update_policy_payload, _write_update_policy_payload,
   )
   ```
6. Rimuovere le definizioni dall'hub.
7. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore con log `Workspace resolved`, `Framework inventory: N agents...`, `MCP resource registry: N URI registrati`.

**Invariante 2:** `mcp dev`. `scf_get_workspace_info`, `scf_get_update_policy`, `scf_set_update_policy` rispondono.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-05"`. Step ad alto rischio: `FrameworkInventory.populate_mcp_registry` istanzia direttamente `McpResourceRegistry` e `PackageResourceStore`. Se i re-export di `registry/` sono incompleti, l'import circolare emergerà come `ImportError`. Verificare ordine import in `workspace/inventory.py`.

## Schema commit

```
refactor(workspace): estrai WorkspaceLocator, FrameworkInventory, update_policy — nessuna modifica logica

Sposta WorkspaceLocator, FrameworkInventory, EngineInventory, build_workspace_info
e le funzioni di update_policy da spark-framework-engine.py
a spark/workspace/{locator,inventory,update_policy}.py.
Conferma dipendenza registry → workspace (FrameworkInventory usa McpResourceRegistry
e PackageResourceStore).
Invarianti verificati.
```

---

## Nota post-completamento (2026-05-01)

Lo step è stato completato con deviazioni significative rispetto al piano:

- **`FrameworkInventory` ed `EngineInventory` sono in `spark/inventory/`**, non in
  `spark/workspace/inventory.py`. Copilot ha estratto un package separato
  `spark/inventory/{framework.py, engine.py}` invece di creare `workspace/inventory.py`.
  Deviazione documentata in `docs/todo.md`. Import corretto:
  `from spark.inventory import FrameworkInventory, EngineInventory`.
- **`spark/workspace/policy.py`** invece di `update_policy.py`.
  Step 1.1 di Fase 1 prevede la rinomina. Import attuale:
  `from spark.workspace.policy import ...`.
- **`MigrationPlan` e `MigrationPlanner`** sono finiti in `spark/workspace/migration.py`
  invece di `spark/packages/migration.py` come previsto dallo step successivo (06).
