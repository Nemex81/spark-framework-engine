# TODO Fase F — Documentazione e Release

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-f--documentazione-e-release)

Stato: Non avviata

---

## Aggiornamento documentazione engine

- [ ] Aggiornare `copilot-instructions.md` dell'engine con riferimento ai nuovi tool
- [ ] Aggiornare sezione tool in README: `scf_get_update_policy`, `scf_set_update_policy`
- [ ] Documentare il parametro `update_mode` su `scf_install_package` e `scf_update_package`
- [ ] Documentare il flusso a 6 step nel README
- [ ] Aggiornare sezione modalità di aggiornamento (Integrativo/Sostitutivo/Conservativo/Selettivo)

## CHANGELOG

- [ ] Aggiungere voce CHANGELOG con sezione `### Added` per nuovi tool e utility
- [ ] Aggiungere sezione `### Changed` per estensione install/update/bootstrap
- [ ] Seguire formato Keep a Changelog

## Versioning

- [ ] Bump `ENGINE_VERSION` in `spark-framework-engine.py` (minor version: nuova feature)
- [ ] Verificare allineamento `ENGINE_VERSION` ↔ ultima voce CHANGELOG
- [ ] Aggiornare `min_engine_version` nei pacchetti se necessario

## Aggiornamento pacchetti

- [ ] Aggiornare `copilot-instructions.md` di `spark-base` con nota sul sistema ownership
- [ ] Aggiornare `copilot-instructions.md` di `scf-master-codecrafter` con nota sul sistema
- [ ] Verificare che i `package-manifest.json` siano allineati alla nuova versione

## Skill e prompt

- [ ] Aggiornare skill `scf-package-management` con riferimento al nuovo flusso
- [ ] Valutare creazione prompt `/scf-update-policy` per gestione rapida della policy
- [ ] Aggiornare skill `scf-tool-development` con nota su `_scf_section_merge`

## Gate di uscita

- [ ] `pytest -q` passa suite completa
- [ ] README aggiornato
- [ ] CHANGELOG aggiornato con voce corretta
- [ ] ENGINE_VERSION bumped
- [ ] Audit di coerenza (`scf-coherence-audit`) superato
