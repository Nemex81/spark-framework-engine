# Fase 6 — scf_bootstrap_workspace aggiornato
# Dipende da: Fasi 1, 2, 5
# Effort stimato: M
# Stato: COMPLETATA — 2026-04-28
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_phase6_bootstrap_assets.py (creato)

## Prerequisiti

- [x] Fase 1: engine-manifest.json e spark-welcome presenti
- [x] Fase 2: McpResourceRegistry operativa
- [x] Fase 5: get_override_dir disponibile

## Task

- [x] 6.1 Generare AGENTS.md dinamicamente
      Helper `_render_agents_md(engine_agents, package_agents, existing_content)`
      con safe-merge tra marker `<!-- SCF:BEGIN:agents-index --> ... END`.
- [x] 6.2 Generare AGENTS-{plugin}.md per ogni pacchetto con agenti
      Helper `_render_plugin_agents_md(package_id, agents)`.
- [x] 6.3 Generare `.clinerules` se assente
      Helper `_render_clinerules(profile_summary)` con estrazione automatica
      da `project-profile.md` (`_extract_profile_summary`).
- [x] 6.4 Scrivere template `project-profile.md` se assente
      Helper `_render_project_profile_template()`.
- [x] 6.5 Integrare in `scf_bootstrap_workspace`
      Funzione `_apply_phase6_assets(workspace_root, engine_root,
      installed_packages, github_write_authorized)` invocata da
      `_finalize_bootstrap_result`. Additiva rispetto al flusso v2,
      report inserito in `result["phase6_assets"]`.
- [x] 6.6 Test bootstrap workspace vergine
      `tests/test_phase6_bootstrap_assets.py::TestApplyPhase6Assets::test_writes_all_assets_when_authorized`.
- [x] 6.7 Test bootstrap idempotente
      `tests/test_phase6_bootstrap_assets.py::TestApplyPhase6Assets::test_idempotent_second_run`.
- [x] 6.8 Test safe-merge AGENTS.md preserva contenuto utente
      `tests/test_phase6_bootstrap_assets.py::TestApplyPhase6Assets::test_safe_merge_preserves_user_agents_md`
      e `TestRenderAgentsMd::test_safe_merge_preserves_user_text`.
- [x] 6.9 Test .clinerules preserved
      `tests/test_phase6_bootstrap_assets.py::TestApplyPhase6Assets::test_clinerules_not_overwritten`.

## Test di accettazione

- [x] Bootstrap su workspace vergine produce AGENTS.md, AGENTS-{pkg}.md,
      project-profile.md template e .clinerules.
- [x] `project-profile.md` modificato dall'utente non sovrascritto al re-bootstrap.
- [x] `.clinerules` esistente non sovrascritto.
- [x] AGENTS.md safe-merge preserva testo utente fuori dai marker SCF.
- [x] Gate `github_write_authorized=False` blocca tutte le scritture.

## Validazione

- 16/16 test in `tests/test_phase6_bootstrap_assets.py` PASSED.
- Suite completa: 272 passed, 42 warnings (28 aprile 2026).

## Note tecniche

- Workaround v3.0 per `scf_update_profile` (rinviato a v3.1):
  l'utente che modifica manualmente `project-profile.md` deve
  eseguire `scf_bootstrap_workspace` per propagare le modifiche
  agli asset derivati (AGENTS.md, .clinerules, ecc.). Documentare
  in MIGRATION-GUIDE-v3.md e nel template di `project-profile.md`
  con un commento in testa al file.

- AGENTS.md esistente nell'engine `.github/AGENTS.md` non va
  toccato (è asset engine, non workspace).
- Il safe-merge deve usare lo stesso pattern di
  `copilot-instructions.md` (marker `SCF:BEGIN/END`).
- `.clinerules` non ha marker SCF: se esiste già con contenuto
  utente, log warning e NON sovrascrivere.
