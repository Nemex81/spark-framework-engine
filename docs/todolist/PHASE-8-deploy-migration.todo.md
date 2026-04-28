# Fase 8 — Deploy v3.0.0 + documentazione migrazione
# Dipende da: Fasi 0-7 (tutte)
# Effort stimato: S
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/CHANGELOG.md
#   - spark-framework-engine/README.md
#   - docs/MIGRATION-GUIDE-v3.md (nuovo)

## Prerequisiti

- [ ] Tutte le fasi precedenti completate e in main
- [ ] Smoke test Copilot superato (Fase 7)
- [ ] Suite test verde
  (`.venv\Scripts\python.exe -m pytest -q`)
- [ ] Coherence audit verde
  (skill `scf-coherence-audit`)

## Task

- [ ] 8.1 Aggiornare `ENGINE_VERSION` a "3.0.0"
      File: `spark-framework-engine.py`
      Riga: 41.

- [ ] 8.2 Aggiornare `CHANGELOG.md`
      File: `CHANGELOG.md`
      Sezione `[3.0.0] - 2026-XX-XX` con:
      - Added: 5 nuovi tool, PackageResourceStore,
        McpResourceRegistry, engine-manifest.json, spark-welcome.
      - Changed: schema manifest v3.0, bootstrap dynamic
        AGENTS.md, cache relocation.
      - Deprecated: engine-skills://, engine-instructions://
        (alias retrocompatibile, rimozione v4.0).
      - Migration: vedi MIGRATION-GUIDE-v3.md.

- [ ] 8.3 Aggiornare `README.md`
      File: `README.md`
      Nuova sezione "Migrazione da v2.x" con link a
      `docs/MIGRATION-GUIDE-v3.md`. Aggiornare tool count, lista
      classi, lista risorse MCP.

- [ ] 8.4 Scrivere `docs/MIGRATION-GUIDE-v3.md`
      Contenuto:
      - Cosa cambia nel workspace utente
      - Step-by-step migrazione con scf_migrate_workspace
      - Scenari di rollback
      - FAQ comuni (override, perdita personalizzazioni, ecc.)

- [ ] 8.5 Aggiornare `min_engine_version` nei manifest
      File: 3 package-manifest.json.
      `min_engine_version` → "3.0.0" (i pacchetti v3.0 richiedono
      engine v3.0).

- [ ] 8.6 Eseguire skill `scf-release-check`
      Verifica checklist pre-release: coerenza interna,
      CHANGELOG popolato, ENGINE_VERSION coerente, README
      aggiornato.

- [ ] 8.7 Proporre tag git (NON eseguire)
      Output:
      ```bash
      git tag -a v3.0.0 -m "SPARK Engine v3.0.0 - Dual-client refactor"
      git push origin v3.0.0
      ```
      Delegare esecuzione a Agent-Git o utente.

## Test di accettazione

- [ ] `ENGINE_VERSION == "3.0.0"`.
- [ ] CHANGELOG sezione `[3.0.0]` completa.
- [ ] MIGRATION-GUIDE-v3.md presente e linkato dal README.
- [ ] `scf-release-check` ritorna PASS.
- [ ] Tag proposto come comando testuale, non eseguito
      autonomamente.

## Note tecniche

- Breaking change formale: clienti che dipendono da
  `engine-skills://` ricevono warning ma continuano a
  funzionare. Rimozione effettiva pianificata in v4.0.
- `min_engine_version: 3.0.0` nei manifest pacchetto v3.x:
  utenti su engine v2.4.0 non potranno installare i nuovi
  pacchetti. Documentare chiaramente nel README.
- Il rilascio del registry può essere indipendente: scf-registry
  schema 2.0 invariato.
