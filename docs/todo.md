# SPARK Framework Engine — TODO Coordinatore

- **Sessione attiva:** Refactoring Modulare — Fase 1 (Stabilizzazione)
- **Ultimo aggiornamento:** 2026-05-01
- **Stato piano:** Fase 0 COMPLETATA — Fase 1 APERTA
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
statico). **Prima di iniziare qualsiasi step di Fase 1**, generare la baseline:

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
   git commit -m "docs(baseline): cattura output scf_verify_workspace post-Fase0"
   ```

Senza questo file l'Invariante 3 di ogni step Fase 1 non è verificabile in modo runtime.

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
  invece di `spark/workspace/inventory.py` come dichiarato nel piano. Il codice è
  corretto e funzionante. Il piano Fase 0 e il grafo in `REFACTORING-DESIGN.md` sono
  stati aggiornati per riflettere questa struttura reale.
- **`spark/workspace/policy.py` invece di `update_policy.py`:** Le 7 funzioni di policy
  (`_default_update_policy`, `_update_policy_path`, ecc.) vivono in `policy.py`. Il piano
  originale dichiarava `update_policy.py`. Rinomina prevista in Fase 1 Step 1.1.
- **Modifiche di interfaccia in `WorkspaceLocator` e `EngineInventory`:** Entrambe
  le classi ora accettano `engine_root: Path = None` con fallback a `Path.cwd()`.
  Il fallback silenzioso è un debito tecnico da hardening in Fase 1 Step 1.2.
- **4 sostituzioni chirurgiche in `SparkFrameworkEngine`:** `EngineInventory()` →
  `EngineInventory(engine_root=self._ctx.engine_root)` e due `Path(__file__)` →
  `self._ctx.engine_root`. Tecnicamente fuori dal mandato "nessuna modifica logica"
  ma architetturalmente obbligatorie. Documentate nel TODO step-08.

---

## Fase 1 — Stabilizzazione (ATTIVA)

**Prerequisito:** Baseline runtime generata (vedi sezione PREREQUISITO ZERO sopra).

| Step | Operazione | Rischio | File TODO | Stato |
|------|-----------|---------|-----------|-------|
| 1.1 | Rinomina `policy.py` → `update_policy.py` + aggiorna import | BASSO | da creare | [ ] |
| 1.2 | Hardening `engine_root` obbligatorio in `WorkspaceLocator` e `EngineInventory` | BASSO | da creare | [ ] |
| 1.3 | Censimento e risoluzione marker `# FASE1-RIASSEGNA` | MEDIO | da creare | [ ] |
| 1.4 | Fix bug `WorkspaceContext.manifest` mancante (causa 8 failure pre-esistenti) | MEDIO | da creare | [ ] |
| 1.5 | Fix log count hardcoded 40/44 in `spark/boot/sequence.py` e docstring engine | BASSO | da creare | [ ] |
| 1.6 | Rimozione `pytest_out.txt` dalla root + aggiornamento `.gitignore` | BASSO | da creare | [ ] |
| 1.7 | Generazione baseline runtime `baseline-verify-workspace.json` | BASSO | da creare | [ ] |
| 1.8 | Aggiornamento `docs/REFACTORING-DESIGN.md` grafo Sezione 6 | BASSO | da creare | [ ] |

**Invariante globale Fase 1:** dopo ogni step, la suite test non deve scendere sotto
27 failed / 263 passed. L'obiettivo finale di Fase 1 è ridurre i failed da 27 a 0.

---

## Fasi successive

| Fase | Obiettivo | Piano | Stato |
|------|-----------|-------|-------|
| Fase 2 | Boot deterministico | [FASE2-PIANO-TECNICO.md](coding%20plans/FASE2-PIANO-TECNICO.md) | in attesa di Fase 1 |
| Fase 3 | Separazione runtime | [FASE3-PIANO-TECNICO.md](coding%20plans/FASE3-PIANO-TECNICO.md) | in attesa di Fase 2 |
| Fase 4 | Gateway e workspace minimale | [FASE4-PIANO-TECNICO.md](coding%20plans/FASE4-PIANO-TECNICO.md) | in attesa di Fase 3 |

---

## Anomalie note — Backlog completo

### P0 — Bloccanti per i test (27 failure pre-esistenti)

- **`WorkspaceContext.manifest` mancante:** il dataclass ha solo 3 campi
  (`workspace_root`, `github_root`, `engine_root`), ma `SparkFrameworkEngine` accede
  a `self._ctx.manifest` in almeno un punto. Causa 8 failure nel gruppo
  `test_bootstrap_workspace`. Da correggere in Fase 1 Step 1.4 aggiungendo il campo
  oppure correggendo il punto di accesso che lo usa erroneamente.
- **`test_package_lifecycle_v3`:** 10 failure pre-esistenti. Causa da analizzare
  durante Fase 1 Step 1.3 censimento marker.
- **`test_workspace_locator` flaky:** 2-3 failure intermittenti legati a `Path.cwd()`
  quando il test non specifica `engine_root`. Risolti da Step 1.2.

### P1 — Non bloccanti, da trattare in Fase 1

- **Log count hardcoded 40/44:** `"Tools registered: 40 total"` in
  `spark/boot/sequence.py` e commento `Tools (40)` in `spark/boot/engine.py`.
  Da aggiornare in Step 1.5.
- **`packages/diff.py` placeholder:** helper di diff sono inner function di
  `register_tools`, non estraibili senza modifica logica. Marker `# FASE1-RIASSEGNA`
  già inseriti. Da risolvere in Step 1.3.
- **`engine_root` opzionale con fallback `Path.cwd()`:** debito tecnico da
  `WorkspaceLocator.__init__` e `EngineInventory.__init__`. Da hardening in Step 1.2.

### P2 — Da trattare in Fase 2

- **`_build_app` non deterministico:** fallback silenziosi su errori di inventory
  e registry. Piano di correzione in `FASE2-PIANO-TECNICO.md`.
- **`validate_completeness`:** funzione con logica parziale annotata
  `# FASE2-FIX: log count hardcoded` (riga ~8380 originale, ora in
  `spark/merge/validators.py` o `spark/boot/sequence.py`).

---

## Storico sessioni precedenti

Le sessioni implementative precedenti (v3.0.0 Dual-Client, SCF 3-Way Merge,
spark-base, File Ownership, Gateway Pattern) sono archiviate in `docs/archivio/`.
