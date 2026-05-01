# SPARK Framework Engine — TODO Coordinatore

- **Sessione attiva:** Refactoring Modulare — Fase 1 (Stabilizzazione)
- **Ultimo aggiornamento:** 2026-05-01
- **Stato piano:** Fase 0 COMPLETATA — Fase 1 ATTIVA (step 1.2 e 1.3 completati)
- **Baseline test:** 27 failed / 263 passed (invariata rispetto al pristine pre-Fase 0)

## Documenti di riferimento

- Design: `docs/REFACTORING-DESIGN.md`
- Prospetto tecnico: `docs/REFACTORING-TECHNICAL-BRIEF.md`
- Piano operativo Fase 0: `docs/coding plans/FASE0-PIANO-TECNICO.md`
- Piano operativo Fase 1: `docs/coding plans/FASE1-PIANO-TECNICO.md`
- Piano operativo Fase 2: `docs/coding plans/FASE2-PIANO-TECNICO.md`
- Piano operativo Fase 3: `docs/coding plans/FASE3-PIANO-TECNICO.md`
- Piano operativo Fase 4: `docs/coding plans/FASE4-PIANO-TECNICO.md`

---

## ⚠ PREREQUISITO ZERO — Baseline diagnostica runtime (APERTO)

La baseline runtime `docs/reports/baseline-verify-workspace.json` non è ancora stata
generata con il motore reale. Fase 0 è stata completata in modalità degradata (confronto
statico). **Generare prima di chiudere Fase 1** (Step 1.7):

1. Avvia il motore in locale:

   ```powershell
   cd <cartella-repo>
   .venv\Scripts\python.exe spark-framework-engine.py
   ```

2. Da un client MCP (o `mcp dev`), chiama `scf_verify_workspace` senza argomenti.
3. Salva l'output JSON completo in `docs/reports/baseline-verify-workspace.json`.
4. Committa:

   ```powershell
   git add docs/reports/baseline-verify-workspace.json
   git commit -m "docs(baseline): cattura output scf_verify_workspace post-Fase1"
   ```

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
- **`spark/workspace/policy.py` invece di `update_policy.py`:** Le 7 funzioni di policy
  vivono in `policy.py`. Rinomina prevista in Step 1.1.
- **Marker `# FASE1-RIASSEGNA` mai materializzati nel codice Python:** i marker erano
  citati nel piano ma non sono mai stati inseriti come commenti inline. Verificato con
  grep exhaustivo in Fase 1 Step 1.3. Step chiuso a zero modifiche.
- **`engine_root` obbligatorio:** hardening completato in Step 1.2 (commit fd4b552).

---

## Fase 1 — Stabilizzazione (ATTIVA)

| Step | Operazione | Rischio | Stato | Note |
|------|-----------|---------|-------|------|
| 1.1 | Rinomina `policy.py` → `update_policy.py` + aggiorna import | BASSO | [ ] | | 
| 1.2 | Hardening `engine_root` obbligatorio in `WorkspaceLocator` e `EngineInventory` | BASSO | [x] | commit fd4b552 |
| 1.3 | Censimento marker `# FASE1-RIASSEGNA` | MEDIO | [x] | 0 marker trovati nel codice Python |
| 1.4 | Analisi e fix 27 failure pre-esistenti (gruppi: bootstrap, lifecycle, locator) | ALTO | [ ] | step successivo |
| 1.5 | Fix log count hardcoded 40/44 in `spark/boot/sequence.py` | BASSO | [ ] | |
| 1.6 | Rimozione `pytest_out.txt` + aggiornamento `.gitignore` | BASSO | [x] | commit f1ed7b6 |
| 1.7 | Generazione baseline runtime `baseline-verify-workspace.json` | BASSO | [ ] | dopo fix failure |
| 1.8 | Aggiornamento `docs/REFACTORING-DESIGN.md` grafo Sezione 6 | BASSO | [ ] | |

**Invariante globale Fase 1:** la suite test non deve scendere sotto 27 failed / 263
passed dopo ogni step. L'obiettivo finale è 0 failed.

---

## Fasi successive

| Fase | Obiettivo | Piano | Stato |
|------|-----------|-------|-------|
| Fase 2 | Boot deterministico | [FASE2-PIANO-TECNICO.md](coding%20plans/FASE2-PIANO-TECNICO.md) | in attesa di Fase 1 |
| Fase 3 | Separazione runtime | [FASE3-PIANO-TECNICO.md](coding%20plans/FASE3-PIANO-TECNICO.md) | in attesa di Fase 2 |
| Fase 4 | Gateway e workspace minimale | [FASE4-PIANO-TECNICO.md](coding%20plans/FASE4-PIANO-TECNICO.md) | in attesa di Fase 3 |

---

## Anomalie note — Backlog completo

### P0 — Causa dei 27 failure pre-esistenti (target Fase 1 Step 1.4)

I 27 failure sono divisi in 3 gruppi distinti. Analisi necessaria prima di
intervento (Step 1.4 produce l'analisi completa con il Prompt 4).

- **Gruppo A — `test_bootstrap_workspace` (~8 failure):** `SparkFrameworkEngine`
  accede a `self._ctx.manifest` ma `WorkspaceContext` non ha questo campo.
  Causa probabile: accesso errato o campo mancante nel dataclass.
- **Gruppo B — `test_package_lifecycle_v3` (~10 failure):** causa da analizzare
  nel Prompt 4. Il gruppo era pre-esistente e non legato ai marker FASE1-RIASSEGNA.
- **Gruppo C — `test_workspace_locator` (~2-3 failure):** flaky su
  `test_workspace_locator_ignores_home_env_without_workspace_markers`. Presente
  nel baseline pre-Fase 0, non introdotto dallo Step 1.2 (confermato da Copilot).

### P1 — Non bloccanti, da trattare nei prossimi step

- **Log count hardcoded 40/44:** `"Tools registered: 40 total"` in
  `spark/boot/sequence.py` e commento `Tools (40)` in `spark/boot/engine.py`.
  Target: Step 1.5.
- **`packages/diff.py` placeholder:** helper di diff sono inner function di
  `register_tools`. Il piano li dichiarava come candidati a marker FASE1-RIASSEGNA
  ma non sono stati annotati. Da valutare se estrarre in Fase 2 (modifica logica).

### P2 — Da trattare in Fase 2

- **`_build_app` non deterministico:** fallback silenziosi su errori di inventory
  e registry. Piano in `FASE2-PIANO-TECNICO.md`.
- **Riferimento obsoleto in FASE2:** il piano cita `_build_app` "alla riga 8348"
  del monolite — quella riga non esiste più. La funzione ora vive in
  `spark/boot/sequence.py`. Correzione prevista in Step 1.8 o all'apertura Fase 2.

---

## Storico sessioni precedenti

Le sessioni implementative precedenti (v3.0.0 Dual-Client, SCF 3-Way Merge,
spark-base, File Ownership, Gateway Pattern) sono archiviate in `docs/archivio/`.
