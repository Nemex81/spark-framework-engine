---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Rapporto di validazione finale — Piano tecnico Fase 0
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Rapporto di validazione finale — Piano tecnico Fase 0

## 1. Panoramica

Il piano tecnico per la Fase 0 della modularizzazione è stato generato e validato in modalità autonoma a partire dal documento di progetto [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md) e dal prospetto integrativo [REFACTORING-TECHNICAL-BRIEF.md](REFACTORING-TECHNICAL-BRIEF.md). La sorgente di verità è il file `spark-framework-engine.py` letto sezione per sezione.

## 2. Classi e funzioni mappate

Sono state individuate e classificate **tutte** le entità di primo livello del sorgente:

- 4 dataclass: `WorkspaceContext`, `FrameworkFile`, `MergeConflict`, `MergeResult`.
- 1 dataclass aggiuntiva: `MigrationPlan`.
- 13 classi: `MergeEngine`, `WorkspaceLocator`, `FrameworkInventory`, `EngineInventory`, `ManifestManager`, `SnapshotManager`, `MergeSessionManager`, `RegistryClient`, `MigrationPlanner`, `PackageResourceStore`, `McpResourceRegistry`, `SparkFrameworkEngine`, più la classe interna `_ToolRegistry` se presente.
- ~70 funzioni di modulo, distribuite tra utility pure (`core/utils.py`), helper di sezione (`merge/sections.py`), validatori (`merge/validators.py`), helper di rendering (`assets/renderers.py`), helper v3_store (`packages/lifecycle.py`), helper di update policy (`workspace/update_policy.py`), funzioni di diff/backup (`manifest/snapshots.py`).
- 1 funzione bootstrap: `_build_app()`.

Ogni simbolo è mappato a una destinazione esplicita in `docs/FASE0-PIANO-TECNICO.md` Sezione 6.

## 3. Stato del grafo dipendenze

Il grafo del design (Sezione 6 di REFACTORING-DESIGN.md) è stato confrontato con l'analisi statica del sorgente. Esito:

| Freccia | Design | Realtà | Commento |
|---|---|---|---|
| `core → merge` | sì | sì | confermata |
| `core → manifest` | sì | sì | confermata |
| `merge → manifest` | NO | sì | `ManifestManager.purge_owner_entry` chiama `_strip_package_section` (riga 1824). Aggiunta esplicita al piano. |
| `manifest → registry` | sì | sì | confermata |
| `registry → workspace` | sì | sì | `FrameworkInventory.populate_mcp_registry` istanzia `McpResourceRegistry` e `PackageResourceStore` (righe 1267–1268) |
| `workspace → packages` | sì | sì | confermata |
| `workspace → assets` | sì | sì | confermata |
| `registry → assets` | NO | sì | `_apply_phase6_assets` istanzia `PackageResourceStore` (riga 3346). Aggiunta esplicita al piano. |
| `assets → boot` | sì | sì | confermata |

**Verdetto grafo:** complessivamente coerente con l'ordine di estrazione canonico. Le due frecce aggiuntive non alterano l'ordine, lo rafforzano. La documentazione di design verrà aggiornata con commit `docs(design)` previsti negli step 03 e 07.

## 4. Tool diagnostico

**Scelto:** `scf_verify_workspace`.

**Motivazione sintetica:** copertura multi-layer (core hash + manifest read + workspace scan), output deterministico, nessuna chiamata di rete, baseline riproducibile via `mcp dev` e archiviabile come JSON.

**Alternative valutate e scartate:**
- `scf_verify_system`: scartato per dipendenza dal registry remoto (output instabile).
- `scf_get_workspace_info`: copertura limitata e formattazione testuale → meno robusto come baseline.
- `scf_list_installed_packages`: tocca solo manifest, non rileva variazioni introdotte da modifiche al layer registry o workspace.

## 5. Step e rischi

| # | Modulo | Rischio | Causa principale di rischio |
|---|---|---|---|
| 1 | `core` | BASSO | nessuna dipendenza interna |
| 2 | `merge` | MEDIO | `MergeSessionManager` usa internamente `MergeEngine` e validators |
| 3 | `manifest` | MEDIO | dipendenza `merge → manifest` (uso di `_strip_package_section`) |
| 4 | `registry` | MEDIO | tre componenti accoppiati con differenti livelli di astrazione |
| 5 | `workspace` | ALTO | `FrameworkInventory` istanzia componenti di `registry/` |
| 6 | `packages` | MEDIO | logica orchestrazione resta in `SparkFrameworkEngine`, vengono estratti solo helper standalone con marker `# FASE1-RIASSEGNA` |
| 7 | `assets` | BASSO | dipendenze già stabilizzate negli step precedenti |
| 8 | `boot` | ALTO | classe `SparkFrameworkEngine` da ~4400 righe — molti riferimenti a globals e inner functions |
| 9 | `cleanup` | BASSO | solo riduzione hub, suite test full come gate finale |

## 6. Documenti generati

**Piani tecnici per fase:**

- [docs/FASE0-PIANO-TECNICO.md](FASE0-PIANO-TECNICO.md)
- [docs/FASE1-PIANO-TECNICO.md](FASE1-PIANO-TECNICO.md)
- [docs/FASE2-PIANO-TECNICO.md](FASE2-PIANO-TECNICO.md)
- [docs/FASE3-PIANO-TECNICO.md](FASE3-PIANO-TECNICO.md)
- [docs/FASE4-PIANO-TECNICO.md](FASE4-PIANO-TECNICO.md)

