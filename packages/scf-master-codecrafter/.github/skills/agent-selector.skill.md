---
spark: true
name: agent-selector
description: Seleziona l'agente corretto in base a task, capability e plugin attivi.
---

# agent-selector

## Regole di selezione

- Setup o profilo progetto: Agent-Welcome.
- Orchestrazione multi-fase: Agent-Orchestrator.
- Git: Agent-Git.
- Documentazione framework: Agent-FrameworkDocs.
- Capability plugin disponibile: dispatcher corrispondente.
- Capability assente: Agent-Research.