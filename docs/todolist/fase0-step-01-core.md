---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 01 — Estrazione core/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 01 — `spark/core/`

## Azioni atomiche

1. Creare `spark/__init__.py` vuoto.
2. Creare `spark/core/__init__.py` vuoto.
3. Creare `spark/core/models.py` con `WorkspaceContext`, `FrameworkFile`, `MergeConflict`, `MergeResult` copiati alla lettera dal sorgente.
   - Origine: `spark-framework-engine.py` righe 75–119 (4 dataclass `frozen=True`).
   - Destinazione: `spark/core/models.py`.
4. Creare `spark/core/constants.py` con tutte le costanti di modulo definite alle righe 44–55 e quelle scoperte durante la lettura (`_RESOURCE_TYPES`, `_MANIFEST_FILENAME`, `_BOOTSTRAP_PACKAGE_ID` — verificarne la posizione esatta con `grep -n "^_RESOURCE_TYPES\|^_MANIFEST_FILENAME\|^_BOOTSTRAP_PACKAGE_ID" spark-framework-engine.py`).
   - Origine: righe 44–55 + costanti scoperte.
   - Destinazione: `spark/core/constants.py`.
5. Creare `spark/core/utils.py` con tutte le funzioni utility pure individuate.
   - Origine: simboli `_utc_now`, `_format_utc_timestamp`, `_parse_utc_timestamp`, `_sha256_text`, `_normalize_string_list`, `_parse_semver_triplet`, `_is_engine_version_compatible`, `parse_markdown_frontmatter`, `_extract_version_from_changelog`, `_is_v3_package`, `_resolve_dependency_update_order`, `_classify_v2_workspace_file`, `_normalize_manifest_relative_path`, `_infer_scf_file_role`.
   - Destinazione: `spark/core/utils.py`.
6. Aggiungere import di re-export in `spark-framework-engine.py` immediatamente sotto la sezione "Logging":

   ```python
   # Re-export hub Fase 0 — Step 1
   from spark.core.models import WorkspaceContext, FrameworkFile, MergeConflict, MergeResult  # noqa: F401
   from spark.core.constants import (  # noqa: F401
       ENGINE_VERSION, _CHANGELOGS_SUBDIR, _SNAPSHOTS_SUBDIR,
       _MERGE_SESSIONS_SUBDIR, _BACKUPS_SUBDIR, _USER_PREFS_FILENAME,
       _ALLOWED_UPDATE_MODES,
   )
   from spark.core.utils import (  # noqa: F401
       _utc_now, _format_utc_timestamp, _parse_utc_timestamp, _sha256_text,
       _normalize_string_list, _parse_semver_triplet, _is_engine_version_compatible,
       parse_markdown_frontmatter, _extract_version_from_changelog, _is_v3_package,
       _resolve_dependency_update_order, _classify_v2_workspace_file,
       _normalize_manifest_relative_path, _infer_scf_file_role,
   )
   ```
7. Rimuovere dal sorgente originale le definizioni copiate. **Mai prima del re-export.**
8. Lanciare i tre invarianti.

## Re-export riga esatta

Aggiungi i blocchi `from spark.core.* import ...` mostrati al punto 6 sotto la riga `_log: logging.Logger = logging.getLogger("spark-framework-engine")` (riga 36) e prima della riga `ENGINE_VERSION: str = "3.1.0"` (riga 44).

## Tre invarianti di verifica

**Invariante 1:** lanciare `.venv\Scripts\python.exe spark-framework-engine.py` per 3 secondi. Verificare assenza di eccezioni e presenza dei log `Workspace resolved`, `Framework inventory`, `MCP resource registry`, `Tools registered: 40 total`.

**Invariante 2:** lanciare `mcp dev .\spark-framework-engine.py` e verificare che l'inspector elenchi 44 tool e ~17 resource. Selezionare `scf_get_workspace_info` e confermare risposta non vuota.

**Invariante 3:** invocare `scf_verify_workspace`, salvare l'output in `docs/reports/step01-verify-workspace.json` e fare diff con `docs/reports/baseline-verify-workspace.json`. Differenza attesa: zero.

## Criterio e procedura di rollback

Se uno qualsiasi degli invarianti fallisce: `git stash push -m "rollback-step-01"`. Rilanciare gli invarianti per confermare ripristino. Analizzare il messaggio di errore o il diff. Se è emersa una dipendenza non mappata, aggiornare il grafo in [REFACTORING-DESIGN.md](../REFACTORING-DESIGN.md) Sezione 6 e ripetere lo step.

## Schema commit

```
refactor(core): estrai modelli, costanti e utility — nessuna modifica logica

Sposta WorkspaceContext, FrameworkFile, MergeConflict, MergeResult,
le costanti di modulo e le utility pure da spark-framework-engine.py
a spark/core/{models,constants,utils}.py.
Aggiunti re-export nell'hub.
Invarianti verificati: avvio motore, wiring MCP (44 tool), output
scf_verify_workspace identico alla baseline.
```
