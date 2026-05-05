---
spark: true
name: code-Agent-CodeUI
version: 1.0.0
scf_owner: "scf-master-codecrafter"
scf_version: "2.6.0"
scf_file_role: "agent"
scf_merge_strategy: "replace"
scf_merge_priority: 20
scf_protected: false
description: Dispatcher per UI e accessibilita. Instrada richieste assistive verso agenti plugin.
model: ['Claude Sonnet 4.6 (copilot)', 'GPT-5.3-Codex (copilot)']
layer: master
role: dispatcher
delegates_to_capabilities: [code-ui, ui]
fallback: code-Agent-Research
---

# code-Agent-CodeUI

Dispatcher per richieste di UI, accessibilita e interazioni assistive.

Instrada verso agenti plugin che dichiarano capability `code-ui` o `ui`.
Se nessun plugin le espone, usa code-Agent-Research e segnala il gap di competenza nativa.
