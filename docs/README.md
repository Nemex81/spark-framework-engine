# docs/ — Documentazione del Motore SPARK

Questa directory contiene la documentazione tecnica, i piani implementativi
e i report di sessione del motore `spark-framework-engine`.

---

## File principali

| File | Descrizione |
|------|-------------|
| [architecture.md](architecture.md) | Architettura del motore: componenti, Dual-Universe, ciclo di boot, flusso install, invarianti del sistema e costanti di riferimento. **Punto di partenza consigliato.** |
| [api.md](api.md) | Riferimento API completo: tutti i 51 tool MCP con firma, parametri, campi di risposta e note di migrazione per i tool deprecated. |
| [getting-started.md](getting-started.md) | Guida operativa per configurare e avviare il server MCP nel proprio editor. |

---

## Piani e design

| File | Descrizione |
|------|-------------|
| [implementation-plan-dual-mode-v3.1.md](implementation-plan-dual-mode-v3.1.md) | Piano implementativo del dual-mode manifest v3.1 (in lavorazione sul branch `feature/dual-mode-manifest-v3.1`). |
| [REFACTORING-DESIGN.md](REFACTORING-DESIGN.md) | Design architetturale del refactoring in corso. |
| [SPARK-DESIGN-FullDecoupling-v1.0.md](SPARK-DESIGN-FullDecoupling-v1.0.md) | Design del decoupling completo motore/workspace. |
| [SPARK-DESIGN-FullDecoupling-v2.0.md](SPARK-DESIGN-FullDecoupling-v2.0.md) | Aggiornamento v2.0 del design FullDecoupling. |
| [todo.md](todo.md) | TODO operativo del branch corrente. |

---

## Sottodirectory

| Directory | Contenuto |
|-----------|-----------|
| `reports/` | Report di completamento sessione SPARK (format `SPARK-REPORT-*.md`). Ogni report documenta una fase implementativa con gate di completamento. |
| `archivio/` | Documenti storici e piani obsoleti (archiviati, non più attivi). |
| `coding plans/` | Piani di implementazione per singoli moduli. |
| `prompts/` | Prompt di sessione usati durante il ciclo di sviluppo. |
| `todolist/` | TODO granulari per sotto-task specifici. |

---

## Note di manutenzione

- Dopo ogni modifica a `spark-framework-engine.py` con nuove firma pubbliche:
  aggiornare `api.md`.
- Dopo ogni modifica strutturale ai package in `spark/`:
  aggiornare `architecture.md` sezioni 2, 3 o 8.
- I report in `reports/` sono documenti storici: non modificare quelli già archiviati.
