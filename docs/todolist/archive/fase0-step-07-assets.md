---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 07 — Estrazione assets/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 07 — `spark/assets/`

## Prerequisiti

- Step 01–06 completati.
- Verificato sul codice reale (riga 3346) che `_apply_phase6_assets` istanzia `PackageResourceStore` → confermata dipendenza `registry → assets` (freccia aggiuntiva al grafo).

## Azioni atomiche

1. Creare `spark/assets/__init__.py` vuoto.
2. Creare `spark/assets/renderers.py` con tutte le funzioni di rendering.
   - Simboli: `_agents_index_section_text` (3113), `_render_agents_md` (3159), `_render_plugin_agents_md` (3191), `_render_clinerules` (3222), `_render_project_profile_template` (3238), `_extract_profile_summary` (3243), `_read_agent_summary` (3268), `_collect_engine_agents` (3286), `_collect_package_agents` (3302), `_apply_phase6_assets` (3320).
   - Import richiesti: `from spark.core.utils import parse_markdown_frontmatter`, `from spark.registry.store import PackageResourceStore`, `from spark.workspace.inventory import EngineInventory`.
3. Aggiungere re-export nell'hub:

   ```python
   from spark.assets.renderers import (  # noqa: F401
       _agents_index_section_text, _render_agents_md, _render_plugin_agents_md,
       _render_clinerules, _render_project_profile_template, _extract_profile_summary,
       _read_agent_summary, _collect_engine_agents, _collect_package_agents,
       _apply_phase6_assets,
   )
   ```
4. Rimuovere le definizioni dall'hub.
5. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore.

**Invariante 2:** `mcp dev`. `scf_bootstrap_workspace` (su workspace già bootstrappato) restituisce `already_bootstrapped` con campo `phase6_assets`.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-07"`. Causa probabile di failure: `_apply_phase6_assets` legge file da engine root tramite `EngineInventory()`. Verificare che il path engine sia ancora calcolato correttamente.

## Schema commit

```
refactor(assets): estrai renderer asset workspace — nessuna modifica logica

Sposta _render_agents_md, _render_clinerules, _render_project_profile_template,
_apply_phase6_assets e gli helper correlati da spark-framework-engine.py
a spark/assets/renderers.py.
Conferma dipendenza registry → assets (uso di PackageResourceStore).
Aggiornare REFACTORING-DESIGN.md Sezione 6 per esplicitare la freccia.
Invarianti verificati.
```

---

## Nota post-completamento (2026-05-01)

Lo step è stato completato con una deviazione rispetto al piano:

- **Il package `spark/assets/` è implementato come 4 file** invece di un singolo
  `renderers.py`:
  - `spark/assets/collectors.py` — `_collect_engine_agents`, `_collect_package_agents`,
    `_read_agent_summary`
  - `spark/assets/phase6.py` — `_apply_phase6_assets`
  - `spark/assets/rendering.py` — `_agents_index_section_text`, `_render_agents_md`,
    `_render_plugin_agents_md`, `_render_clinerules`, `_render_project_profile_template`,
    `_extract_profile_summary`
  - `spark/assets/templates.py` — `_AGENTS_INDEX_BEGIN`, `_AGENTS_INDEX_END`,
    `_CLINERULES_TEMPLATE_HEADER`, `_PROJECT_PROFILE_TEMPLATE`
- L’import è `from spark.assets import _apply_phase6_assets, ...` (aggiornato
  in `spark/assets/__init__.py`).
- La freccia `registry → assets` (via `PackageResourceStore` in `_apply_phase6_assets`)
  è stata confermata e aggiornata nel grafo `REFACTORING-DESIGN.md` Sezione 6.
- `_apply_phase6_assets` usa anche `EngineInventory` da `spark/inventory/` —
  freccia `inventory → assets` aggiunta al grafo.

```
docs(design): aggiorna grafo — dipendenza registry→assets rilevata step 07

Aggiunta freccia esplicita registry → assets nel grafo della Sezione 6
di REFACTORING-DESIGN.md. _apply_phase6_assets istanzia PackageResourceStore
direttamente (riga 3346 del sorgente pre-refactor).
```
