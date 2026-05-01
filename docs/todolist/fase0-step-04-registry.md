---
spark: true
scf-file-role: todo
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: TODO Fase 0 — Step 04 — Estrazione registry/
parent_plan: ../FASE0-PIANO-TECNICO.md
---

# Fase 0 — Step 04 — `spark/registry/`

## Prerequisiti

- Step 01, 02, 03 completati.

## Azioni atomiche

1. Creare `spark/registry/__init__.py` vuoto.
2. Creare `spark/registry/client.py` con la classe `RegistryClient`.
   - Origine: riga 2682 fino a riga ~2828.
   - Import richiesti: `from spark.core.constants import _CHANGELOGS_SUBDIR`, `from spark.core.utils import _utc_now`.
3. Creare `spark/registry/store.py` con `PackageResourceStore` e gli helper di basso livello.
   - Simboli: `_v3_store_sentinel_file` (3399), `_build_package_raw_url_base` (3409), `_resource_filename_candidates` (3595), `PackageResourceStore` (3609).
   - Import richiesti: `from spark.core.constants import _RESOURCE_TYPES`, `from spark.core.utils import parse_markdown_frontmatter`.
4. Creare `spark/registry/mcp_registry.py` con `McpResourceRegistry`.
   - Origine: riga 3751 fino a 3881.
   - Import richiesti: `from spark.core.constants import _RESOURCE_TYPES`.
5. Aggiungere re-export nell'hub:

   ```python
   from spark.registry.client import RegistryClient  # noqa: F401
   from spark.registry.store import (  # noqa: F401
       PackageResourceStore, _v3_store_sentinel_file, _build_package_raw_url_base,
       _resource_filename_candidates,
   )
   from spark.registry.mcp_registry import McpResourceRegistry  # noqa: F401
   ```
6. Rimuovere le definizioni dall'hub.
7. Lanciare i tre invarianti.

## Tre invarianti di verifica

**Invariante 1:** lancio motore con log `MCP resource registry: N URI registrati`.

**Invariante 2:** `mcp dev` permette di leggere `agents://list`, `skills://list`. Le risorse rispondono.

**Invariante 3:** `scf_verify_workspace` byte-identico a baseline.

## Criterio e procedura di rollback

`git stash push -m "rollback-step-04"`. Possibile causa di failure: `_resource_filename_candidates` o `_v3_store_sentinel_file` referenziati da codice ancora nell'hub via re-export non aggiornato. Verificare che TUTTI i call site usino il re-export corretto.

## Schema commit

```
refactor(registry): estrai RegistryClient, PackageResourceStore, McpResourceRegistry — nessuna modifica logica

Sposta i tre componenti del layer registry e gli helper di basso livello
v3_store_sentinel_file, _build_package_raw_url_base, _resource_filename_candidates
da spark-framework-engine.py a spark/registry/{client,store,mcp_registry}.py.
Aggiunti re-export nell'hub.
Invarianti verificati.
```
