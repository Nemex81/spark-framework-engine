---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 02 — Estrazione merge/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 02 — `spark/merge/`

## Prerequisiti

- Step 01 completato e verificato.

## Azioni atomiche

1. Creare `spark/merge/__init__.py` vuoto.
2. Creare `spark/merge/engine.py` con la classe `MergeEngine`.
   - Origine: `spark-framework-engine.py` riga 120 fino a fine classe (~292).
   - Import richiesti: `from spark.core.models import MergeConflict, MergeResult`.
3. Creare `spark/merge/validators.py` con le funzioni di validazione e i loro helper privati.
   - Simboli: `_normalize_merge_text`, `_extract_frontmatter_block`, `_extract_markdown_headings`, `validate_structural`, `validate_completeness`, `validate_tool_coherence`, `run_post_merge_validators`, `_resolve_disjoint_line_additions`.
   - Origine: righe 814–973.
4. Creare `spark/merge/sections.py` con le funzioni che gestiscono le sezioni `<!-- SCF:BEGIN -->` / `<!-- SCF:END -->`.
   - Simboli: `_section_markers_for_package`, `_scf_section_markers`, `_scf_split_frontmatter`, `_scf_extract_merge_priority`, `_scf_iter_section_blocks`, `_scf_render_section`, `_classify_copilot_instructions_format`, `_prepare_copilot_instructions_migration`, `_scf_section_merge_text`, `_scf_strip_section`, `_scf_section_merge`, `_strip_package_section`.
   - Origine: righe 975–1238.
5. Creare `spark/merge/sessions.py` con `MergeSessionManager`.
   - Origine: riga 2480 fino a fine classe (~2681).
   - Import richiesti: `from spark.core.constants import _MERGE_SESSIONS_SUBDIR`, `from spark.merge.engine import MergeEngine`.
6. Aggiungere re-export nell'hub:

   ```python
   from spark.merge.engine import MergeEngine  # noqa: F401
   from spark.merge.validators import (  # noqa: F401
       validate_structural, validate_completeness, validate_tool_coherence,
       run_post_merge_validators,
   )
   from spark.merge.sections import (  # noqa: F401
       _scf_section_merge, _scf_section_merge_text, _scf_strip_section,
       _strip_package_section, _scf_render_section, _scf_iter_section_blocks,
       _classify_copilot_instructions_format, _prepare_copilot_instructions_migration,
   )
   from spark.merge.sessions import MergeSessionManager  # noqa: F401
   ```
7. Rimuovere le definizioni copiate dall'hub.
8. Lanciare i tre invarianti.

## Re-export riga esatta

Aggiungere i blocchi al punto 6 immediatamente sotto i re-export di `spark.core.*`.

## Tre invarianti di verifica

**Invariante 1:** lancio motore senza eccezioni e log standard.

**Invariante 2:** `mcp dev` mostra 44 tool e tutti i tool che usano merge (es. `scf_install_package` simulato in dry mode) rispondono.

**Invariante 3:** `scf_verify_workspace` produce output byte-identico alla baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-02"`. Riverificare invarianti su stato pre-step. Probabili dipendenze nascoste da indagare: `MergeSessionManager` potrebbe usare `validate_*` e/o helper `_scf_*` — verificare ordine di import dentro `sessions.py`.

## Schema commit

```
refactor(merge): estrai algoritmo, validatori, sezioni SCF e sessioni — nessuna modifica logica

Sposta MergeEngine, validate_*, run_post_merge_validators, helper _scf_*
delle sezioni SCF e MergeSessionManager da spark-framework-engine.py
a spark/merge/{engine,validators,sections,sessions}.py.
Aggiunti re-export nell'hub.
Invarianti verificati.
```
