---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 09 — Cleanup re-export hub
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 09 — Cleanup re-export hub

## Prerequisiti

- Step 01–08 completati.

## Obiettivo

Ridurre `spark-framework-engine.py` a un file di ~80 righe contenente solo:

- shebang/docstring di modulo
- import minimali
- blocco di re-export per backward compatibility con test e tool esterni
- invocazione `_build_app().run(transport="stdio")`

## Azioni atomiche

1. Verificare con `grep -n "^class \|^def \|^@dataclass" spark-framework-engine.py` che NON esistano più definizioni di classi o funzioni nel file (a parte l'eventuale `_log` setup).
2. Riorganizzare gli import in tre blocchi:
   - Standard library
   - Re-export pubblici (per tool esterni che fanno `from spark_framework_engine import ENGINE_VERSION`)
   - Import interni del bootstrap
3. Sostituire il contenuto del file con:

   ```python
   """SPARK Framework Engine entry point."""
   from __future__ import annotations
   
   import logging
   import sys
   
   logging.basicConfig(
       level=logging.INFO,
       format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
       stream=sys.stderr,
   )
   
   # Re-export pubblici per compatibilità test e tool esterni.
   from spark.core.constants import ENGINE_VERSION  # noqa: F401, E402
   from spark.core.models import (  # noqa: F401, E402
       WorkspaceContext, FrameworkFile, MergeConflict, MergeResult,
   )
   from spark.merge.engine import MergeEngine  # noqa: F401, E402
   from spark.manifest.manager import ManifestManager  # noqa: F401, E402
   from spark.workspace.inventory import FrameworkInventory  # noqa: F401, E402
   from spark.boot.sequence import SparkFrameworkEngine, _build_app  # noqa: E402
   
   if __name__ == "__main__":
       _build_app().run(transport="stdio")
   ```
4. Lanciare i tre invarianti.
5. Lanciare la suite test completa con `.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_integration_live.py`.

## Tre invarianti di verifica

**Invariante 1:** lancio motore con log completi.

**Invariante 2:** `mcp dev` mostra 44 tool e tutti rispondono.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline. Inoltre la suite test passa con stesso numero di test e zero regressioni rispetto al baseline pre-Fase 0 (stored in repository memory: 290 passed, 42 warnings).

## Criterio e procedura di rollback

`git stash push -m "rollback-step-09"`. Causa più probabile: un test referenzia un simbolo privato (`_qualcosa`) dell'hub che ora non è più re-esportato. Aggiungere il simbolo al blocco di re-export pubblici.

## Schema commit

```
refactor(boot): riduci spark-framework-engine.py a re-export hub minimale — nessuna modifica logica

Conclude la Fase 0 portando l'entry point a ~80 righe.
Mantenuti solo logging setup, re-export pubblici per backward compatibility
e invocazione _build_app().
Invarianti verificati. Suite test: 290 passed, 42 warnings.
```

```
docs(design): chiusura Fase 0 — sistema modulare attivo

Aggiorna REFACTORING-DESIGN.md aggiungendo nota di chiusura Fase 0:
tutti i moduli spark/ estratti, hub minimale, suite test verde.
Pronti per Fase 1 (stabilizzazione).
```
