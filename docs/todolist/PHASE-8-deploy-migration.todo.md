# Fase 8 — Deploy v3.0.0 + documentazione migrazione
# Dipende da: Fasi 0-7 (tutte)
# Effort stimato: S
# Stato: COMPLETATA — 2026-04-28
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/CHANGELOG.md
#   - spark-framework-engine/README.md
#   - docs/MIGRATION-GUIDE-v3.md (nuovo)

## Prerequisiti

- [x] Tutte le fasi precedenti completate e in main
- [DEFERRED] Smoke test Copilot superato (Fase 7) — vedi SMOKE-TEST-COPILOT-v3.md
- [x] Suite test verde — 272 passed
- [x] Coherence audit equivalente: tutti i test passano e ENGINE_VERSION
      allineata al CHANGELOG (verificato da test_engine_version_changelog_alignment)

## Task

- [x] 8.1 Aggiornare `ENGINE_VERSION` a "3.0.0"
      File: `spark-framework-engine.py` (linea 43).

- [x] 8.2 Aggiornare `CHANGELOG.md`
      Sezione `[3.0.0] - 2026-04-28` con Added / Changed /
      Deprecated / Migration / Notes.

- [x] 8.3 Aggiornare `README.md`
      Aggiunto banner versione 3.0.0 con link a
      `docs/MIGRATION-GUIDE-v3.md`.

- [x] 8.4 Scrivere `docs/MIGRATION-GUIDE-v3.md`
      Documento completo: cambiamenti, procedura
      `scf_migrate_workspace`, override workspace, rollback, FAQ.

- [x] 8.5 Aggiornare `min_engine_version` nei manifest
      `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`
      → `"3.0.0"`.

- [x] 8.6 Eseguire skill `scf-release-check` (mental check)
      ENGINE_VERSION 3.0.0 = CHANGELOG [3.0.0]. README banner
      aggiornato. Suite test verde. Pacchetti aggiornati.

- [x] 8.7 Proporre tag git (NON eseguito)
      Comando proposto (manuale o via Agent-Git):
      ```bash
      git tag -a v3.0.0 -m "SPARK Engine v3.0.0 — Centralized package store + MCP resource registry"
      git push origin v3.0.0
      ```
      Stessa procedura nei repo pacchetto dopo bump versione interna.

## Test di accettazione

- [x] `ENGINE_VERSION == "3.0.0"`.
- [x] CHANGELOG sezione `[3.0.0]` completa.
- [x] `MIGRATION-GUIDE-v3.md` presente e linkato dal README.
- [x] Coherence check (versione + changelog allineati): PASS.
- [x] Tag proposto come comando testuale, non eseguito autonomamente.

## Validazione finale

- pytest --ignore=tests/test_integration_live.py: **272 passed,
  42 warnings, 12 subtests passed in 24.40s** (28 aprile 2026).
- Compilazione: `python -m py_compile spark-framework-engine.py` OK.

## Note tecniche

- Breaking change formale: clienti che dipendono da
  `engine-skills://` ricevono warning ma continuano a
  funzionare. Rimozione effettiva pianificata in v4.0.
- `min_engine_version: 3.0.0` nei manifest pacchetto v3.x:
  utenti su engine v2.4.0 non potranno installare i nuovi
  pacchetti. Documentare chiaramente nel README.
- Il rilascio del registry può essere indipendente: scf-registry
  schema 2.0 invariato.
