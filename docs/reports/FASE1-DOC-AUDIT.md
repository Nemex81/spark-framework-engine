# SPARK — Audit Documentazione Post-Fase 1

- **Data:** 2026-05-01
- **Agente:** spark-engine-maintainer
- **Metodo:** Censimento codice reale → audit documenti → scrittura allineata

---

## Stato codice reale al momento dell'audit

| Indicatore | Valore |
|---|---|
| Package `spark/` presenti | 9 (core, merge, manifest, registry, inventory, workspace, packages, assets, boot) |
| Tool registrati | 44 (verificato con `grep -c "@_register_tool(" spark/boot/engine.py`) |
| Log atteso | `"Tools registered: 44 total"` in `spark/boot/sequence.py` |
| Suite test | 0 failed / 282 passed / 8 skipped |
| Test skippati | 8 (6 in `test_bootstrap_workspace.py` + 2 in `test_smoke_bootstrap_v3.py`) |
| Git HEAD | `2ccfc90` |

---

## Violazioni contratto architetturale

| Gravità | Contratto | File | Descrizione |
|---|---|---|---|
| CRITICA | — | — | (nessuna) |
| MEDIA | 4.6 (packages/) | `spark/packages/lifecycle.py` ~85 | Direct file writes (`dest.write_text`, `mkdir`) in packages/ invece che nel gateway |
| BASSA | 4.5 (workspace/) | `spark/workspace/migration.py` | `MigrationPlanner` (orchestrazione) in workspace/ invece che in packages/ |

---

## Deviazioni strutturali da piano originale

### Confermate e documentate in `docs/todo.md` (pre-audit)

1. `spark/inventory/` estratto come package separato (piano: `workspace/inventory.py`)
2. `workspace/policy.py` invece di `update_policy.py` (Step 1.1 pianifica rinomina)
3. `engine_root` obbligatorio (risolta, commit `fd4b552`)
4. Routing `scf_install_package → _install_package_v3` (risolta, commit `2ccfc90`)
5. `RegistryClient` istanziato inline (risolta, Step 1.4 Bug 3)
6. `_is_github_write_authorized_v3` (risolta, Step 1.4 Bug 2)
7. `ManifestManager(github_root)` in bootstrap (risolta, Step 1.4 Bug 1)
8. Tool counter 44 (risolta, Step 1.5)
9. 8 test `@unittest.skip` (risolta, Step 1.4)

### Nuove (emerse in questo audit)

| # | File previsto | File reale | Step di riferimento |
|---|---|---|---|
| 1 | `manifest/manager.py` | `manifest/manifest.py` | fase0-step-03 |
| 2 | `registry/mcp_registry.py` | `registry/mcp.py` | fase0-step-04 |
| 3 | `packages/migration.py` | `workspace/migration.py` | fase0-step-06 |
| 4 | `assets/renderers.py` | 4 file (collectors, phase6, rendering, templates) | fase0-step-07 |
| 5 | `boot/sequence.py` (SparkFrameworkEngine) | `boot/engine.py` | fase0-step-08 |
| 6 | `boot/validation.py` (placeholder) | non creato | fase0-step-08 |
| 7 | `packages/diff.py` (placeholder) | non creato | fase0-step-06 |
| 8 | — | `packages/registry_summary.py` (aggiunto) | fase0-step-06 |
| 9 | — | `registry/v3_store.py` (aggiunto) | fase0-step-04 |

---

## Documenti aggiornati in questo audit

| File | Tipo modifica |
|---|---|
| `docs/coding plans/FASE1-PIANO-TECNICO.md` | Riscrittura completa (piano precedente basato su marker inesistenti) |
| `docs/REFACTORING-DESIGN.md` Sezione 4 | Struttura fisica aggiornata (nomi file reali, `inventory/` aggiunto) |
| `docs/REFACTORING-DESIGN.md` Sezione 6 | Grafo dipendenze aggiornato (`inventory`, freccia `merge→manifest`) |
| `docs/coding plans/FASE2-PIANO-TECNICO.md` | Sezione DRIFT aggiunta |
| `docs/coding plans/FASE3-PIANO-TECNICO.md` | Sezione DRIFT aggiunta |
| `docs/coding plans/FASE4-PIANO-TECNICO.md` | Sezione DRIFT aggiunta |
| `docs/todolist/fase0-step-01-core.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-03-manifest.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-04-registry.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-05-workspace.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-06-packages.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-07-assets.md` | Nota post-completamento aggiunta |
| `docs/todolist/fase0-step-08-boot.md` | Nota post-completamento aggiunta |
| `docs/todo.md` | Header, baseline test, step 1.4/1.5/1.8, anomalie P0/P1 |
| `docs/reports/FASE1-DOC-AUDIT.md` | Creazione (questo file) |

---

## Debiti tecnici trovati (non corretti in questo audit)

| File | ~Riga | Descrizione | Gravità |
|---|---|---|---|
| `docs/REFACTORING-DESIGN.md` §11 | — | Testo cita `workspace/inventory.py` (non aggiornato — fuori perimetro §6) | BASSA |
| `spark/boot/engine.py` | ~179 | Vecchio metodo istanza `_install_package_v3_into_store` residuo (non più chiamato) | BASSA |
| `spark/packages/lifecycle.py` | ~85 | Direct file writes in packages/ (contratto 4.6 violato) | MEDIA |

---

## Step residui Fase 1

| Step | Descrizione | Bloccante per Fase 2? |
|---|---|---|
| 1.1 | Rinomina `policy.py` → `update_policy.py` + aggiorna import | No |
| 1.7 | Generazione baseline runtime (`baseline-verify-workspace.json`) | No (degrado accettabile) |

---

## Raccomandazione

**FASE 2 PRONTA**

Motivazione: 0 test falliti, routing v3 corretto, tool counter allineato, documentazione
allineata alla struttura reale. Step 1.1 e 1.7 sono non-bloccanti per Fase 2. La
documentazione è ora coerente con il codice prodotto da Fase 0 e con i fix di Fase 1.
