# Fase 0 — scf_migrate_workspace
# Dipende da: nessuna
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_migrate_workspace.py

## Prerequisiti

- [ ] VALIDATION-REPORT.md presente con verdetto PASS
- [ ] Engine v2.4.0 con suite test verde
  (`.venv\Scripts\python.exe -m pytest -q`)
- [ ] `SnapshotManager` operativo (riga 1839 di
  `spark-framework-engine.py`)

## Task

- [ ] 0.1 Definire helper `_classify_v2_workspace_file(path)` -> str
      File: `spark-framework-engine.py`
      Punto di inserimento: prima della classe `SparkFrameworkEngine`
      Snippet di riferimento:
      `def _classify_v2_workspace_file(path: Path) -> str:`
      Categorie: "keep" | "move_to_override" | "delete" | "untouched".
      Mapping da §14.1 del design.

- [ ] 0.2 Implementare `MigrationPlanner` interno
      File: `spark-framework-engine.py`
      Metodi: `analyze(workspace) -> dict`,
              `apply(workspace, plan, snapshot_id) -> dict`.
      Usa `SnapshotManager` per registrare snapshot pre-esecuzione.

- [ ] 0.3 Registrare tool `scf_migrate_workspace`
      File: `spark-framework-engine.py`
      Punto di inserimento: dopo `scf_bootstrap_workspace`
      (attualmente alla riga 5075).
      Signature:
      `async def scf_migrate_workspace(dry_run: bool = True,
                                       force: bool = False) -> dict`.

- [ ] 0.4 Aggiornare contatore tool registrati nel log boot
      File: `spark-framework-engine.py`
      Cercare stringa "Tools registered" e aggiornare a 36
      (35 esistenti + scf_migrate_workspace).

- [ ] 0.5 Test: dry_run su workspace simulato
      File: `tests/test_migrate_workspace.py`
      Usa `tmp_path` di pytest, crea struttura v2.x sintetica.

- [ ] 0.6 Test: esecuzione reale con rollback su errore iniettato
      File: `tests/test_migrate_workspace.py`
      Mock di `Path.replace` che lancia OSError, verifica
      `SnapshotManager.rollback()` chiamato.

- [ ] 0.7 Test: idempotenza su workspace già migrato
      File: `tests/test_migrate_workspace.py`
      Migrazione ripetuta → migration_plan vuoto, no side-effect.

## Test di accettazione

- [ ] Workspace simulato con `agents/code-Agent-Code.md` modificato
      → finisce in `.github/overrides/agents/code-Agent-Code.md`.
- [ ] Workspace simulato con `AGENTS.md` non modificato (SHA matches
      pacchetto) → eliminato.
- [ ] `.scf-registry-cache.json` → spostato in
      `engine_dir/cache/registry-cache.json`.
- [ ] `dry_run=True` non scrive nulla su filesystem.
- [ ] `dry_run=False` con error injection → rollback completo.
- [ ] Tool count nel log boot aggiornato.

## Note tecniche

- Edge case: workspace senza `.github/` → migration_plan vuoto,
  ritornare immediatamente.
- Edge case: `engine_dir/cache/` non scrivibile → fallback a
  `%APPDATA%\spark-engine\cache\`.
- File utente fuori dal manifest pacchetto: NEVER toccare. Logga
  `[SPARK-ENGINE][INFO] File non gestito preservato: {path}`.
- Il tool va backportato come patch su engine v2.4.x se possibile,
  altrimenti utenti devono prima aggiornare a engine v3.0 e poi
  migrare.
