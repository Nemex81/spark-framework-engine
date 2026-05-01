# Fase 7 — ManifestManager snellimento + smoke test Copilot
# Dipende da: Fase 6
# Effort stimato: M
# Stato: COMPLETATA (codice + test) — Smoke test manuali DEFERRED a docs/SMOKE-TEST-COPILOT-v3.md
# Data: 2026-04-28
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_manifest_manager.py
#   - docs/SMOKE-TEST-COPILOT-v3.md (nuovo, report manuale)

## Prerequisiti

- [x] Fasi 0-6 completate e in main
- [x] Suite test verde dopo ogni fase
- [ ] Workspace di test isolato (separato da quello dev) — DEFERRED

## Task

- [x] 7.1 Aggiornare tracking SHA-256 in `ManifestManager`
      File: `spark-framework-engine.py`
      In v3 i file di pacchetto vivono in `engine_dir/packages/<pkg>/.github/`
      e non vengono più copiati nel workspace, quindi il tracking SHA in
      `.scf-manifest.json` resta naturalmente limitato a `workspace_files[]`
      e a `.github/overrides/{type}/*.md`. Logica `_sha256` invariata, ambito
      ridotto by-design dalla Fase 6.

- [x] 7.2 Aggiornare schema `.scf-manifest.json` per nuovo tracking
      File: `spark-framework-engine.py`
      Schema bump a `3.0` (`_MANIFEST_SCHEMA_VERSION`); aggiunto
      `_LEGACY_MANIFEST_SCHEMA_VERSIONS` e set supportato esteso a
      `{"1.0","2.0","2.1","3.0"}`. `save()` ora emette anche un campo
      `overrides[]` (type, name, file, sha256) ordinato e derivato dalle
      entries con `override_type`. Lettura v2.x backward-compat: load()
      ritorna le entries; alla prima save() il file viene riscritto in
      schema 3.0.

- [x] 7.3 Test ManifestManager nuovo schema
      File: `tests/test_manifest_manager.py` (creato).
      10 test verdi: schema v3.0 emit, overrides[] derivato e ordinato,
      backward-read v2.0/v2.1, rejection schema futuri, upgrade automatico
      v2→v3 al prossimo save(), cycle override write/drop.

- [DEFERRED] 7.4 Smoke test manuale Copilot — preparazione
      Vedi `docs/SMOKE-TEST-COPILOT-v3.md`.

- [DEFERRED] 7.5 Smoke test 1: bootstrap genera AGENTS.md correttamente
      Coverage automatica equivalente in `tests/test_phase6_bootstrap_assets.py`.

- [DEFERRED] 7.6 Smoke test 2: Copilot riconosce agenti
      UI manuale.

- [DEFERRED] 7.7 Smoke test 3: MCP Resources accessibili da Copilot
      UI manuale.

- [DEFERRED] 7.8 Smoke test 4: ciclo override completo
      Coverage automatica in `tests/test_override_tools.py` e
      `tests/test_manifest_manager.py::TestOverrideCycleV3`.

- [DEFERRED] 7.9 Smoke test 5: install + remove pacchetto aggiorna AGENTS.md
      Coverage parziale in `tests/test_phase6_bootstrap_assets.py`.

- [DEFERRED] 7.10 Smoke test 6: migrazione workspace v2.x reale
      UI/MCP manuale.

- [x] 7.11 Compilare report `docs/SMOKE-TEST-COPILOT-v3.md`
      Documento creato con stato DEFERRED, mappa coverage automatica
      ed esito suite pytest.

## Test di accettazione

- [DEFERRED] Tutti i 6 smoke test passati e documentati nel report.
- [x] Suite test pytest verde (incluso `tests/test_manifest_manager.py`).
- [x] Nessuna regressione su tool MCP esistenti — 272 passed.

## Note tecniche

- Smoke test 6 richiede VS Code Insiders aggiornato per MCP
  Resource picker (verificare versione minima nelle release
  notes Microsoft).
- Se uno smoke test fallisce: NON procedere a Fase 8. Fix
  mirato + retry.
