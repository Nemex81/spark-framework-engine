---
spark: true
applyTo: '**'
---

# Workflow Standard

## Sequenza

1. Analyze
2. Design
3. Plan
4. Code
5. Validate
6. Docs
7. Release

## Regole

- Ogni fase deve avere un criterio di uscita verificabile.
- Non passare alla fase successiva se la validazione locale fallisce.
- Aggiorna `docs/TODO.md` dopo ogni fase implementativa.
- Se manca una capability plugin, usa il fallback Agent-Research e segnala il gap.
# Workflow Standard — Risposta alle richieste di modifica
## Sequenza operativa (ogni richiesta di modifica)
Quando l'utente chiede modifiche al codice, applica questa sequenza:
1. TODO Gate (se multi-file o multi-commit):
   - Verifica esistenza docs/TODO.md
   - Se assente: crealo seguendo `.github/skills/document-template.skill.md`
   - Verifica che il TODO appartenga al task corrente
   - Leggi TODO + PLAN collegato prima di scrivere codice
2. Implementazione:
   - Type hints obbligatori (vedi `python.instructions.md`)
   - Logging semantico, zero print() in src/
   - Accessibilità NVDA verificata se tocchi UI (vedi `ui.instructions.md`)

3. Pre-commit (prima di ogni commit):
   - `python -m py_compile src/**/*.py`
   - `mypy src/ --strict`
   - `pylint --enable=cyclic-import`
   - `grep -r "print(" src/` (deve restituire 0 occorrenze)
   - `pytest --cov=src`  # soglia letta da pyproject.toml
   - `python scripts/validate_gates.py --check-all docs/2\ -\ projects/`

4. Sync documentazione (dopo ogni modifica .py):
   - API.md: aggiorna se ci sono signature pubbliche nuove o modificate
   - ARCHITECTURE.md: aggiorna se cambia struttura, layer flow, pattern
   - CHANGELOG.md: SEMPRE (Added/Fixed/Changed). Usa [Unreleased] nel branch.

5. Feedback strutturato all'utente:
   - Cosa cambia: file + righe coinvolte
   - Perché: motivazione tecnica
   - Impatto docs: file di documentazione da aggiornare

## File obbligatori per task complessi

| File | Trigger | Ciclo di vita |
|------|---------|---------------|
| DESIGN_*.md | Feature architetturale | DRAFT → REVIEWED |
| PLAN_*.md | Task multi-commit | DRAFT → READY |
| docs/TODO.md | PLAN approvato | Operativo durante il branch |

Per struttura e frontmatter: → `.github/skills/document-template.skill.md`
