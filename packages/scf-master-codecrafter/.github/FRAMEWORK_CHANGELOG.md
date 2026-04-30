---
spark: true
scf_owner: "scf-master-codecrafter"
scf_version: "2.1.0"
scf_file_role: "config"
scf_merge_strategy: "replace"
scf_merge_priority: 20
scf_protected: false
---

# Framework Changelog

## [2026-04-24]

### MSI cleanup

- Rimossi i duplicati legacy `-MSI` residui sotto `.github/` del pacchetto master, mantenendo come canonici solo i file attivi allineati al manifest e agli indici correnti.

### Framework unlock

- Framework unlock usato per riallineare i riferimenti documentali all'engine `spark-framework-engine >= 2.4.0` nei file protetti `copilot-instructions.md` e `AGENTS.md`, aggiungendo anche la nota che vincola `python.instructions.md` e `tests.instructions.md` alla presenza di `scf-pycode-crafter` nel workspace.

## [2026-04-23]

### Cross-package alignment

- Finestra di sblocco framework usata per correggere i riferimenti cross-package nei file protetti di `spark-base`, riallineare i changelog protetti e ripristinare subito `framework_edit_mode: false` nei project profile coinvolti al termine del batch.

## [2026-04-17]

### Changed

- OWN-A: normalizzati i front matter SCF dei file markdown sotto .github/, aggiornato il manifest del pacchetto allo schema 2.1 con files_metadata e allineati gli asset protetti del framework.
