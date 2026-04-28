---
title: Smoke Test Copilot v3.0 — Report
status: DEFERRED
date: 2026-04-28
---

# Smoke Test Copilot v3.0 — Report

## Stato

**DEFERRED** — I task 7.4–7.10 della Fase 7 sono smoke test manuali
che richiedono interazione diretta con l'IDE VS Code Insiders (chat
Copilot, dropdown agenti, "Add Context > MCP Resources") e con un
workspace di test isolato. Non possono essere eseguiti dall'agente
Copilot in modalità autonoma.

## Test rinviati

| ID | Smoke test | Tipo | Esito |
| --- | --- | --- | --- |
| 7.4 | Preparazione workspace test (engine v3.0.0-rc1) | Setup manuale | PENDING |
| 7.5 | Bootstrap genera AGENTS.md correttamente | UI manuale | PENDING |
| 7.6 | Copilot riconosce agenti nel dropdown | UI manuale | PENDING |
| 7.7 | MCP Resources accessibili da picker Copilot | UI manuale | PENDING |
| 7.8 | Ciclo override completo (write → read → drop) | UI/MCP manuale | PENDING |
| 7.9 | Install + remove pacchetto aggiorna AGENTS.md | UI/MCP manuale | PENDING |
| 7.10 | Migrazione workspace v2.x reale (dry-run + apply) | UI/MCP manuale | PENDING |

## Coverage automatica equivalente

I comportamenti core sono comunque coperti dalla suite pytest:

- Bootstrap → AGENTS.md: `tests/test_phase6_bootstrap_assets.py`
  (16 test, inclusi safe-merge, plugin AGENTS-{pkg}.md, .clinerules).
- Override cycle: `tests/test_override_tools.py` e
  `tests/test_manifest_manager.py::TestOverrideCycleV3`.
- Resource aliases / engine vs override priority:
  `tests/test_resource_aliases.py`.
- Manifest schema v3.0 + backward read v2.x:
  `tests/test_manifest_manager.py` (10 test).
- Bootstrap end-to-end: `tests/test_bootstrap_workspace.py`.

## Esecuzione manuale richiesta prima del rilascio

Lo sviluppatore (utente finale del repo) deve eseguire i test
7.4–7.10 in un workspace di test pulito prima di pubblicare v3.0.0
e aggiornare questo file marcando ciascun test come PASS/FAIL e
allegando eventuali screenshot o log rilevanti in
`docs/screenshots/v3-smoke/`.

## Pre-requisiti suite pytest (automatica)

Comando di regressione:

```pwsh
.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

Esito attuale: **272 passed** (28 aprile 2026).
