---
spark: true
scf_file_role: "config"
scf_version: "1.0.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "user"
scf_merge_priority: 0
---
# Copilot Instructions — Workspace Gateway

Questo workspace utilizza il Gateway Pattern SPARK.

- Gli agenti disponibili sono caricati tramite `.github/agents/` (Layer 0 gateway).
- Tutte le altre risorse (skills, prompts, instructions) sono accessibili via MCP (`agents://`, `skills://`, `prompts://`, `instructions://`).
- Consulta `docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md` per dettagli.

Per caricare un agente:
- Usa il loader gateway (`spark-assistant.agent.md` o `spark-guide.agent.md`)
- Per risorse aggiuntive, invoca i tool MCP corrispondenti.

---

Non modificare questo file manualmente salvo istruzioni specifiche dal piano gateway.
