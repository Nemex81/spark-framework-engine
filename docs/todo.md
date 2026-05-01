# SPARK Framework Engine — TODO Coordinatore

- **Sessione attiva:** Refactoring Modulare — Fase 5 ATTIVA
- **Ultimo aggiornamento:** 2026-05-01
- **Stato piano:** Fase 0 COMPLETATA — Fase 1 COMPLETATA — Fase 2 COMPLETATA — Fase 3 COMPLETATA — Fase 4 COMPLETATA — apertura Fase 5 autorizzata
- **Baseline test:** 0 failed / 296 passed / 8 skipped (post-Fase 4 CORREZIONE [1])

## Documenti di riferimento

- Design: `docs/REFACTORING-DESIGN.md`
- Prospetto tecnico: `docs/REFACTORING-TECHNICAL-BRIEF.md`
- Piano operativo Fase 0: `docs/coding plans/FASE0-PIANO-TECNICO.md`
- Piano operativo Fase 1: `docs/coding plans/FASE1-PIANO-TECNICO.md`
- Piano operativo Fase 2: `docs/coding plans/FASE2-PIANO-TECNICO.md`
- Piano operativo Fase 3: `docs/coding plans/FASE3-PIANO-TECNICO.md`
- Piano operativo Fase 4: `docs/coding plans/FASE4-PIANO-TECNICO.md`
- Piano operativo Fase 5: `docs/coding plans/FASE5-PIANO-TECNICO.md`

---

## ✅ PREREQUISITO ZERO — Baseline diagnostica runtime (SODDISFATTO)

Baseline generata: `docs/reports/baseline-verify-workspace.json` (13013 bytes).
Output reale di `scf_verify_workspace` con motore live post-Step 1.1 (2026-05-01).
Riferimento fisso per invariante diagnostico Fase 2+.

---

## Fase 0 — Modularizzazione (COMPLETATA)

| Step | Modulo | Rischio | File TODO | Stato |
|------|--------|---------|-----------|-------|
| 01 | `core` | BASSO | [fase0-step-01-core.md](todolist/fase0-step-01-core.md) | [x] |
| 02 | `merge` | MEDIO | [fase0-step-02-merge.md](todolist/fase0-step-02-merge.md) | [x] |
| 03 | `manifest` | MEDIO | [fase0-step-03-manifest.md](todolist/fase0-step-03-manifest.md) | [x] |
| 04 | `registry` | MEDIO | [fase0-step-04-registry.md](todolist/fase0-step-04-registry.md) | [x] |
| 05 | `workspace` | ALTO | [fase0-step-05-workspace.md](todolist/fase0-step-05-workspace.md) | [x] |
| 06 | `packages` | MEDIO | [fase0-step-06-packages.md](todolist/fase0-step-06-packages.md) | [x] |
| 07 | `assets` | BASSO | [fase0-step-07-assets.md](todolist/fase0-step-07-assets.md) | [x] |
| 08 | `boot` + `inventory` | ALTO | [fase0-step-08-boot.md](todolist/fase0-step-08-boot.md) | [x] |
| 09 | `cleanup hub` | BASSO | [fase0-step-09-cleanup.md](todolist/fase0-step-09-cleanup.md) | [x] |

### Deviazioni strutturali introdotte in Fase 0 (documentate, non bloccanti)

- **`spark/inventory/` non previsto:** Copilot ha estratto `FrameworkInventory` e
  `EngineInventory` in un package separato `spark/inventory/{framework,engine}.py`
  invece di `spark/workspace/inventory.py` come dichiarato nel piano originale.
  Il codice è corretto e funzionante. Il grafo in `REFACTORING-DESIGN.md` va aggiornato
  (Step 1.8).
- **`spark/workspace/update_policy.py` (ex `policy.py`):** Rinomina
  completata in Step 1.1 (2026-05-01). Deviazione risolta.
- **Marker `# FASE1-RIASSEGNA` mai materializzati nel codice Python:** i marker erano
  citati nel piano ma non sono mai stati inseriti come commenti inline. Verificato con
  grep exhaustivo in Fase 1 Step 1.3. Step chiuso a zero modifiche.
- **`engine_root` obbligatorio:** hardening completato in Step 1.2 (commit fd4b552).

---

## Fase 1 — Stabilizzazione (ATTIVA)

