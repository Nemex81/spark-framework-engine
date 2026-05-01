---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Chiusura Fase 3 — Separazione runtime
generated_by: spark-engine-maintainer
---

# Chiusura Fase 3 — Separazione runtime

**Data chiusura:** 2026-05-08
**Versione engine:** 3.1.0
**Baseline test finale:** 0 failed / 282 passed / 8 skipped / 42 warnings

---

## Obiettivo conseguito

I file di stato temporaneo (snapshot, sessioni di merge, backup, prefs utente) sono
stati spostati da `.github/runtime/` a una directory di runtime dedicata
`<engine_root>/runtime/<workspace_hash_12>/`, isolata per workspace.
Il workspace utente non contiene più file di stato temporaneo.

---

## Step implementati

| Step | Modulo | Operazione |
|------|--------|-----------|
| 3.0 | `spark/merge/sessions.py` | Aggiunto `list_active()` (guardia migrazione idempotente) |
| 3.1 | `spark/core/constants.py` | Costanti subdir senza prefisso `runtime/`; env `SPARK_RUNTIME_DIR`; filename `user-prefs.json` |
| 3.2 | `spark/boot/validation.py` | `resolve_runtime_dir(engine_root, workspace_root) -> Path` con override via env |
| 3.3 | `spark/manifest/snapshots.py` | `_scf_backup_workspace()` accetta `backup_root: Path | None` opzionale |
| 3.4 | `spark/boot/sequence.py` | `_migrate_runtime_to_engine_dir()` con idempotenza `.runtime-migrated`; `_build_app()` integra `runtime_dir` |
| 3.5 | `spark/boot/engine.py` | `SparkFrameworkEngine.__init__` accetta `runtime_dir=None`; fallback a `resolve_runtime_dir`; orchestrator-state resta in `.github/runtime/` |
| 3.6 | 7 test file | Import `resolve_runtime_dir` + helper `_runtime_dir` + path legacy sostituiti |

---

## Invarianti post-Fase 3

- **`orchestrator-state.json`** resta a `.github/runtime/orchestrator-state.json` — non migrato.
- **`user-prefs.json`** è ora a `.github/user-prefs.json` (no prefisso `runtime/`).
- **Runtime formula:** `engine_root / "runtime" / sha256(workspace_root.absolute())[:12]`
- **Override env:** `SPARK_RUNTIME_DIR` permette path custom (utile per test e CI).
- **Migrazione automatica:** se esiste `.github/runtime/` con file legacy, vengono spostati alla prima accensione. Marker idempotente: `.github/runtime/.runtime-migrated`.

---

## Correzioni DRIFT

1. `_sha256_text` non in `spark/core/utils.py` → helper locale in `validation.py`.
2. `EngineInventory` non necessario in `validation.py` → import rimosso.
3. `list_active()` aggiunto in Step 3.0 (non previsto nel piano originale) per guardia migrazione.
4. Fix script `_fix_tests2.py`: il guard `"_runtime_dir" not in t` era falso perché le chiamate `self._runtime_dir(...)` erano già nel testo dopo il replace dei path. Il metodo `_runtime_dir` NON è stato inserito in 3 file. Corretto manualmente con `replace_string_in_file`.
5. `test_multi_owner_policy.py`: `def _registry_package` consumato dall'oldString durante il replace. Ripristinato.
6. `test_bootstrap_workspace.py` lines 312/330: riferimenti a vecchio prefs path in metodi `@unittest.skip`. Confermati SKIPPED — no fix necessario.

---

## File toccati

### Sorgenti (8 file)

- `spark/merge/sessions.py` — `list_active()`
- `spark/core/constants.py` — costanti subdir + env + filename
- `spark/boot/validation.py` — `resolve_runtime_dir()`
- `spark/manifest/snapshots.py` — backup_root opzionale
- `spark/boot/sequence.py` — migrazione + build_app
- `spark/boot/engine.py` — runtime_dir in `__init__`
- `spark/boot/__init__.py` — re-export `resolve_runtime_dir`
- `spark-framework-engine.py` — re-export `resolve_runtime_dir`

### Test (7 file)

- `tests/test_bootstrap_workspace.py` — snapshot path in idempotent test
- `tests/test_merge_integration.py` — 6 snapshot + 2 session_path
- `tests/test_merge_session.py` — 5 merge-sessions + 1 snapshot
- `tests/test_multi_owner_policy.py` — 2 snapshot
- `tests/test_package_installation_policies.py` — 2 snapshot
- `tests/test_update_planner.py` — 1 snapshot
- `tests/test_update_policy.py` — 3 prefs_path

### Documentazione (3 file)

- `docs/todo.md` — Fase 3 COMPLETATA, apertura Fase 4
- `docs/coding plans/FASE3-PIANO-TECNICO.md` — sezione CHIUSURA aggiunta
- `docs/archivio/FASE3-CHIUSURA-REPORT.md` — questo file

---

## Pattern test introdotto (invariante per Fase 4+)

Ogni test file di integrazione che usa path runtime deve seguire:

```python
# Import (accanto agli altri import _module.*)
resolve_runtime_dir: Any = _module.resolve_runtime_dir

# Helper nel corpo della classe di test
def _runtime_dir(self, workspace_root: Path) -> Path:
    """Compute the engine-local runtime dir for this workspace (mirrors sequence.py)."""
    return resolve_runtime_dir(workspace_root / "spark-framework-engine", workspace_root)

# Uso nei test
snapshots = SnapshotManager(self._runtime_dir(workspace_root) / "snapshots")
session_mgr = MergeSessionManager(self._runtime_dir(workspace_root) / "merge-sessions")
```

**Regola:** NON passare `runtime_dir` esplicito a `SparkFrameworkEngine` nei test.
Il motore lo calcola autonomamente tramite `context.engine_root`. Il `_runtime_dir` helper
nel test usa la stessa formula, garantendo che i path coincidano.
