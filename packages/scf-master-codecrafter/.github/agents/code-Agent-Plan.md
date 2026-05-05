---
spark: true
name: code-Agent-Plan
version: 1.0.0
description: Dispatcher per breakdown implementativi e checklist operative con fallback research.
model: ['Claude Sonnet 4.6 (copilot)', 'GPT-5.4 (copilot)']
layer: master
role: dispatcher
delegates_to_capabilities: [plan]
fallback: code-Agent-Research
---

# code-Agent-Plan

Dispatcher per breakdown implementativi e checklist operative.

## Istruzioni contestuali

- Per piani che toccano tool MCP, prompt framework o codice engine, considera `.github/instructions/mcp-context.instructions.md`.

Usa agenti plugin con capability `plan`; se mancanti, produce un fallback tramite code-Agent-Research prima di proporre il piano.
