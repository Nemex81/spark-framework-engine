---
spark: true
name: Agent-Design
version: 1.0.0
scf_owner: "scf-master-codecrafter"
scf_version: "2.5.1"
scf_file_role: "agent"
scf_merge_strategy: "replace"
scf_merge_priority: 20
scf_protected: false
description: Dispatcher per decisioni architetturali e documenti di design con fallback research.
model: ['Claude Sonnet 4.6 (copilot)', 'GPT-4o-mini (copilot)']
layer: master
role: dispatcher
delegates_to_capabilities: [design]
fallback: Agent-Research
---

# Agent-Design

Dispatcher per decisioni architetturali e documenti di design.

## Istruzioni contestuali

- Per design su tool MCP, prompt framework o codice engine, considera `.github/instructions/mcp-context.instructions.md`.

Usa agenti plugin con capability `design`; in assenza di copertura, richiede ad Agent-Research un brief architetturale preliminare.