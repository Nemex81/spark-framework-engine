---
description: >
scf_protected: false
scf_file_role: "prompt"
name: Help Agente
scf_merge_priority: 20
scf_merge_strategy: "replace"
scf_version: "2.1.0"
spark: true
scf_owner: "scf-master-codecrafter"
---

Spiega come funziona l'agente ${input:Nome agente (es: code-Agent-Code, code-Agent-Design, Agent-Git...)}.

Se il nome richiesto e uno degli agenti condivisi forniti da `spark-base`
(`Agent-Orchestrator`, `Agent-Git`, `Agent-Helper`, `Agent-Release`,
`Agent-FrameworkDocs`, `Agent-Welcome`, `Agent-Research`, `Agent-Analyze`,
`Agent-Plan`, `Agent-Docs`, `Agent-Validate`), usa la definizione fornita da
`spark-base` nel workspace installato.

Se invece il nome richiesto e un agente esclusivo del master, leggi il file
`.github/agents/${input:Nome agente (es: code-Agent-Code, code-Agent-Design...)}.md`
e produci una spiegazione strutturata:

1. Scopo principale (1 riga)
2. Quando usarlo (trigger tipici)
3. Cosa produce in output
4. Gate di completamento
5. Comando per attivarlo direttamente
