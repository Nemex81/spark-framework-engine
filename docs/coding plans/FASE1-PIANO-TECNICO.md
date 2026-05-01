---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Piano Tecnico Fase 1 — Stabilizzazione
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Piano Tecnico Fase 1 — Stabilizzazione

## 1. Obiettivo

Eliminare bug noti, duplicazioni e ri-assegnare responsabilità segnalate in Fase 0 con il marker `# FASE1-RIASSEGNA`. Nessuna nuova feature.

## 2. Criterio di completamento

- Tutti i bug noti del backlog sono corretti.
- Ogni `# FASE1-RIASSEGNA` è risolto: la logica annotata è stata spostata nel modulo corretto.
- Nessuna duplicazione di funzioni helper tra moduli (parsing, hashing, validazione).
- Suite test passa con copertura uguale o superiore a quella post-Fase 0.

## 3. File coinvolti

Tutti i moduli sotto `spark/` creati in Fase 0. In particolare:

- `spark/packages/lifecycle.py` — assorbe metodi inner di `SparkFrameworkEngine` legati a install/update/remove se classificati come logica di orchestrazione.
- `spark/manifest/manager.py` — accoglie helper di parsing `.scf-manifest.json` eventualmente duplicati altrove.
- `spark/registry/store.py` — accoglie funzioni di basso livello v3_store annotate per riassegnazione.
- `spark/merge/sections.py` — consolidamento di chiamate duplicate `_strip_package_section`.

## 4. Operazioni specifiche

1. Censire tutti i marker `# FASE1-RIASSEGNA` con `grep -rn "FASE1-RIASSEGNA" spark/`.
2. Per ogni occorrenza: produrre un mini-piano di spostamento (origine, destinazione, simbolo, motivazione).
3. Risolvere il bug del metodo duplicato P1 (vedi backlog Fase 0): identificare il duplicato in `ManifestManager` o classi limitrofe e consolidare.
4. Verificare che nessun layer alto reimplementi parsing/hashing che esiste già in `core/utils.py`.
5. Regenerare la baseline `scf_verify_workspace` post-Fase 1 e archiviarla come `docs/reports/baseline-verify-workspace-fase1.json`.

## 5. Dipendenze dalla fase precedente

- Fase 0 deve essere chiusa: tutti i moduli `spark/` esistono, l'entry point è hub di re-export, suite test passa.
- I marker `# FASE1-RIASSEGNA` devono essere stati inseriti durante Fase 0 (non vengono creati ora).
- Il grafo dipendenze in [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md) Sezione 6 deve riflettere la realtà post-Fase 0.

## 6. Rischi specifici

- **Modifica logica camuffata da pulizia.** Ogni spostamento può alterare semantica se non isolato in commit dedicato. Mitigazione: invariante tool diagnostico ancora valido come baseline per ogni sotto-step.
- **Cascata di import.** Riassegnare un helper può rompere import in più moduli. Mitigazione: spostamento in due commit (1: aggiungi nel target, 2: rimuovi origine + aggiorna chiamanti).
- **Regressioni di copertura test.** I test scritti in Fase 0 potrebbero referenziare l'import path vecchio. Mitigazione: aggiornare gli import dei test nello stesso commit del fix.
