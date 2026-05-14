> **STATO: COMPLETATO** — Archiviato il 2026-05-14 (ENGINE_VERSION 3.6.0).
> Documento di sola lettura. Non modificare.

***

# FASE 5 — Consolidamento Finale e Verifica Contratti Architetturali
<!-- version: 1.0.0 | stato: ATTIVO | autore: spark-engine-maintainer -->

## Obiettivo

Verificare e consolidare tutti i contratti architetturali del refactoring modulare
completato nelle Fasi 0–4. Correggere le deviazioni minori. Documentare le deviazioni
accettate e quelle rinviate come lavoro futuro. Certificare la chiusura del ciclo di
refactoring modulare.

---

## Analisi READ-ONLY (FASE 1–3)

### FASE 1 — Prerequisiti

| Check | Risultato |
|-------|-----------|
| Suite test | 296 passed / 8 skipped / 0 failed (post-CORREZIONE [1]) |
| Entry point righe | 376 righe (contratto ~80 — vedi CORREZIONE [4]) |
| Grafo dipendenze | 0 violazioni |
| docs/todo.md | STALE — Fase 3 attiva, baseline 282, Fase 4 non completata |
| REFACTORING-DESIGN.md | v1.1.0 — discrepanze struttura (vedi CORREZIONE [2]) |
| Struttura fisica | Conforme + gateway.py (Fase 4, non dichiarato in design) |
| Engine startup | Tools registered: 44 total ✓ |

### FASE 2 — Censimento violazioni contratto

#### 2.A — Entry point (INVARIANTE-6)

`spark-framework-engine.py` è 376 righe. Il contratto dichiara ~80 righe.
Breakdown:
- ~35 righe: docstring + import stdlib + logging setup
- ~130 righe: re-export `from spark.X import ...`
- ~200 righe: commenti storici `# XYZ moved to spark.X.Y`
- ~11 righe: bootstrap `if __name__ == "__main__"`

**Valutazione**: nessuna logica di business presente.
Eccesso per commenti storici rimovibili (CORREZIONE [4]).

#### 2.B — Scritture workspace/ su .github/**

| File | Scrittura | Classificazione |
|------|-----------|-----------------|
| `workspace/locator.py:61-62` | probe su engine_dir/cache | LEGITTIMA — non tocca workspace .github/ |
| `workspace/migration.py:206-266` | shutil/write_bytes su .github/ | SKIP (Fase 4) — migrazione one-shot v2→v3 |
| `workspace/update_policy.py:121` | write_text user-prefs.json | SKIP (Fase 4) — policy file su workspace root |

#### 2.C — Scritture packages/ (contratto orchestrazione pura)

| File | Scrittura | Classificazione |
|------|-----------|-----------------|
| `packages/lifecycle.py:92,95` | write_text nel engine store | OUT-OF-SCOPE — engine store, non workspace |
| `packages/lifecycle.py:130` | shutil.rmtree nel engine store | OUT-OF-SCOPE — engine store, non workspace |

lifecycle.py viola il contratto "orchestrazione pura" letteralmente (scrittura
filesystem diretta), ma opera sull'engine store e non ha alternativa pratica.
Classificato NOTA — RINVIATO come refactoring futuro.

#### 2.D — Gateway bypass (INVARIANTE-4)

