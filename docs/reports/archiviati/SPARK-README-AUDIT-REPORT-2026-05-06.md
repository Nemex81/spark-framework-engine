# SPARK README Audit Report — 2026-05-06

## Riepilogo

- Versione dichiarata nel README: 3.1.0 | Versione in `spark/core/constants.py`: 3.2.0 | Esito: **AGGIORNATA**
  - Nota: `pyproject.toml` non contiene il campo `version`; la versione è stata ricavata
    da `spark/core/constants.py` (confermata da `CHANGELOG.md` voce `[3.2.0] - 2026-05-06`).
- Tool dichiarati nel README: 44 | Tool trovati nel codice (`@_register_tool`): 44 | Esito: **OK**
- Resources dichiarate nel README: 19 | Resources trovate nel codice (`@_register_resource`): 19 | Esito: **OK**
- Python richiesto nel README: 3.10 | Python in `pyproject.toml` (`requires-python`): ≥3.11 | Esito: **AGGIORNATO**
- Firma `scf_bootstrap_workspace` nel README: incompleta (3 param) | Firma nel codice: 6 param | Esito: **AGGIORNATA**
- Refactor strutturale: **eseguito** — 5 sezioni spostate in `docs/getting-started.md`

---

## Modifiche applicate al README

- **Versione** (`riga ~10`): `3.1.0 (05 maggio 2026)` → `3.2.0 (06 maggio 2026)`
- **Requisiti — Python** (`riga ~17`): `Python 3.10 o superiore` → `Python 3.11 o superiore`
- **Tools Disponibili — `scf_bootstrap_workspace`**: firma aggiornata da
  `(install_base=False, conflict_mode="abort", update_mode="")` a
  `(install_base=False, conflict_mode="abort", update_mode="", migrate_copilot_instructions=False, force=False, dry_run=False)`
- **Migrazione Da Workspace Pre-Ownership — descrizione `scf_bootstrap_workspace`**: stessa firma aggiornata nel corpo narrativo
- **Refactor strutturale**: sostituzione del blocco da `## Quick Start` a `## Registrazione in VS Code (globale)` con:
  ```markdown
  ## Installazione e Primo Avvio

  Per la guida completa all'installazione, al primo avvio e alla
  configurazione del workspace, consulta:

  → **[docs/getting-started.md](docs/getting-started.md)**
  ```

---

## Contenuto spostato in `docs/getting-started.md`

- `## Quick Start (nuovo utente)` — completa, inclusi blocchi PowerShell e bash
- `## Installazione manuale` — completa
- `## Primo avvio (manuale)` — completa, inclusa sottosezione `### Configurazione manuale alternativa`
- `## Prima Configurazione` — completa
- `## Registrazione in VS Code (globale)` — completa

Tutte le sezioni copiate verbatim — nessuna riscrittura o semplificazione.

---

## Discrepanze segnalate (no modifica autonoma)

- **FILE MANCANTE**: `SCF-PROJECT-DESIGN.md` — citato nella sezione `## Architettura SCF` e in
  `## Progetto Correlati` del README, ma il file fisico non esiste nella root del repo.
  Trovato solo in `docs/archivio/SCF-PROJECT-DESIGN.md`.
  Azione richiesta: aggiornare il link nel README o spostare il file in root (decisione coordinatore).

- **COMPORTAMENTO DIVERGENTE**: `scf_bootstrap_workspace` — il README (sezione `## Migrazione`)
  descrive il bootstrap come "gli 9 prompt `scf-*.prompt.md`", ma il
  `packages/spark-base/package-manifest.json` dichiara attualmente **13** file
  `scf-*.prompt.md` in `workspace_files` (righe 149–161).
  Il testo è stato lasciato invariato. Richiede decisione del coordinatore su aggiornamento del conteggio.

---

## Note tecniche

- `pyproject.toml` non contiene il campo `version = "..."` nel blocco `[project]`.
  Nessun `setup.py` presente. La versione è stata determinata da `spark/core/constants.py`
  (`ENGINE_VERSION = "3.2.0"`) e verificata in `CHANGELOG.md` (`[3.2.0] - 2026-05-06`).
- `pyproject.toml` non dichiara `mcp` come dipendenza runtime (`[project.dependencies]` assente).
  La dipendenza è documentata in `requirements.txt`. La sezione `Requisiti` del README
  resta invariata sul punto `mcp (include FastMCP)` — allineata con `requirements.txt`.
- Il commento in `requirements.txt` recita "Python 3.10+ required (MCP SDK baseline)" ma
  `pyproject.toml` dichiara `requires-python = ">=3.11"`. Il README ora allinea a `pyproject.toml`
  (3.11). Il commento in `requirements.txt` non è stato toccato (file runtime, non README).
- Report di audit precedente rilevato: `SPARK-DOC-SYNC-REPORT-2026-05-06.md` — tipo diverso
  (sync documentazione generale), non duplicato del presente audit README.
- `docs/getting-started.md` non esisteva prima di questa sessione → FASE 7 eseguita.
