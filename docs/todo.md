# SPARK Framework Engine — TODO Coordinatore
- **Sessione attiva:** Ottimizzazioni Prestazionali v3 — COMPLETATA
- **Ultimo aggiornamento:** 2026-05-06
- **Stato piano:** Fase 0 COMPLETATA — Fase 1 COMPLETATA — Fase 2 COMPLETATA — Fase 3 COMPLETATA — Fase 4 COMPLETATA — Fase 5 COMPLETATA — Fase 4-BIS COMPLETATA — Refactoring-Estrazione Fase 1 COMPLETATA — Refactoring-Estrazione Fase 2 COMPLETATA — Ottimizzazioni Prestazionali v3 COMPLETATA
- **Baseline test:** 0 failed / 313 passed / 9 skipped / 42 warnings (verificata 2026-05-06)

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

## Fase 1 — Stabilizzazione (COMPLETATA)

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
| Fase 5 | Consolidamento finale e verifica contratti | [FASE5-PIANO-TECNICO.md](coding%20plans/FASE5-PIANO-TECNICO.md) | COMPLETATA (SHA: a2a32ac) |
| Fase 4-BIS | Chiusura INVARIANTE-4 — gateway forward writes | [FASE5-PIANO-TECNICO.md § Chiusura](coding%20plans/FASE5-PIANO-TECNICO.md) | COMPLETATA (SHA: a2a32ac, 2026-05-01) |

---

## Sessione 2026-05-05 — Refactoring estrattivo (COMPLETATO)

| Fase | Obiettivo | File introdotto | Stato |
|------|-----------|-----------------|-------|
| Refactoring Fase 1 | Estrazione ``spark/boot/install_helpers.py`` | ``spark/boot/install_helpers.py`` | COMPLETATA |
| Refactoring Fase 2 | Estrazione ``spark/boot/lifecycle.py`` | ``spark/boot/lifecycle.py`` | COMPLETATA |

### Refactoring Fase 1 — Estrazione `spark/boot/install_helpers.py` (DONE 2026-05-05)

- **File:** `spark/boot/install_helpers.py` (nuovo)
- **Operazione:** 21 funzioni estratte dalla closure `register_tools()` (13 pure + 8 shim).
  `engine.py` alleggerito di circa 500 righe.
- **Validazione:** 313 passed, 9 skipped (baseline invariata).
- **Stato:** DONE.

### Refactoring Fase 2 — Estrazione `spark/boot/lifecycle.py` (DONE 2026-05-05)

- **File:** `spark/boot/lifecycle.py` (nuovo)
- **Operazione:** `_V3LifecycleMixin` con 8 metodi v3 lifecycle estratti da
  `SparkFrameworkEngine`. `engine.py` da ~5169 a 4002 righe (-22.6%).
- **Validazione:** 313 passed, 9 skipped (baseline invariata).
- **Stato:** DONE.

### Ottimizzazioni Prestazionali v3 — 8 OPT (COMPLETATA 2026-05-06)

- **Commit:** `0c9d7ec` `perf(install): optimize v3 package installation (manifest cache, batch writes, parallel downloads)`
- **File toccati:** `spark/manifest/manifest.py`, `spark/manifest/gateway.py`,
  `spark/boot/lifecycle.py`, `spark/packages/lifecycle.py`, `spark/assets/phase6.py`
- **OPT-1:** Cache mtime-validata in `ManifestManager.load()` — evita relettura JSON su accessi ripetuti.
- **OPT-2:** Accumulo `pending_writes` in `_install_workspace_files_v3` — singola flush fisica invece di scrittura per file.
- **OPT-3:** Download parallelo in `_install_package_v3_into_store` — `ThreadPoolExecutor(max_workers=8)` al posto del loop seriale.
- **OPT-4:** Singola `manifest.upsert_many()` dopo batch writes — elimina N round-trip al file manifest.
- **OPT-5:** SHA-sentinel skip in `_install_workspace_files_v3` — file invariati non vengono riscritti.
- **OPT-6:** Hint `freshly_installed` in `_v3_repopulate_registry` — evita rilettura da disco del pacchetto appena installato.
- **OPT-7:** `sha256_hint` in `ManifestManager._build_entry()` — evita ricalcolo SHA su contenuto già noto.
- **OPT-8:** `WorkspaceWriteGateway.write_many()` — N scritture fisiche + singola `upsert_many()` al manifest.
- **Validazione:** 313 passed, 9 skipped (baseline invariata dopo fix cache mtime).
- **Stato:** DONE.

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

### P3 — Bootstrap primo avvio da workspace utente `[RISOLTO 2026-05-02]`

