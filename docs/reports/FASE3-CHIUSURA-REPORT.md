---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Report Chiusura Fase 3 — Separazione Runtime
generated_by: spark-engine-maintainer
---

# SPARK — Report Chiusura Fase 3: Separazione Runtime

## Dati sessione

- Data: 2026-05-01
- Commit SHA: 950c81a77d04a8b92517c5499d92431ee04514b0
- Invariante finale: 0 failed / 282 passed / 8 skipped (confermato)
- Engine startup: Tools registered: 44 total

## Step implementati

| Step | Descrizione | File | Stato |
|------|-------------|------|-------|
| 3.0 | Aggiunto `list_active()` in `MergeSessionManager` per guardia migrazione | `spark/merge/sessions.py` | COMPLETATO |
| 3.1 | Costanti subdir senza prefisso `runtime/`; env `SPARK_RUNTIME_DIR`; `_USER_PREFS_FILENAME` | `spark/core/constants.py` | COMPLETATO |
| 3.2 | `resolve_runtime_dir(engine_root, workspace_root) -> Path` con override env | `spark/boot/validation.py` | COMPLETATO |
| 3.3 | `_scf_backup_workspace()` accetta `backup_root: Path \| None` opzionale | `spark/manifest/snapshots.py` | COMPLETATO |
| 3.4 | `_migrate_runtime_to_engine_dir()` + `_build_app()` integra `runtime_dir` | `spark/boot/sequence.py` | COMPLETATO |
| 3.5 | `SparkFrameworkEngine.__init__` accetta `runtime_dir=None`; orchestrator-state resta in `.github/runtime/` | `spark/boot/engine.py` + `spark/boot/__init__.py` | COMPLETATO |
| 3.6 | Import `resolve_runtime_dir` + helper `_runtime_dir` + path legacy sostituiti in 7 test file | `tests/test_*.py` (×7) | COMPLETATO |

## Prerequisito validate_workspace_context()

Il piano Fase 3 sezione 5 dichiarava: *"`validate_workspace_context()` esiste e restituisce
`runtime_dir` corretto"*. La funzione effettiva implementata si chiama `resolve_runtime_dir()`,
non `validate_workspace_context()`. Dettagli:

- **Nome effettivo:** `resolve_runtime_dir(engine_root: Path, workspace_root: Path) -> Path`
- **File:** `spark/boot/validation.py`
- **Firma:** restituisce il Path della dir runtime (non la crea — il caller è responsabile)
- **Override env:** `SPARK_RUNTIME_DIR` — se impostato, ha priorità sull'hash deterministico
- **Re-export:** `spark/boot/__init__.py` e `spark-framework-engine.py`

## Migrazione runtime

- **Funzione:** `_migrate_runtime_to_engine_dir(github_root, runtime_dir)` in `spark/boot/sequence.py`
- **Marker:** `.runtime-migrated` in `runtime_dir/` — idempotenza garantita
- **Sessioni attive:** `MergeSessionManager.list_active()` — se > 0, migrazione saltata (INVARIANTE-7)
- **Sorgenti migrate:** `runtime/snapshots`, `runtime/merge-sessions`, `runtime/backups`
- **Prefs utente:** spostato da `runtime/spark-user-prefs.json` → `.github/user-prefs.json` (è preferenza utente, non runtime)

## Drift risolti

| ID | Sezione piano | Risoluzione |
|----|---------------|-------------|
| D1 | Sezione 3: `spark/workspace/policy.py` → `update_policy.py` | Rinomina completata in Fase 1 Step 1.1 — drift già risolto all'ingresso di Fase 3 [950c81a] |
| D2 | Sezione 3: `SnapshotManager` e `MergeSessionManager` già in package separati (Fase 0) | Confermato — modifiche applicate ai file esistenti correttamente [950c81a] |
| D3 | Sezione 5: funzione `validate_workspace_context()` dichiarata ma non esistente | Funzione implementata con nome `resolve_runtime_dir()` — comportamento equivalente [950c81a] |
| D4 | Test helper `_runtime_dir`: script fix inserisce chiamate prima del metodo | Fix manuale con `replace_string_in_file` per 3 file mancanti [950c81a] |

## Note e correzioni strategia

CORREZIONE [1] — `list_active()` in `MergeSessionManager` non previsto nel piano originale.
Incoerenza rilevata: il piano descriveva la guardia migrazione ma non dichiarava il metodo da aggiungere.
Modifica alla strategia: aggiunto Step 3.0 per implementare `list_active()` prima di ogni altro step.
Motivazione: la guardia migrazione non funzionava senza questo metodo.
Impatto sui caller: MergeSessionManager ora espone un metodo pubblico in più.

CORREZIONE [2] — `_sha256_text` non presente in `spark/core/utils.py`.
Incoerenza rilevata: il piano assumeva l'esistenza di questo helper.
Modifica alla strategia: helper implementato direttamente in `spark/boot/validation.py` via `spark/core/utils.py`.
Motivazione: nessuna dipendenza aggiuntiva necessaria.
Impatto sui caller: nessuno.

## Apertura Fase 4

AUTORIZZATA