`spark/boot/engine.py` contiene scritture dirette su workspace/.github/**
nelle funzioni di installazione/aggiornamento pacchetti:
- linee 2594, 2617, 2641, 2659, 2681: `dest.write_text` in scf_install_package / scf_update_package
- linee 2722, 2736, 2797: scritture conflitti (manual merge)
- linea 3738: `dst.write_bytes` in bootstrap
- linee 4156: `dest_path.write_bytes` in scf_bootstrap_workspace
- linee 4377, 4428: scritture in scf_approve_conflict / scf_reject_conflict

La Fase 4 aveva migrato solo `_apply_phase6_assets` → gateway.
Le operazioni di install/update pacchetti e merge conflitti NON sono state migrate.

**Classificazione**: VIOLAZIONE CONTRATTO INVARIANTE-4 — ALTO — BLOCCANTE PER QUESTA FASE.
Il refactoring completo richiederebbe una Fase 4-BIS dedicata.
Documentato come lavoro futuro.

### FASE 3 — Elenco correzioni

| ID | Tipo | File | Descrizione | Rischio | Azione |
|----|------|------|-------------|---------|--------|
| C1 | Bug-test | `tests/test_engine_coherence.py` | Regex saltava `[Unreleased]` | BASSO | Applicata (da committare) |
| C2 | Docs | `docs/REFACTORING-DESIGN.md` | Sezione 4: policy.py→update_policy.py, gateway.py mancante, [validation.py] senza brackets, aggiungere Fase 5 | BASSO | Step 5.1 |
| C3 | Docs | `docs/todo.md` | Stale: Fase 4 non completata, baseline 282 vs 296 | BASSO | Step 5.0 |
| C4 | Code | `spark-framework-engine.py` | 376 righe vs ~80 contratto — rimozione commenti storici | MEDIO | Step 5.2 |
| C5 | Arch | `spark/boot/engine.py` | write_text su workspace .github/** senza gateway | ALTO | BLOCCANTE — RINVIATO |

---

## Verdetto Finale

**GATE**: CHIUSO — C1–C5 tutti implementati.
C5 eseguita in Fase 4-BIS (commit `a2a32ac`, 2026-05-01) come previsto al momento del rinvio.

**Motivazione**:
- C1–C3: correzioni documentali/test, rischio basso, nessuna logica toccata.
- C4: rimozione commenti storici dall'entry point, rischio medio, nessuna logica toccata.
- C5: refactoring gateway completato in Fase 4-BIS (12 callsite migrati, 2 helper introdotti).

---

## Piano di Implementazione (FASE 6)

### Step 5.0 — Aggiorna docs/todo.md

- Aggiorna `Sessione attiva` → Refactoring Modulare — Fase 5 ATTIVA
- Segna Fase 4 COMPLETATA con SHA commit
- Aggiorna baseline test → 296 passed / 8 skipped
- Aggiunge sezione Fase 5

**Criterio di uscita**: todo.md riflette stato reale.

### Step 5.1 — Aggiorna docs/REFACTORING-DESIGN.md

- Sezione 4: sostituisce `workspace/policy.py` con `workspace/update_policy.py`
- Sezione 4: aggiunge `spark/manifest/gateway.py` con descrizione
- Sezione 4: rimuove brackets da `[validation.py]`
- Sezione 7: aggiunge paragrafo Fase 5 — Consolidamento Finale

**Criterio di uscita**: design doc allineato alla struttura reale.

### Step 5.2 — Slim entry point spark-framework-engine.py

- Rimuove tutti i commenti storici `# XYZ moved to spark.X.Y`
- Conserva re-export, docstring, logging setup, bootstrap
- Target: ≤ 180 righe (re-export necessari + bootstrap)

**Criterio di uscita**: file ≤ 180 righe, suite test verde.

### Step 5.3 — Commit CORREZIONE [1]

- Commit: `tests/test_engine_coherence.py` (già modificato)
- Message: `fix(tests): regex salto [Unreleased] in test allineamento versione`

### Step 5.4 — Aggiorna CHANGELOG.md [Unreleased]

- Aggiunge Fase 5 changes nella sezione [Unreleased]

---

## Deviazioni Documentate e Rinviate

| Deviazione | File | Motivo | Priorità futura |
|------------|------|--------|-----------------|
| ~~Gateway bypass install/update~~ | spark/boot/engine.py | **RISOLTO in Fase 4-BIS** (commit a2a32ac) | CHIUSA |
| lifecycle.py write dirette su engine store | spark/packages/lifecycle.py | Funzionalità essenziale store | BASSA |
| migration.py write su .github/ | spark/workspace/migration.py | Migrazione one-shot storica | NESSUNA (terminata) |
| update_policy.py write user-prefs | spark/workspace/update_policy.py | Scrive su workspace root, non .github/ | NESSUNA |

---

## Chiusura

| Step | SHA | Stato |
|------|-----|-------|
| 5.0 — todo.md | a2a32ac | ✅ COMMITTATO |
| 5.1 — REFACTORING-DESIGN.md | a2a32ac | ✅ COMMITTATO |
| 5.2 — slim entry point | a2a32ac | ✅ COMMITTATO |
| 5.3 — commit C1 fix test | a2a32ac | ✅ COMMITTATO |
| 5.4 — CHANGELOG | a2a32ac | ✅ COMMITTATO |
| FASE5-CHIUSURA-REPORT.md | a2a32ac | ✅ COMMITTATO |
| C5 — Fase 4-BIS gateway | a2a32ac | ✅ COMMITTATO (fuori piano originale) |
