---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 06 — Estrazione packages/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 06 — `spark/packages/`

## Prerequisiti

- Step 01–05 completati.

## Nota di scope

Durante la Fase 0 il modulo `packages/` riceve **solo** i simboli standalone già presenti a livello di modulo nel sorgente. La logica di lifecycle inner-function dentro `SparkFrameworkEngine.register_tools` resta nella classe e verrà migrata in Fase 1 (annotazione `# FASE1-RIASSEGNA: spostare in spark.packages.lifecycle`).

## Azioni atomiche

1. Creare `spark/packages/__init__.py` vuoto.
2. Creare `spark/packages/migration.py` con `MigrationPlan` e `MigrationPlanner`.
   - Origine: `MigrationPlan` (riga 2862, dataclass `frozen=True`), `MigrationPlanner` (riga 2897 fino a ~3112).
   - Import richiesti: `from spark.core.utils import _classify_v2_workspace_file, _utc_now`, `from spark.manifest.manager import ManifestManager`.
3. Creare `spark/packages/lifecycle.py` con gli helper standalone v3_store.
   - Simboli: `_install_package_v3_into_store` (3421), `_remove_package_v3_from_store` (3514), `_list_orphan_overrides_for_package` (3540), `_v3_overrides_blocking_update` (3566).
   - Import richiesti: `from spark.registry.store import PackageResourceStore`, `from spark.registry.mcp_registry import McpResourceRegistry`, `from spark.manifest.manager import ManifestManager`.
4. Creare `spark/packages/diff.py` come placeholder per la Fase 1.
   - Contenuto iniziale: solo docstring di modulo. La maggior parte degli helper diff sono inner functions di `register_tools` e verranno estratti in Fase 1.
5. Aggiungere re-export nell'hub:

   ```python
   from spark.packages.migration import MigrationPlan, MigrationPlanner  # noqa: F401
   from spark.packages.lifecycle import (  # noqa: F401
       _install_package_v3_into_store, _remove_package_v3_from_store,
       _list_orphan_overrides_for_package, _v3_overrides_blocking_update,
   )
   ```
6. Rimuovere le definizioni dall'hub.
7. Inserire annotazioni `# FASE1-RIASSEGNA: spostare in spark.packages.lifecycle` sui blocchi di `SparkFrameworkEngine` che gestiscono install/update/remove.
8. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore.

**Invariante 2:** `mcp dev`. `scf_migrate_workspace(dry_run=True)` risponde con piano. `scf_install_package` (su pacchetto fittizio non installato) restituisce errore strutturato non eccezione.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-06"`. Possibile causa: i nomi `_install_package_v3_into_store` ecc. sono usati anche come metodo di `SparkFrameworkEngine` (vedi riga 3884 — metodo omonimo). Verificare che il re-export non oscuri il metodo di classe.

## Schema commit

```
refactor(packages): estrai MigrationPlanner e helper v3_store — nessuna modifica logica

Sposta MigrationPlan, MigrationPlanner e gli helper di basso livello
_install_package_v3_into_store, _remove_package_v3_from_store,
_list_orphan_overrides_for_package, _v3_overrides_blocking_update
da spark-framework-engine.py a spark/packages/{migration,lifecycle}.py.
Annotati i blocchi di SparkFrameworkEngine con # FASE1-RIASSEGNA.
Invarianti verificati.
```

---

## Nota post-completamento (2026-05-01)

Lo step è stato completato con deviazioni rispetto al piano:

- **`MigrationPlan` e `MigrationPlanner` sono in `spark/workspace/migration.py`**,
  non in `spark/packages/migration.py`. La deviazione è avvenuta durante l'estrazione
  dello step precedente (05). Deviazione non bloccante; il codice è funzionante.
- **Le annotazioni `# FASE1-RIASSEGNA` non sono state inserite.** Il piano le
  prevedeva su blocchi di `SparkFrameworkEngine`, ma i marker non sono mai stati
  scritti nel codice. Verificato con grep in Fase 1 Step 1.3 (0 occorrenze trovate).
  Il piano FASE1-PIANO-TECNICO.md è stato riscritto di conseguenza.
- **`spark/packages/diff.py` non creato** come placeholder. Non bloccante.
- **`spark/packages/registry_summary.py`** aggiunto (non previsto nel piano):
  contiene `_build_registry_package_summary`, `_get_registry_min_engine_version`,
  `_resolve_package_version`.
