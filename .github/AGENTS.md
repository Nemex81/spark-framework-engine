---
spark: true
scf_file_role: "config"
scf_version: "1.2.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

# AGENTS Index

## Base Agents (spark-base)

- spark-assistant — executor — workspace entrypoint, onboarding, package lifecycle, diagnostics
- spark-engine-maintainer — executor — manutenzione engine, diagnostica e operazioni di mantenimento framework
- spark-guide — executor — user entrypoint, framework orientation, routing to spark-assistant

## Plugin Agents

Questa sezione viene popolata dai plugin installati tramite file `AGENTS-{plugin-id}.md`.
Il motore aggrega i file disponibili tramite `scf://agents-index`.

## MCP Runtime Tools (engine v2.4.0 — feature introdotte tra v1.5.0 e v1.6.0)

I tool seguenti sono disponibili e operativi nel motore corrente (v2.4.0).

### Runtime State (da v1.5.0)

- `scf_get_runtime_state()` — legge `.github/runtime/orchestrator-state.json`
- `scf_update_runtime_state(patch)` — aggiorna lo stato runtime dell'orchestratore con merge parziale
- `scf://runtime-state` — resource JSON con lo stato runtime corrente
- `scf://agents-index` — aggrega `AGENTS.md` e `AGENTS-{plugin-id}.md`

### Package Management (da v1.6.0)

- `scf_check_updates()` — restituisce solo i pacchetti installati con aggiornamento disponibile
- `scf_update_package(package_id)` — aggiorna un singolo pacchetto preservando i file modificati dall'utente

***

## Agenti di Supporto Interno

Al momento non sono presenti agenti di supporto interno aggiuntivi oltre ai tre agenti SCF-native elencati sopra.
