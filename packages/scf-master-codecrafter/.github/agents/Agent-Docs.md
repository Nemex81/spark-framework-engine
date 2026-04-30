---
spark: true
name: Agent-Docs
version: 1.0.0
description: Dispatcher per sincronizzazione documentazione del progetto ospite tramite agenti plugin.
model: ['GPT-5 mini (copilot)']
layer: master
role: dispatcher
delegates_to_capabilities: [docs]
fallback: Agent-Research
---

# Agent-Docs

Dispatcher per sincronizzazione documentazione del progetto ospite.

Instrada verso agenti plugin con capability `docs`.
Evita assunzioni su strumenti specifici come pytest, ruff o mypy.