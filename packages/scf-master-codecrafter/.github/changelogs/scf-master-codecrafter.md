---
spark: true
scf_file_role: "config"
scf_version: "2.6.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_merge_priority: 20
---

# Changelog — scf-master-codecrafter

<!-- markdownlint-disable MD024 -->

## [Unreleased]

## [2.6.0] — agent-prefix-cleanup

### Changed

- Tutti gli agenti rinominati con prefisso `code-Agent-*` per evitare conflitti con agenti omonimi in `spark-base`.
- `mcp_resources.prompts` svuotato: tutti i 7 prompt erano duplicati di `spark-base`.
- Dipendenza `spark-base` aggiornata da `min_version 1.4.0` a `1.6.1`.
- Elenco agenti aggiornato in `AGENTS-master.md` e `copilot-instructions.md`.
- `files_metadata` aggiornato: tutti i file con `scf_version: "2.6.0"`.

### Added

- `code-Agent-Analyze`, `code-Agent-Docs`, `code-Agent-FrameworkDocs`, `code-Agent-Git`, `code-Agent-Helper`, `code-Agent-Plan`, `code-Agent-Research`: aggiunti al manifest e al bundle.

### Removed

- `Agent-Analyze`, `Agent-CodeRouter`, `Agent-CodeUI`, `Agent-Design`, `Agent-Docs`, `Agent-FrameworkDocs`, `Agent-Git`, `Agent-Helper`, `Agent-Plan`, `Agent-Research`: sostituiti dai corrispondenti `code-Agent-*`.
- `.github/prompts/*.prompt.md` (7 file): rimossi, ora forniti da `spark-base`.

### Cross-package alignment

- Le skill `clean-architecture` e `docs-manager` restano dipendenze cross-package fornite da `scf-master-codecrafter`; i riferimenti consumer in `spark-base` sono stati riallineati ai path reali basati su directory.
