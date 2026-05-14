> **STATO: COMPLETATO** — Archiviato il 2026-05-14 (ENGINE_VERSION 3.6.0).
> Documento di sola lettura. Non modificare.

***

# Refactoring Phase 1-2 — engine.py Modularization

## Obiettivo

Ridurre la dimensione di `spark/boot/engine.py` estraendo due insiemi
di funzioni/metodi in moduli dedicati, migliorando la manutenibilità
senza modificare nessun comportamento pubblico.

---

## Task 1 — `spark/boot/install_helpers.py`

### Cosa è stato estratto

21 funzioni helper dalla closure `register_tools()` in `engine.py`:

**Helper pure (aliasate direttamente):**
- `_build_install_result`, `_build_diff_summary`, `_resolve_effective_update_mode`
- `_normalize_file_policies`, `_validate_extend_policy_target`
- `_summarize_available_updates`, `_read_text_if_possible`
- `_supports_stateful_merge`, `_build_session_entry`, `_replace_session_entry`
- `_find_session_entry`, `_count_remaining_conflicts`, `_resolve_conflict_automatically`

**Helper con capture di closure (chiamate via shim):**
- `_save_snapshots` (cattura `snapshots`)
- `_render_marker_text` (cattura `merge_engine`)
- `_propose_conflict_resolution` (cattura `sessions`)
- `_build_remote_file_records` (cattura `registry`)
- `_build_update_flow_payload` (cattura `inventory`)
- `_detect_workspace_migration_state` (cattura `github_root`, `manifest`)
- `_get_package_install_context` (cattura `registry`, `manifest`)
- `_classify_install_files` (cattura `manifest`, `workspace_root`, `snapshots`)

### Strategia shim

Le funzioni con captures non possono essere pure. In `register_tools()`:
```python
from spark.boot import install_helpers as _ih
# Alias puri:
_build_install_result = _ih._build_install_result
# Shim con inject:
def _save_snapshots(package_id, files):
    return _ih._save_snapshots(package_id, files, snapshots)
```

---

## Task 2 — `spark/boot/lifecycle.py`

### Cosa è stato estratto

8 metodi v3 lifecycle dalla classe `SparkFrameworkEngine`:

| Metodo | Tipo |
|--------|------|
| `_v3_runtime_state` | sync |
| `_is_github_write_authorized_v3` | sync |
| `_v3_repopulate_registry` | sync |
| `_install_workspace_files_v3` | sync |
| `_remove_workspace_files_v3` | sync |
| `_install_package_v3` | async |
| `_remove_package_v3` | async |
| `_update_package_v3` | async |

### Strategia Mixin

```python
class _V3LifecycleMixin:
    """Mixin con i metodi v3 lifecycle per SparkFrameworkEngine."""
    ...

class SparkFrameworkEngine(_V3LifecycleMixin):
    ...
```

### Nota: circular import

`lifecycle.py` non può importare da `spark.boot.engine`.
`_install_workspace_files_v3` usa `WorkspaceWriteGateway(...).write(...)` 
direttamente invece di `_gateway_write_text(...)` (closure di engine.py).

---

## Metriche

| File | Righe PRIMA | Righe DOPO |
|------|------------|-----------|
| `spark/boot/engine.py` | ~5169 | 4002 |
| `spark/boot/install_helpers.py` | — (nuovo) | 984 |
| `spark/boot/lifecycle.py` | — (nuovo) | 580 |

**Riduzione engine.py:** −1167 righe (−22.6%)

---

## Validazione

Suite completa non-live:

```
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

**Risultato:** 313 passed, 9 skipped, 42 warnings

Baseline pre-refactoring Task 1: **313 passed, 9 skipped, 42 warnings**  
Nessuna regressione introdotta.

---

## Vincoli rispettati

- Tool handler `@_register_tool(...)` restano dentro `register_tools()` (closure FastMCP).
- Resource handler `@_register_resource(...)` restano dentro `register_resources()`.
- Nessuna modifica a signature pubbliche di `SparkFrameworkEngine`.
- Nessun `print()` introdotto — logging esclusivamente su `_log` (stderr).
- `lifecycle.py` non importa da `spark.boot.engine` (prevenzione import circolare).
