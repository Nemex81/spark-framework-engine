---
spark: true
scf-file-role: report
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Report di Chiusura Fase 4 — WorkspaceWriteGateway
generated_at: "2026-05-01"
---

# Report di Chiusura Fase 4 — WorkspaceWriteGateway

## Sommario

Fase 4 completata. Introdotto `WorkspaceWriteGateway` in `spark/manifest/gateway.py`
come gateway centralizzato per le scritture del lifecycle phase6 sul workspace
`.github/`. I file `AGENTS.md`, `AGENTS-{pkg}.md` e `project-profile.md` generati
dal motore sono ora tracciati nel manifest automaticamente dopo ogni write.

---

## Step implementati

| Step | File | SHA | Descrizione |
|------|------|-----|-------------|
| 4.0 | `spark/manifest/gateway.py` (NEW) | `0761afd` | `WorkspaceWriteGateway` con `write()`, `write_bytes()`, `delete()` |
| 4.0 | `spark/manifest/__init__.py` | `0761afd` | Re-export `WorkspaceWriteGateway` da `__init__` |
| 4.2 | `spark/assets/phase6.py` | `5650f79` | `_apply_phase6_assets` usa gateway opzionale; owner `"spark-engine"` |
| 4.4 | `spark/boot/engine.py` | `6dc60eb` | Gateway iniettato ai 3 callsite phase6 |
| 4.5 | `tests/test_workspace_gateway.py` (NEW) | `d047cb0` | Suite test gateway (14 test) |

---

## Reclassificazioni rispetto al piano originale

| File | Verdetto | Motivazione |
|------|----------|-------------|
| `spark/packages/lifecycle.py` | OUT-OF-SCOPE | Scrive nel store engine (`engine_root/packages/`), non workspace `.github/` |
| `spark/workspace/migration.py` | SKIP | Migrazione one-shot v2→v3; caller senza manifest disponibile |
| `spark/workspace/update_policy.py` | SKIP | Scrive `user-prefs.json` (prefs utente); caller senza manifest |

---

## Decisioni di design

### Owner dei file phase6: `"spark-engine"` non `pkg_id`

I file `AGENTS-{pkg}.md` sono generati dall'engine durante ogni rebuild phase6,
non installati dai pacchetti. Usare `"spark-engine"` come owner:

1. Evita collisioni con il lifecycle v3 (`_remove_package_v3` rimuove solo le entry
   con `installation_mode: "v3_store"` e `package == pkg_id`).
2. Riflette correttamente la fonte: il file è prodotto dall'engine, non dal pacchetto.
3. Mantiene la retrocompatibilità: se `gateway` non è fornito (backward compat),
   il comportamento precedente (scrittura diretta, nessun tracking) è invariato.

### `.clinerules` — scrittura diretta invariata

`.clinerules` è a root del workspace, non sotto `.github/`. Il gateway è scoped a
`workspace_root/.github/`. Lasciarlo come scrittura diretta è corretto per design.

### `TYPE_CHECKING` guard in phase6.py

Per evitare import circolari a runtime (`spark.assets` → `spark.manifest`), l'import
di `WorkspaceWriteGateway` in `phase6.py` è sotto `TYPE_CHECKING`:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from spark.manifest.gateway import WorkspaceWriteGateway
```

Il parametro `gateway` nella signature usa lo string literal `"WorkspaceWriteGateway | None"`.

---

## Metriche di completamento

- **Test totali (suite completa):** 296 passed, 8 skipped, 0 failed
- **Test nuovi Fase 4:** 14 (test_workspace_gateway.py)
- **Regressioni introdotte:** 1 (corretta nella stessa sessione — `test_remove_v3_deletes_store_and_manifest_entry`)
- **File modificati:** 4 (gateway.py NEW, __init__.py, phase6.py, engine.py, test NEW)
- **Commit totali Fase 4:** 4

---

## Commit SHA

| Commit | Messaggio |
|--------|-----------|
| `0761afd` | feat(manifest): introduce WorkspaceWriteGateway in gateway.py |
| `5650f79` | refactor(assets): _apply_phase6_assets usa WorkspaceWriteGateway |
| `6dc60eb` | refactor(boot): SparkFrameworkEngine inietta gateway nei tool MCP |
| `d047cb0` | test(manifest): aggiunge test tracciamento gateway e manifest |

---

## Criterio di completamento parziale

Il criterio originale richiedeva che **tutte** le scritture su `<workspace>/.github/**`
passassero dal gateway. La Fase 4 ha migrato il sottoinsieme phase6 (principale
responsabile della generazione asset). Le scritture `migration.py` e `update_policy.py`
sono state classificate SKIP per motivazioni documentate sopra.

Il criterio completo richiederebbe una Fase 4-BIS per i casi SKIP, se necessario
in futuro.