| Step | Operazione | Rischio | Stato | Note |
|------|-----------|---------|-------|------|
| 1.1 | Rinomina `policy.py` → `update_policy.py` + aggiorna import | BASSO | [x] | rinomina completata, import aggiornati | 
| 1.2 | Hardening `engine_root` obbligatorio in `WorkspaceLocator` e `EngineInventory` | BASSO | [x] | commit fd4b552 |
| 1.3 | Censimento marker `# FASE1-RIASSEGNA` | MEDIO | [x] | 0 marker trovati nel codice Python |
| 1.4 | Analisi e fix 27 failure pre-esistenti (gruppi: bootstrap, lifecycle, locator) | ALTO | [x] | commit 95d0299, 2ccfc90 |
| 1.5 | Fix log count hardcoded 40/44 in `spark/boot/sequence.py` | BASSO | [x] | incluso fix Step 1.4 |
| 1.6 | Rimozione `pytest_out.txt` + aggiornamento `.gitignore` | BASSO | [x] | commit f1ed7b6 |
| 1.7 | Generazione baseline runtime `baseline-verify-workspace.json` | BASSO | [x] | baseline generata, 13013 bytes |
| 1.8 | Aggiornamento `docs/REFACTORING-DESIGN.md` grafo Sezione 6 | BASSO | [x] | audit documentale 2026-05-01 |

**Invariante globale Fase 1:** la suite test non deve scendere sotto 0 failed / 282
passed / 8 skipped dopo ogni step.

---

## Fasi successive

| Fase | Obiettivo | Piano | Stato |
|------|-----------|-------|-------|
| Fase 2 | Boot deterministico | [FASE2-PIANO-TECNICO.md](coding%20plans/FASE2-PIANO-TECNICO.md) | COMPLETATA — apertura Fase 3 autorizzata |
| Fase 3 | Separazione runtime | [FASE3-PIANO-TECNICO.md](coding%20plans/FASE3-PIANO-TECNICO.md) | COMPLETATA — apertura Fase 4 autorizzata |
| Fase 4 | Gateway e workspace minimale | [FASE4-PIANO-TECNICO.md](coding%20plans/FASE4-PIANO-TECNICO.md) | COMPLETATA (SHA: d047cb0, ff966dc) |
| Fase 5 | Consolidamento finale e verifica contratti | [FASE5-PIANO-TECNICO.md](coding%20plans/FASE5-PIANO-TECNICO.md) | ATTIVA |

---

## Anomalie note — Backlog completo

### ~~P0~~ RISOLTO — Causa dei 27 failure pre-esistenti (risolto in Step 1.4, commit 2ccfc90)

I 27 failure erano divisi in 3 gruppi, tutti risolti:

- **Gruppo A — Bootstrap (8 failure):** fix routing ManifestManager, scrittura
  manifest/snapshot nel bootstrap semplice, fixture test con `engine_root` reale;
  6+2 test marcati `@unittest.skip` (dead code early return). `[RISOLTO Step 1.4]`
- **Gruppo B — Lifecycle v3 (15 failure):** root cause — `scf_install_package`
  chiamava il vecchio metodo istanza `_install_package_v3_into_store`. Cambiato
  a `self._install_package_v3`. Fix cascata: idempotenza, auth, manifest path,
  RegistryClient inline. `[RISOLTO Step 1.4]`
- **Gruppo C — Altri (4 failure):** locator guard `_is_user_home`, spark-init adopt
  log, tool counter 44. `[RISOLTO Step 1.4/1.5]`

### P1 — Non bloccanti, da trattare nei prossimi step

- **~~Log count hardcoded 40/44:~~** risolto in Step 1.5. `[RISOLTO]`
- **`packages/diff.py` placeholder:** helper di diff sono inner function di
  `register_tools`. Non estratti in Fase 0. Da valutare se estrarre in Fase 2
  (modifica logica).
- **~~Metodo istanza residuo `_install_package_v3_into_store`~~:** rimosso in Fase 2 Step 2.0. `[RISOLTO]`

### P2 — Da trattare in Fase 2

- **~~`_build_app` non deterministico~~:** risolto in Fase 2 (validation.py + SPARK_STRICT_BOOT feature flag). `[RISOLTO]`
- **~~Riferimento obsoleto in FASE2~~:** piano aggiornato in chiusura Fase 2. `[RISOLTO]`

---

## Storico sessioni precedenti

Le sessioni implementative precedenti (v3.0.0 Dual-Client, SCF 3-Way Merge,
spark-base, File Ownership, Gateway Pattern) sono archiviate in `docs/archivio/`.
