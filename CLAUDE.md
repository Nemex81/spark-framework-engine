# CLAUDE.md

## MCP Server

- Avvio: `python spark-framework-engine.py`
- File engine: `spark-framework-engine.py` (root repo)
- Transport: stdio (JSON-RPC)

## URI Schema supportati

- `agents://<nome>` — Recupera un agente dal registry MCP (es: `agents://spark-assistant`)
- `skills://<nome>` — Recupera una skill (es: `skills://changelog-entry`)
- `prompts://<nome>` — Recupera un prompt (es: `prompts://scf-release-check`)
- `instructions://<nome>` — Recupera una instruction (es: `instructions://python.instructions`)
- `scf://<resource>` — Risorsa di sistema (es: `scf://agents-index`)

## Tool MCP principali

- `scf_get_agent` — Recupera un agente per nome
- `scf_get_skill` — Recupera una skill per nome
- `scf_get_prompt` — Recupera un prompt per nome
- `scf_list_installed_packages` — Elenca i pacchetti installati
- `scf_bootstrap_workspace` — Esegue il bootstrap Layer 0 nel workspace

## Risorse Layer 0

- `.github/agents/spark-assistant.agent.md` — Gateway loader agenti
- `.github/agents/spark-guide.agent.md` — Onboarding e discovery
- `.github/instructions/spark-assistant-guide.instructions.md` — Istruzioni operative (se presente)
- `.github/prompts/scf-*.prompt.md` — Prompt di sistema (pattern)

## Come interrogare le risorse

Esempio prompt per Claude:

> "Recupera l'agente `spark-assistant` via MCP usando `scf_get_agent(name="spark-assistant")` e inietta le sue istruzioni nella sessione corrente."