- **File:** `spark/workspace/locator.py`, `spark/boot/engine.py`, `spark/boot/sequence.py`, `mcp-config-example.json`
- **Problema:** il server MCP non materializzava automaticamente il Layer 0 nel
  workspace utente al primo avvio e la risoluzione del workspace dipendeva da
  fallback fragili quando il processo veniva lanciato fuori dalla cartella progetto.
- **Correzione applicata:** aggiunta precedenza esplicita per `--workspace` e env
  `WORKSPACE_FOLDER`, hook di auto-bootstrap in `_build_app()`, bootstrap minimo
  basato sul bundle locale `packages/spark-base/.github` con copia di agenti,
  istruzioni, prompt, `AGENTS.md`, `copilot-instructions.md` e `project-profile.md`.
- **Validazione:** `38 passed, 6 skipped` su suite focalizzata bootstrap/locator.

### P4 — ~~Logica duplicata in `scf_bootstrap_workspace`~~ (NO-OP 2026-05-05)

- **File:** `spark/boot/engine.py` — `scf_bootstrap_workspace`
- **Problema originale:** Il corpo della funzione conterrebbe logica di loop bootstrap duplicata
  (eredità del path pre-patch). Consolidare in un helper privato `_copy_bootstrap_targets`.
- **Verifica 2026-05-05:** Problema NON presente nel codice attuale. Esiste un solo loop di copia
  (riga 4589 circa). L'altra occorrenza (riga 4515) è un'espressione generatore inside `all(...)`
  per il gate di idempotenza — logica read-only, semanticamente incompatibile.
  Il P4 si riferiva a una versione precedente del codice già consolidata.
- **Stato:** CHIUSO — NO-OP.

### P5 — ~~Payload non uniforme in `scf_bootstrap_workspace`~~ (RISOLTO 2026-05-05)

- **File:** `spark/boot/engine.py` — `scf_bootstrap_workspace`
- **Problema:** I campi del dizionario di ritorno non erano uniformi tra tutti i rami
  (rami early-return vs ramo principale via `_finalize_bootstrap_result`).
- **Soluzione applicata 2026-05-05:** Aggiunta di `base_result: dict[str, Any]` come prima
  istruzione utile della funzione (fornisce defaults `files_copied`, `files_skipped`,
  `files_protected`, `sentinel_present`, `message`). Tutti i 7 rami early-return aggiornati
  con `**base_result` + campo `message` esplicito. Il ramo principale (`_finalize_bootstrap_result`)
  NON toccato. Nessun import aggiunto.
- **Validazione:** 313 passed, 9 skipped (baseline invariata).
- **Stato:** RISOLTO.

### P6 — Fase 3 — Promozione oggetti closure a attributi di istanza (IN ATTESA DI CONFERMA)

- **File:** `spark/boot/engine.py` — `SparkFrameworkEngine.__init__()` + `register_tools()`
- **Descrizione:** `register_tools()` crea localmente manifest, registry, merge_engine,
  snapshots, sessions come variabili di closure. Gli 8 shim in `install_helpers.py`
  dipendono da questo ciclo di vita. La Fase 3 prevede la promozione di questi oggetti
  a `self._manifest`, `self._registry` ecc. in `SparkFrameworkEngine.__init__()`,
  eliminando gli shim e rendendo la logica testabile in isolamento.
- **Prerequisito:** nessuno — il sistema e' stabile senza questa fase.
- **Trigger consigliato:** solo se viene aggiunto un secondo entry point all'engine
  (es. client Flutter o CLI diretta).
- **Rischio:** ALTO — tocca `__init__` e centinaia di riferimenti interni.
  Richiede ciclo di validazione dedicato.
- **Priorita':** BASSA.
- **Stato:** IN ATTESA DI CONFERMA DA LUCA.

### Verifica 2026-05-05 — `scf_bootstrap_workspace` audit completo

- **Audit richiesto da:** Coordinatore SPARK Council (Perplexity) — proposta "tool non ancora implementato"
- **Esito verifica:** SCENARIO C — Tool presente e completo (tool #37, riga 4086, engine.py).
  Parametri `force`/`dry_run` presenti. Idempotenza via sentinella verificata. File user_protected
  mai sovrascritti. Risposta MCP strutturata con tutti i campi richiesti. No stdout contaminato.
  `spark-assistant.agent.md` presente in `spark-base/.github/agents/`. Baseline 313 passed.
- **Azioni eseguite:** nessuna modifica al codice. Aggiornamento date e baseline in questo file.
- **Anomalie censite (gia' in P4/P5):** loop body duplicato e payload non uniforme — backlog BASSA priorita' invariato.

---

## Storico sessioni precedenti

Le sessioni implementative precedenti (v3.0.0 Dual-Client, SCF 3-Way Merge,
spark-base, File Ownership, Gateway Pattern) sono archiviate in `docs/archivio/`.
