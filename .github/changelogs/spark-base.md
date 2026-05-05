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

### Changed

- `spark-assistant.agent.md`: espande frontmatter `tools:` da 6 a 23 tool MCP reali; corregge nome `scf_list_available_agents` → `scf_list_agents` nel corpo.
- `spark-guide.agent.md`: corregge 3 nomi tool errati nel frontmatter (`scf_list_available_agents` → `scf_list_agents`, `scf_workspace_info` → `scf_get_workspace_info`, `scf_get_registry` → `scf_list_available_packages`); aggiunge 5 tool discovery; allinea nomi nel corpo.
- `copilot-instructions.md`: sostituisce sezione utente vuota con guida operativa engine-specifica (istruzioni attive, routing agenti, regole operative). Blocchi SCF invariati.

- Corretti i riferimenti cross-package negli agenti base verso skill distribuite come directory (`clean-architecture`, `docs-manager`, `framework-index`, `framework-query`, `project-doc-bootstrap`, `validate-accessibility`, `changelog-entry`).
- Rimossi i riferimenti rotti a `tests.instructions.md` e `project.instructions.md` dai flussi documentali base per allinearli agli asset realmente distribuiti nel layer `spark-base`.

### Changed

- Aggiunte note esplicite negli agenti base quando un riferimento rimanda a skill fornite da `scf-master-codecrafter` e disponibili solo se il pacchetto plugin e installato nel workspace.

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
