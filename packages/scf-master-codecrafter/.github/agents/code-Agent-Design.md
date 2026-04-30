---
scf_merge_strategy: "replace"
name: code-Agent-Design
fallback: Agent-Research
version: 1.0.0
scf_owner: "scf-master-codecrafter"
role: dispatcher
delegates_to_capabilities: [design]
scf_file_role: "agent"
scf_version: "2.2.0"
layer: master
scf_merge_priority: 20
scf_protected: false
spark: true
model: ['Claude Sonnet 4.6 (copilot)', 'GPT-4o-mini (copilot)']
description: Dispatcher per decisioni architetturali e documenti di design con fallback research.
---

# code-Agent-Design

Dispatcher per decisioni architetturali e documenti di design.

## Istruzioni contestuali

- Per design su tool MCP, prompt framework o codice engine, considera `.github/instructions/mcp-context.instructions.md`.

Usa agenti plugin con capability `design`; in assenza di copertura, richiede ad Agent-Research un brief architetturale preliminare.