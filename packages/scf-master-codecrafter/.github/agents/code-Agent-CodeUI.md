---
scf_merge_strategy: "replace"
name: code-Agent-CodeUI
fallback: Agent-Research
version: 1.0.0
scf_owner: "scf-master-codecrafter"
role: dispatcher
delegates_to_capabilities: [code-ui, ui]
scf_file_role: "agent"
scf_version: "2.2.0"
layer: master
scf_merge_priority: 20
scf_protected: false
spark: true
model: ['Claude Sonnet 4.6 (copilot)', 'GPT-5.3-Codex (copilot)']
description: Dispatcher per UI e accessibilita. Instrada richieste assistive verso agenti plugin.
---

# code-Agent-CodeUI

Dispatcher per richieste di UI, accessibilita e interazioni assistive.

Instrada verso agenti plugin che dichiarano capability `code-ui` o `ui`.
Se nessun plugin le espone, usa Agent-Research e segnala il gap di competenza nativa.