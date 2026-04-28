# TODO Fase F — Documentazione e Release

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-f--documentazione-e-release)

Stato: Completata

---

## Aggiornamento documentazione engine

- [x] Aggiornare `copilot-instructions.md` dell'engine con riferimento ai nuovi tool
- [x] Aggiornare sezione tool in README: `scf_get_update_policy`, `scf_set_update_policy`
- [x] Documentare il parametro `update_mode` su `scf_install_package` e `scf_update_package`
- [x] Documentare il flusso a 6 step nel README
- [x] Aggiornare sezione modalità di aggiornamento (Integrativo/Sostitutivo/Conservativo/Selettivo)

## CHANGELOG

- [x] Aggiungere voce CHANGELOG con sezione `### Added` per nuovi tool e utility
- [x] Aggiungere sezione `### Changed` per estensione install/update/bootstrap
- [x] Seguire formato Keep a Changelog

## Versioning

- [x] Bump `ENGINE_VERSION` in `spark-framework-engine.py` (minor version: nuova feature)
- [x] Verificare allineamento `ENGINE_VERSION` ↔ ultima voce CHANGELOG
- [x] Aggiornare `min_engine_version` nei pacchetti se necessario

## Aggiornamento pacchetti

- [x] Aggiornare `copilot-instructions.md` di `spark-base` con nota sul sistema ownership
- [x] Aggiornare `copilot-instructions.md` di `scf-master-codecrafter` con nota sul sistema
- [x] Verificare che i `package-manifest.json` siano allineati alla nuova versione

## Skill e prompt

- [x] Aggiornare skill `scf-package-management` con riferimento al nuovo flusso
- [x] Valutare creazione prompt `/scf-update-policy` per gestione rapida della policy
- [x] Aggiornare skill `scf-tool-development` con nota su `_scf_section_merge`

## Gate di uscita

- [x] `pytest -q` passa suite completa
- [x] README aggiornato
- [x] CHANGELOG aggiornato con voce corretta
- [x] ENGINE_VERSION bumped
- [x] Audit di coerenza (`scf-coherence-audit`) superato

Nota implementativa:

- Release allineata a `2.3.0` come minor semantico per consolidare OWN-B, OWN-C, OWN-D, OWN-E e OWN-F.
- I `package-manifest.json` di `spark-base` e `scf-master-codecrafter` sono stati verificati e non richiedono bump di `min_engine_version`: la release OWN-F documenta il sistema, non introduce un nuovo requisito tecnico lato pacchetto.
