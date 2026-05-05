---
spark: true
scf_file_role: "config"
scf_version: "2.1.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_merge_priority: 30
---

# Copilot Instructions — SCF Python CodeCrafter

## Contesto

Questo pacchetto aggiunge al framework SPARK il layer Python-specifico.
Definisce agenti dedicati, instruction file e regole operative per sviluppo,
test e review di codice Python. Richiede `spark-base` e `scf-master-codecrafter`
come prerequisiti.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 2.4.0`.
Instruction file attivate automaticamente:
- `python.instructions.md` — attiva su `*.py`
- `tests.instructions.md` — attiva su `tests/**/*.py`
- `mcp-context.instructions.md` — attiva quando il task tocca codice engine MCP

## Regole operative Python

- Usa gli agenti `py-Agent-*` per analisi, design, code, plan e validate su task Python.
- Applica sempre `.github/instructions/python.instructions.md` per file `*.py`.
- Applica anche `.github/instructions/tests.instructions.md` quando lavori in `tests/`.
- Mantieni type hints, docstring Google-style, `pathlib.Path`, pytest
	e gestione esplicita delle eccezioni.
- Nei test privilegia fixture pytest, isolamento dei casi e mock
	limitati alle dipendenze esterne.
- Quando il task tocca codice MCP (tool FastMCP, resource, decorator),
	applica `.github/instructions/mcp-context.instructions.md`.

## Routing degli agenti

- `py-Agent-Analyze` — analisi codice Python esistente.
- `py-Agent-Design` — progettazione strutture e architettura Python.
- `py-Agent-Code` — implementazione e refactoring codice Python.
- `py-Agent-Plan` — pianificazione task Python con TODO strutturato.
- `py-Agent-Validate` — review, lint e verifica standard.

Per verificare quali agenti py-* sono installati:
→ resource `scf://agents-index`

## Ownership e Update Policy

- Questo blocco viene integrato nel workspace tramite `merge_sections`.
- Non trattarlo come file single-owner sostitutivo.
- Le scritture sotto `.github/` richiedono `github_write_authorized: true`
	nel runtime state; usa `scf_get_runtime_state()` per verificare.

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.
