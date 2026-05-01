---
# SPARK Gateway Pattern — Piano Tecnico Implementativo

## Sezione 1: Architettura Gateway (invariante)

### Diagramma testuale

```
[.github/agents/spark-assistant.agent.md] --(loader)--> [MCP: scf_get_agent()]
[.github/agents/spark-guide.agent.md] --(onboarding)--> [MCP: scf_list_available_agents()]
[workspace user] --(richiesta)--> [Layer 0] --(pull)--> [Layer 1 MCP] --(proxy)--> [Layer 2 pacchetti]
```

### Tabella architettura

| Layer  | Dove risiede                | Cosa contiene                                               | Chi lo gestisce         |
|--------|-----------------------------|-------------------------------------------------------------|-------------------------|
| 0      | .github/ (workspace)        | spark-assistant.agent.md, spark-guide.agent.md,             | Engine (bootstrap)      |
|        |                             | spark-assistant-guide.instructions.md, scf-*.prompt.md      |                         |
| 1      | MCP server (engine + pkg)   | Tutti gli agenti, skills, prompts, instructions dei pacchetti| Engine MCP              |
| 2      | Registry pacchetti SCF      | Pacchetti installabili, versioni, risorse aggiuntive        | Registry + Engine       |

---

## Sezione 2: Intervento 1 — File gateway Layer 0

### .github/agents/spark-assistant.agent.md
- **Scopo**: Agente gateway che recupera risorse SPARK via MCP e le inietta nella sessione.
- **Frontmatter obbligatorio**:
	- spark: true
	- scf_file_role: "agent"
	- scf_owner: "spark-framework-engine"
	- tools: [scf_get_agent, scf_get_skill, scf_get_prompt, scf_get_instruction, scf_list_installed_packages, scf_list_available_agents]
- **Body**: Sezioni H2 obbligatorie:
	- Come recuperare un agente
	- Come recuperare una skill
	- Come recuperare un prompt
	- Pacchetti installati
	- Nota operativa
- **Tool MCP da usare**: scf_get_agent, scf_get_skill, scf_get_prompt, scf_list_installed_packages, scf_list_available_agents

### .github/agents/spark-guide.agent.md
- **Scopo**: Agente di onboarding che guida l’utente nella scoperta e uso del framework.
- **Frontmatter obbligatorio**:
	- spark: true
	- scf_file_role: "agent"
	- scf_owner: "spark-framework-engine"
	- tools: [scf_list_installed_packages, scf_list_available_agents, scf_workspace_info, scf_bootstrap_workspace, scf_get_registry]
- **Body**: Sezioni H2 obbligatorie:
	- Prima sessione su un workspace
	- Scoperta risorse
	- Installazione pacchetti
- **Tool MCP da usare**: scf_list_installed_packages, scf_list_available_agents, scf_workspace_info, scf_bootstrap_workspace, scf_get_registry

---

## Sezione 3: Intervento 2 — Refactor scf_bootstrap_workspace

- **Comportamento da mantenere**: idempotenza tramite sentinella spark-assistant.agent.md
- **Comportamento da modificare**: il set di file copiati deve essere ESATTAMENTE:
	- agents/spark-assistant.agent.md
	- agents/spark-guide.agent.md
	- instructions/spark-assistant-guide.instructions.md (se presente)
	- prompts/scf-*.prompt.md (pattern glob)
- **Logica di verifica**: se un file è già presente E modificato dall’utente (sha256 diverso), non sovrascrivere e loggare warning su stderr
- **Punto di inserimento**: dopo la riga `def scf_bootstrap_workspace` (~riga 7379)

---

## Sezione 4: Intervento 3 — Riscrittura CLAUDE.md

**Contenuto richiesto:**

- **Sezione MCP Server**: come avviare, path file engine, transport stdio
- **Sezione URI Schema**: elenco completo schemi supportati con esempio (agents://, skills://, prompts://, instructions://, scf://)
- **Sezione Tool MCP principali**: scf_get_agent, scf_get_skill, scf_get_prompt, scf_list_installed_packages, scf_bootstrap_workspace (descrizione 1 riga ciascuno)
- **Sezione Risorse Layer 0**: elenco file in .github/ con scopo
- **Sezione Come interrogare le risorse**: esempio concreto di prompt per Claude

---

## Sezione 5: Criteri di accettazione verificabili

- scf_bootstrap_workspace copia solo i 4 file gateway; verifica eseguendo il tool su un workspace vuoto e controllando che .github/agents/ contenga solo spark-assistant.agent.md e spark-guide.agent.md
- Se spark-assistant-guide.instructions.md non è presente nell’engine, non viene copiato
- Se un file gateway è già presente e modificato dall’utente (sha256 diverso), non viene sovrascritto
- CLAUDE.md contiene tutte le sezioni richieste, senza placeholder
- I file agent gateway hanno frontmatter e body come da specifica
