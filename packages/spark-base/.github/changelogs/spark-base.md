---
spark: true
scf_file_role: "config"
scf_version: "1.4.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

# Changelog — spark-base

<!-- markdownlint-disable MD024 -->

## [Unreleased]

### Added

- `Agent-Orchestrator` ritorna in `spark-base` come agente core del ciclo E2E.
- Skill operative `error-recovery`, `semantic-gate`, `task-scope-guard` ora in `spark-base`.
- Prompt `orchestrate` ora in `spark-base`.

### Removed

- `spark-assistant` e `spark-guide` spostati in `spark-ops` (layer sistemico).
- Rimossi dal catalogo distribuito MCP di `spark-base` gli agenti operativi
	`Agent-FrameworkDocs` e `Agent-Release`, forniti
	dal package `spark-ops`.
- Rimossi dal catalogo distribuito i prompt `release`,
	`framework-changelog`, `framework-release` e `framework-update`, forniti
	da `spark-ops`.

### Changed

- `spark-base` passa a `2.1.0`.
	sorgente legacy non vengono eliminati fisicamente finche non viene confermata
	la procedura `file-deletion-guard`.

### Fixed

- Corretti i riferimenti cross-package negli agenti base verso skill distribuite come directory (`clean-architecture`, `docs-manager`, `framework-index`, `framework-query`, `project-doc-bootstrap`, `validate-accessibility`, `changelog-entry`).
- Rimossi i riferimenti rotti a `tests.instructions.md` e `project.instructions.md` dai flussi documentali base per allinearli agli asset realmente distribuiti nel layer `spark-base`.

### Changed

- Aggiunte note esplicite negli agenti base quando un riferimento rimanda a skill fornite da `scf-master-codecrafter` e disponibili solo se il pacchetto plugin e installato nel workspace.

## [1.6.1] - 2026-04-28

### Changed

- Bump patch di compatibilita: `min_engine_version` aggiornata a `3.1.0` senza modifiche funzionali al payload del pacchetto.

## [1.4.0] - 2026-04-22

### Added

- Nuova instruction contestuale `.github/instructions/project-reset.instructions.md` per governare in modo esplicito il reset di `.github/project-profile.md` con conferme, backup e guard rail di framework.

### Changed

- `package-manifest.json` aggiornato a `1.4.0` e riallineato ai file realmente distribuiti nel pacchetto base dopo la reidratazione dei contenuti framework richiesti in questo rilascio.
- Gli asset base aggiornati nel ciclo `1.4.0` ora dichiarano `scf_version: "1.4.0"` dove appropriato, mentre skill e instruction engine-managed restano registrate come `engine-managed` nel manifest.
- Le skill e instruction engine-managed continuano a richiedere `spark-framework-engine >= 2.4.0`, ma il pacchetto torna a distribuire contenuto locale completo invece di limitarsi agli stub leggeri introdotti nel `1.3.0`.

### Notes

- Le aggiunte che appartengono gia a layer superiori o ad altri package (`Agent-Design`, `mcp-context.instructions.md`, `code-routing`, `clean-architecture`, `docs-manager`) restano volutamente escluse da `spark-base` per evitare conflitti di ownership tra pacchetti.

## [1.3.0] - 2026-04-22

### Changed

- 19 skill universali e 7 instruction universali sostituite da **stub leggeri** che delegano il contenuto al motore SPARK tramite le nuove resource MCP `engine-skills://{name}` e `engine-instructions://{name}`. Elenco delegato in `engine_provided_skills` e `engine_provided_instructions` nel `package-manifest.json`.
- Rimossi dal payload i subfolder `skills/changelog-entry/templates/`, `skills/error-recovery/reference/`, `skills/framework-query/reference/` e `skills/validate-accessibility/checklists/`: ora hostati integralmente dal motore.
- `min_engine_version` alzato a `2.4.0` (dipendenza dai namespace `engine-*://` introdotti dall'engine 2.4.0).

### Notes

- Retrocompatibilita: workspace su `spark-base@1.2.0` con file fisici pieni continuano a funzionare. La migrazione a stub avviene solo all'esecuzione esplicita di `scf_update_package("spark-base")`.
- I 5 asset contestuali restano file fisici completi: `agent-selector.skill.md`, `project-doc-bootstrap/`, `project-profile.skill.md`, `project-reset.skill.md` (skill) + nessuna instruction contestuale in questo pacchetto dopo la delega (era solo `spark-assistant-guide` che e` stato classificato come delegabile).

## [1.2.0] - 2026-04-16

### Added

- Nuova suite di prompt `scf-*` per installazione, rimozione, stato, aggiornamenti e ispezione dei pacchetti SCF dal picker prompt di VS Code.
- Prompt `scf-pre-implementation-audit` per audit read-only dei piani di hardening e delle modifiche ecosistema prima dell'implementazione.

## [1.1.0] - 2026-04-15

### Added

- `spark-guide.agent.md` entra nel layer base come agente user-facing condiviso tra bootstrap iniziale e stack pacchetti.

### Changed

- Il pacchetto richiede `spark-framework-engine >= 2.1.0` per adottare in sicurezza `spark-guide` quando il file era gia' stato bootstrap-pato dal motore.

## [1.0.0] - 2026-04-15

### Added

- Prima release del layer fondazionale SCF.
- 11 agenti base per orchestrazione, validazione, git, release, docs e ricerca.
- Instruction, skill condivise e prompt framework migrati da `scf-master-codecrafter`.

### Notes

- Richiede `spark-framework-engine >= 1.9.0`.
