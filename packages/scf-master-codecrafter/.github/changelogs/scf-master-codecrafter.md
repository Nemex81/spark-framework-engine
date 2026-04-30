---
spark: true
scf_file_role: "config"
scf_version: "2.2.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_merge_priority: 20
---

# Changelog — scf-master-codecrafter

<!-- markdownlint-disable MD024 -->

## [Unreleased]

### Cross-package alignment

- Le skill `clean-architecture` e `docs-manager` restano dipendenze cross-package fornite da `scf-master-codecrafter`; i riferimenti consumer in `spark-base` sono stati riallineati ai path reali basati su directory.

### Changed

- Rimossi dal repository del master gli 11 agenti condivisi ora forniti dal layer `spark-base`, mantenendo nel pacchetto solo gli agenti esclusivi legati alla programmazione.
- Rinominati gli agenti esclusivi del master con prefisso `code-` (`code-Agent-Code`, `code-Agent-CodeRouter`, `code-Agent-CodeUI`, `code-Agent-Design`).
- Aggiornati indice agenti, copilot instructions e manifest del pacchetto per riflettere la nuova ownership degli agenti condivisi e il nuovo naming degli agenti esclusivi.
- Razionalizzati i prompt condivisi: i wrapper e i prompt framework con logica specifica restano nel master, mentre i prompt workflow duplicati sono rimossi in favore delle definizioni condivise fornite da `spark-base`.
- Rimosse dal pacchetto master le instruction condivise duplicate (`framework-guard`, `git-policy`, `model-policy`, `personality`, `verbosity`, `workflow-standard`), mantenendo solo le instruction esclusive del layer master.
- Aggiunti al `package-manifest.json` i prompt condivisi che restano fisicamente distribuiti nel pacchetto (`framework-release`, `framework-unlock`, `framework-update`, `git-commit`, `git-merge`, `help`, `package-update`).

## [2.4.1] - 2026-04-28

### Changed

- Bump patch di compatibilita: `min_engine_version` aggiornata a `3.1.0` mantenendo invariato il comportamento funzionale del pacchetto.

## [2.2.0] - 2026-04-22

### Changed

- Skill `clean-architecture` e `docs-manager` sostituite da stub leggeri che delegano il contenuto al motore SPARK via resource MCP `engine-skills://clean-architecture` e `engine-skills://docs-manager`. Elenco in `engine_provided_skills` nel `package-manifest.json`.
- Rimossi dal payload i subfolder `skills/clean-architecture/templates/` e `skills/docs-manager/templates/`: ora hostati integralmente dal motore.
- `min_engine_version` alzato a `2.4.0` (dipendenza dai namespace `engine-*://` introdotti dall'engine 2.4.0).

### Unchanged (contestuali)

- `skills/code-routing.skill.md` rimane file fisico: dipende dagli agenti installati nel workspace.
- `instructions/mcp-context.instructions.md` rimane file fisico: dipende dai tool MCP disponibili nell'installazione utente.

## [2.1.0] - 2026-04-15

### Added

- Ripristinato `code-Agent-Code` come executor generico del layer master per coprire richieste `code` quando non esiste un plugin linguaggio-specifico.

### Changed

- `code-Agent-CodeRouter` usa ora `code-Agent-Code` come fallback implementativo del master prima di ricorrere a `Agent-Research`.

### Compatibility

- Richiede `spark-base >= 1.1.0` e `spark-framework-engine >= 2.1.0`.

## [2.0.0] - 2026-04-15

### Changed

- Nuovo file `.github/AGENTS-master.md` per dichiarare gli agenti CORE-CRAFT del pacchetto.
- Il pacchetto diventa un plugin CORE-CRAFT sopra `spark-base`.
- Il manifest dichiara `dependencies: ["spark-base"]` e mantiene solo design, routing e contesto MCP.

### Removed

- Agenti base, instruction condivise, skill general-purpose e prompt framework migrati a `spark-base`.

### Compatibility

- Richiede `spark-base >= 1.0.0` e `spark-framework-engine >= 1.9.0`.

## [1.0.0] - 2026-04-10

### Added

- Prima release del layer master SCF.
- 7 agenti esecutori: Orchestrator v2.0, Git, Helper, Release, FrameworkDocs, Welcome, Research.
- 6 agenti dispatcher con fallback verso Agent-Research.
- Skill trasversali, instruction condivise e runtime state orchestratore.
- Supporto pattern multi-plugin M1 con `AGENTS-{plugin-id}.md`.

### Notes

- Richiede `spark-framework-engine >= 1.9.0`.
