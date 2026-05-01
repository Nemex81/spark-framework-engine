---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Piano Tecnico Fase 3 — Separazione runtime
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Piano Tecnico Fase 3 — Separazione runtime

## 1. Obiettivo

Spostare tutti i file di stato temporaneo (snapshot, sessioni di merge, backup, prefs utente) in una directory di runtime dedicata fuori dal workspace utente. Il workspace contiene solo file framework SCF persistenti.

## 2. Criterio di completamento

- Il workspace utente non contiene più `runtime/snapshots/`, `runtime/merge-sessions/`, `runtime/backups/`, `runtime/spark-user-prefs.json`.
- I path runtime sono configurabili tramite costante in `spark/core/constants.py`.
- Migrazione automatica dei file runtime esistenti dalla vecchia posizione alla nuova al primo avvio post-aggiornamento.
- Output `scf_verify_workspace` segnala la migrazione runtime come `migration_runtime_v3.1`.

## 3. File coinvolti

- `spark/core/constants.py` — aggiunta `RUNTIME_DIR` come Path configurabile via env `SPARK_RUNTIME_DIR`.
- `spark/manifest/snapshots.py` — `SnapshotManager` accetta `runtime_dir` invece di calcolarlo da `github_root`.
- `spark/merge/sessions.py` — `MergeSessionManager` accetta `runtime_dir` esplicito.
- `spark/workspace/update_policy.py` — `_USER_PREFS_FILENAME` rimane in workspace (è preferenza utente, non runtime), ma viene rinominato `user-prefs.json` senza prefisso `runtime/`.
- `spark/boot/sequence.py` — risolve `RUNTIME_DIR` ed esegue la migrazione runtime se necessario.

## 4. Operazioni specifiche

1. Definire `RUNTIME_DIR` con default a `<engine_root>/runtime/<workspace_hash>/` per isolare workspace multipli.
2. Aggiornare le costanti `_SNAPSHOTS_SUBDIR`, `_MERGE_SESSIONS_SUBDIR`, `_BACKUPS_SUBDIR` per essere relative a `RUNTIME_DIR`.
3. Implementare `migrate_runtime_to_engine_dir()` in `spark/boot/sequence.py` che sposta atomicamente i file esistenti e crea un marker `.runtime-migrated`.
4. Aggiornare i test che costruiscono path attesi sotto `.github/runtime/`.

## 5. Dipendenze dalla fase precedente

- Fase 2 chiusa: boot deterministico abilitato in modalità strict.
- `validate_workspace_context()` esiste e restituisce `runtime_dir` corretto.

## 6. Rischi specifici

- **Migrazione idempotente non triviale.** Se l'utente lancia il motore mentre una sessione di merge è attiva, il file potrebbe essere in uso. Mitigazione: la migrazione runtime avviene solo se non ci sono sessioni attive (`MergeSessionManager.list_active() == []`).
- **Workspace multipli che condividono engine.** Mitigazione: il path runtime include un hash deterministico del `workspace_root.absolute()`.

---

## DRIFT — Note di allineamento post-Fase 0/1 (2026-05-01)

Aggiornamenti alla struttura reale rispetto a quanto scritto sopra:

- **Sezione 3 — `spark/workspace/update_policy.py`:** il file si chiama
  `spark/workspace/policy.py`. Step 1.1 di Fase 1 prevede la rinomina a
  `update_policy.py`. Se non eseguita prima di Fase 3, aggiornare il
  riferimento. **[RISOLTO commit 950c81a — rinomina completata in Fase 1 Step 1.1]**
- **`SnapshotManager` e `MergeSessionManager`:** entrambi già in
  `spark/manifest/snapshots.py` e `spark/merge/sessions.py` rispettivamente
  (estratti in Fase 0). Le modifiche ai path runtime si applicano a questi
  file esistenti, non a nuovi file da creare. **[RISOLTO commit 950c81a]**

---

## CHIUSURA FASE 3 (2026-05-08)

**Stato:** COMPLETATA — suite 0 failed / 282 passed / 8 skipped.

### Step implementati

| Step | Modulo | Operazione | Stato |
|------|--------|-----------|-------|
| 3.0 | `spark/merge/sessions.py` | Aggiunto `list_active()` per guardia migrazione | ✅ |
| 3.1 | `spark/core/constants.py` | Costanti subdir senza prefisso `runtime/`; `_SPARK_RUNTIME_DIR_ENV`; `_USER_PREFS_FILENAME` | ✅ |
| 3.2 | `spark/boot/validation.py` | `resolve_runtime_dir(engine_root, workspace_root)` con override env | ✅ |
| 3.3 | `spark/manifest/snapshots.py` | `_scf_backup_workspace()` accetta `backup_root` opzionale | ✅ |
| 3.4 | `spark/boot/sequence.py` | `_migrate_runtime_to_engine_dir()` + `_build_app()` integra runtime_dir | ✅ |
| 3.5 | `spark/boot/engine.py` | `__init__` accetta `runtime_dir=None`; orchestrator-state resta in `.github/runtime/` | ✅ |
| 3.6 | test files (7 file) | Import `resolve_runtime_dir` + helper `_runtime_dir` + path aggiornati | ✅ |

### Correzioni DRIFT introdotte durante implementazione

1. `_sha256_text` non era in `spark/core/utils.py` → aggiunto helper in `validation.py` locale.
2. `EngineInventory` non necessario in `validation.py` → import rimosso.
3. `list_active()` in `MergeSessionManager` non era previsto nel piano → aggiunto in Step 3.0 per guardia migrazione.
4. `_fix_tests2.py` ha rimpiazzato i path prima di inserire il metodo `_runtime_dir` → la stringa `_runtime_dir` era già presente nel testo (negli usi), bloccando il guard `"_runtime_dir" not in t`. Risolto manualmente con `replace_string_in_file` per i 3 file mancanti.
5. `test_multi_owner_policy.py`: durante aggiunta `_runtime_dir`, `def _registry_package` fu consumato dall'oldString. Ripristinato.
6. `test_bootstrap_workspace.py` lines 312/330: riferimenti a vecchio prefs path in metodi `@unittest.skip` — SKIPPED, no fix needed.

### File toccati

**Sorgenti:**
- `spark/merge/sessions.py`
- `spark/core/constants.py`
- `spark/boot/validation.py`
- `spark/manifest/snapshots.py`
- `spark/boot/sequence.py`
- `spark/boot/engine.py`
- `spark/boot/__init__.py`
- `spark-framework-engine.py` (re-export `resolve_runtime_dir`)

**Test:**
- `tests/test_bootstrap_workspace.py`
- `tests/test_merge_integration.py`
- `tests/test_merge_session.py`
- `tests/test_multi_owner_policy.py`
- `tests/test_package_installation_policies.py`
- `tests/test_update_planner.py`
- `tests/test_update_policy.py`

