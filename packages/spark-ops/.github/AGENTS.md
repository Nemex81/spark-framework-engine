---
spark: true
scf_file_role: "config"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-ops"
scf_merge_priority: 15
---

# AGENTS Index - spark-ops

## Operational Agents

- Agent-Orchestrator - executor - E2E orchestration, gates, runtime-state coordination
- Agent-FrameworkDocs - executor - framework docs, changelog, AGENTS index alignment
- Agent-Release - executor - semver, packaging guidance, release coordination

## Dependency Boundary

`spark-ops` depends on `spark-base` for shared policies, git guard rails, output style, and user-facing entrypoints.
`spark-base` must not depend on `spark-ops`.
