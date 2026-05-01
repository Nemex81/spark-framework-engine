---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 03 — Estrazione manifest/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 03 — `spark/manifest/`

## Prerequisiti

- Step 01 e 02 completati.

## Azioni atomiche

1. Creare `spark/manifest/__init__.py` vuoto.
2. Creare `spark/manifest/manager.py` con la classe `ManifestManager`.
   - Origine: riga 1689 fino a fine classe (~2243).
   - Import richiesti: `from spark.core.constants import _MANIFEST_FILENAME`, `from spark.core.utils import _sha256_text, _utc_now, _format_utc_timestamp, _normalize_manifest_relative_path, _infer_scf_file_role`, `from spark.merge.sections import _strip_package_section`.
3. Creare `spark/manifest/snapshots.py` con `SnapshotManager` e gli helper diff/backup.
   - Simboli: `SnapshotManager` (2244), `_normalize_remote_file_record` (2368), `_scf_diff_workspace` (2403), `_scf_backup_workspace` (2446).
   - Import richiesti: `from spark.core.constants import _SNAPSHOTS_SUBDIR, _BACKUPS_SUBDIR`, `from spark.core.utils import _sha256_text`, `from spark.manifest.manager import ManifestManager`.
4. Aggiungere re-export nell'hub:

   ```python
   from spark.manifest.manager import ManifestManager  # noqa: F401
   from spark.manifest.snapshots import (  # noqa: F401
       SnapshotManager, _scf_diff_workspace, _scf_backup_workspace,
   )
   ```
5. Rimuovere le definizioni dall'hub.
6. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore.

**Invariante 2:** `mcp dev` mostra 44 tool. Verificare `scf_list_installed_packages` e `scf_verify_workspace` rispondano correttamente.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-03"`. Verifica probabile: `ManifestManager` usa `_strip_package_section` (linea 1824). Se il re-export di `merge.sections` è incompleto, l'import in `manifest/manager.py` fallirà → confermerà che la freccia `merge → manifest` è obbligatoria nel grafo.

## Schema commit

```
refactor(manifest): estrai ManifestManager e SnapshotManager — nessuna modifica logica

Sposta ManifestManager, SnapshotManager e gli helper _scf_diff_workspace,
_scf_backup_workspace, _normalize_remote_file_record da spark-framework-engine.py
a spark/manifest/{manager,snapshots}.py.
Conferma dipendenza merge → manifest (uso di _strip_package_section).
Invarianti verificati.
```

---

## Nota post-completamento (2026-05-01)

Lo step è stato completato con una deviazione rispetto al piano:

- **Il file si chiama `spark/manifest/manifest.py`**, non `manager.py` come pianificato.
  La classe `ManifestManager` è presente e funzionante. L'import nei file del package
  è `from spark.manifest.manifest import ManifestManager`.
- **Aggiunto `spark/manifest/diff.py`:** gli helper diff (`_normalize_remote_file_record`,
  `_scf_diff_workspace`) sono in `diff.py` invece di `snapshots.py`.
- La dipendenza `merge → manifest` è stata confermata (uso di `_strip_package_section`)
  e aggiornata nel grafo di `REFACTORING-DESIGN.md` Sezione 6.