**TODO operativi per ogni step della Fase 0:**

- [docs/todolist/fase0-step-01-core.md](todolist/fase0-step-01-core.md)
- [docs/todolist/fase0-step-02-merge.md](todolist/fase0-step-02-merge.md)
- [docs/todolist/fase0-step-03-manifest.md](todolist/fase0-step-03-manifest.md)
- [docs/todolist/fase0-step-04-registry.md](todolist/fase0-step-04-registry.md)
- [docs/todolist/fase0-step-05-workspace.md](todolist/fase0-step-05-workspace.md)
- [docs/todolist/fase0-step-06-packages.md](todolist/fase0-step-06-packages.md)
- [docs/todolist/fase0-step-07-assets.md](todolist/fase0-step-07-assets.md)
- [docs/todolist/fase0-step-08-boot.md](todolist/fase0-step-08-boot.md)
- [docs/todolist/fase0-step-09-cleanup.md](todolist/fase0-step-09-cleanup.md)

**Totale:** 5 piani tecnici + 9 TODO operativi + 1 rapporto = 15 file generati.

## 7. Iterazioni di validazione

**Iterazione 1 — coerenza step ↔ TODO:**
- Verificata corrispondenza 1:1 tra le 9 righe della tabella in FASE0 Sezione 5 e i 9 file TODO.
- Verificata coerenza tra simboli/righe in FASE0 Sezione 6 e quelli citati in ogni TODO.
- Esito: nessuna correzione necessaria.

**Iterazione 1 — coerenza con design:**
- Le due frecce aggiuntive del grafo (`merge→manifest`, `registry→assets`) sono dichiarate sia in FASE0 Sezione 4 sia nei TODO step 03 e 07, con commit dedicato per l'aggiornamento di REFACTORING-DESIGN.md.
- L'ordine di estrazione canonico resta valido. Confidence aggiornamento grafo: 0.9.
- Esito: nessuna correzione bloccante; aggiornamento documentazione di design programmato negli step 03 e 07.

**Iterazione 1 — completezza e navigabilità:**
- Tutti i link interni a documenti generati risolvono nei path esistenti.
- Ogni TODO include: azioni atomiche, simboli con righe, re-export esatti, tre invarianti (avvio motore, wiring MCP, output `scf_verify_workspace` identico alla baseline), procedura di rollback, schema commit conforme a Conventional Commits.
- Esito: nessuna correzione necessaria.

**Iterazioni totali eseguite:** 1 su 3 ammesse.
**Correzioni applicate:** zero.

## 8. Anomalie e blocchi rimasti aperti

**Anomalie non bloccanti rilevate:**

1. **Log "Tools registered: 40 total" hardcoded:** il sorgente registra di fatto 44 tool ma il messaggio di log a riga 8380 è statico. Non bloccante per Fase 0 (non altera comportamento), va aggiornato in Fase 2 (boot deterministico) come parte della riscrittura di `_build_app`.
2. **`packages/diff.py` placeholder:** la maggior parte degli helper di diff sono inner function di `register_tools` e non sono estraibili senza modifica logica. Verranno migrati in Fase 1 con marker `# FASE1-RIASSEGNA`.
3. **Conferma necessaria della baseline:** la baseline `docs/reports/baseline-verify-workspace.json` deve essere prodotta dall'utente prima dell'avvio di Step 01 con il comando indicato in FASE0 Sezione 2. Senza baseline, l'invariante 3 di ogni step non è verificabile.

**Blocchi aperti:** nessuno.

**Conferma utente attesa:** nessuna richiesta dal piano. La generazione del piano è autonoma; l'esecuzione tecnica passo-passo richiederà conferme solo nei punti previsti dal modo `spark-engine-maintainer` (modifiche a `spark-framework-engine.py`, breaking change, rilascio).

## 9. Verdetto finale

**PIANO PRONTO PER REVISIONE UMANA.**

Il piano è internamente coerente, i 9 step di Fase 0 sono ordinati su un grafo dipendenze validato sul codice reale, ogni step è verificabile tramite tre invarianti deterministici e ogni step ha procedura di rollback definita. Le anomalie del grafo design sono state esplicitate e gestite con commit di aggiornamento documentazione.

**Prossimo passaggio (su decisione utente):**
1. Produrre la baseline `docs/reports/baseline-verify-workspace.json` come indicato in FASE0 Sezione 2.
2. Iniziare l'esecuzione dello Step 01 secondo `docs/todolist/fase0-step-01-core.md`.
3. Procedere step per step. Dopo ogni step, verificare i tre invarianti e committare con lo schema indicato.

**Confidence complessiva del piano:** 0.9.

Punti che hanno limitato la confidence al massimo livello:
- Numero esatto di inner function in `SparkFrameworkEngine` non enumerato (out-of-scope per Fase 0, rilevante solo per Fase 1).
- Stima delle righe per `boot/sequence.py` post-step-08 basata su conteggio approssimato (~4500 righe).
- Le costanti private oltre quelle elencate in righe 44–55 (es. `_RESOURCE_TYPES`, `_MANIFEST_FILENAME`) richiedono una rilettura puntuale durante l'esecuzione di Step 01 per evitare omissioni.
