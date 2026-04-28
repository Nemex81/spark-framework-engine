# Fase 7 — ManifestManager snellimento + smoke test Copilot
# Dipende da: Fase 6
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_manifest_manager.py
#   - docs/SMOKE-TEST-COPILOT-v3.md (nuovo, report manuale)

## Prerequisiti

- [ ] Fasi 0-6 completate e in main
- [ ] Suite test verde dopo ogni fase
- [ ] Workspace di test isolato (separato da quello dev)

## Task

- [ ] 7.1 Aggiornare tracking SHA-256 in `ManifestManager`
      File: `spark-framework-engine.py`
      Riga partenza: 1391.
      Logica: tracciare SHA solo per:
      - File in `workspace_files[]` di ogni manifest.
      - File in `.github/overrides/{type}/*.md`.
      Rimuovere tracking di file `agents/`, `prompts/`, `skills/`
      nel workspace (che non esisteranno più post-Fase 6).

- [ ] 7.2 Aggiornare schema `.scf-manifest.json` per nuovo
      tracking
      File: `spark-framework-engine.py`
      Schema bump a v3.0 con campo `overrides[]`. Backward
      compatibility: leggere v2.x e migrare in lettura.

- [ ] 7.3 Test ManifestManager nuovo schema
      File: `tests/test_manifest_manager.py`
      Casi: scrittura `.scf-manifest` v3.0, lettura v2.x con
      auto-migrazione, gate `github_write_authorized` rispettato.

- [ ] 7.4 Smoke test manuale Copilot — preparazione
      Workspace di test: nuovo VS Code workspace pulito.
      Engine: build v3.0.0-rc1 da branch.
      Pacchetti: spark-base + scf-master-codecrafter +
      scf-pycode-crafter.

- [ ] 7.5 Smoke test 1: bootstrap genera AGENTS.md correttamente
      Eseguire `scf_bootstrap_workspace`, verificare AGENTS.md
      con tutti gli agenti elencati.

- [ ] 7.6 Smoke test 2: Copilot riconosce agenti
      Aprire chat Copilot, dropdown agenti deve mostrare
      `@spark-assistant`, `@code-Agent-Code`, `@py-Agent-Code`.

- [ ] 7.7 Smoke test 3: MCP Resources accessibili da Copilot
      "Add Context > MCP Resources" mostra lista agenti
      engine + pacchetto.

- [ ] 7.8 Smoke test 4: ciclo override completo
      `scf_override_resource("agents://spark-guide", "...")` →
      file creato in `.github/overrides/agents/spark-guide.md`.
      `scf_read_resource("agents://spark-guide", "auto")` →
      ritorna override.
      `scf_drop_override("agents://spark-guide")` → file
      rimosso, lettura ritorna engine.

- [ ] 7.9 Smoke test 5: install + remove pacchetto aggiorna
      AGENTS.md
      `scf_install_package("scf-pycode-crafter")` → AGENTS.md
      include `py-Agent-*`.
      `scf_remove_package("scf-pycode-crafter")` → entry
      rimosse.

- [ ] 7.10 Smoke test 6: migrazione workspace v2.x reale
      Workspace v2.x con engine v2.4.0 esistente →
      `scf_migrate_workspace(dry_run=True)` → review →
      `scf_migrate_workspace(dry_run=False)` → workspace v3.0.

- [ ] 7.11 Compilare report `docs/SMOKE-TEST-COPILOT-v3.md`
      Lista test eseguiti, esito, eventuali regressioni.

## Test di accettazione

- [ ] Tutti i 6 smoke test passati e documentati nel report.
- [ ] Suite test pytest verde (incluso
      `tests/test_manifest_manager.py`).
- [ ] Nessuna regressione su tool MCP esistenti.

## Note tecniche

- Smoke test 6 richiede VS Code Insiders aggiornato per MCP
  Resource picker (verificare versione minima nelle release
  notes Microsoft).
- Se uno smoke test fallisce: NON procedere a Fase 8. Fix
  mirato + retry.
