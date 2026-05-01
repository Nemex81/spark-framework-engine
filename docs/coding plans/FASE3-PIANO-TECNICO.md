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
