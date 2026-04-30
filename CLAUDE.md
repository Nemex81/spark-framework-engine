# CLAUDE.md

Questo progetto utilizza il framework SPARK MCP.

## Come avviare il server MCP
- Esegui: `python spark-framework-engine.py`
- Il server espone tool MCP per agenti, skills, prompts, instructions.

## Risorse Gateway
- Gli agenti disponibili sono caricati tramite `.github/agents/` (Layer 0 gateway).
- Tutte le altre risorse sono accessibili via MCP (`agents://`, `skills://`, `prompts://`, `instructions://`).

## Contesto progetto
- Consulta `copilot-instructions.md` per dettagli Copilot.
- Consulta `docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md` per la strategia gateway.

---

Claude: usa solo Layer 0 per agenti, tutto il resto via MCP.
