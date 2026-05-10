---
spark: true
scf_file_role: "config"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-ops"
scf_merge_priority: 15
---

<!-- markdownlint-disable MD024 -->

# Changelog - spark-ops

## [Unreleased]

### Added

- `spark-assistant` e `spark-guide` ora forniti da `spark-ops` (spostati da `spark-base`).

### Removed

- `Agent-Orchestrator` spostato in `spark-base` (agente core del ciclo E2E utente).
- Skill operative `error-recovery`, `semantic-gate`, `task-scope-guard` ora in `spark-base`.
- Prompt `orchestrate` ora in `spark-base`.

## [1.0.0] - 2026-05-10

### Added

- First release of the SPARK operational layer split from `spark-base`.
