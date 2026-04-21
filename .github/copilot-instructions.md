---
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "config"
scf_merge_strategy: "merge_sections"
scf_merge_priority: 0
scf_protected: false
---
# Copilot Instructions - spark-framework-engine

## Sezione 1 - Contesto repo

- Questo repository contiene il motore MCP universale del SPARK Code Framework.
- Linguaggio principale: Python 3.11+.
- Framework MCP usato: FastMCP.
- File principale: spark-framework-engine.py.

## Sezione 2 - Quando usare @spark-engine-maintainer

Usare @spark-engine-maintainer per:
- audit di coerenza interna del motore
- aggiunta o rimozione tool MCP
- creazione o revisione prompt in .github/prompts/
- aggiornamento CHANGELOG e ENGINE_VERSION dopo modifiche
- checklist pre-release e proposta tag
- aggiornamento README e documentazione di design/piano

## Sezione 2bis - Quando usare @spark-guide

Usare @spark-guide per:
- orientamento iniziale sul sistema SPARK e sui suoi componenti
- richieste user-facing su quale agente o pacchetto usare
- routing verso `spark-assistant` per operazioni workspace come bootstrap, installazione, aggiornamento o rimozione pacchetti
- chiarimento del perimetro tra agente guida, assistant workspace e maintainer engine

## Sezione 3 - Cosa NON delegare a @spark-engine-maintainer

Non delegare a @spark-engine-maintainer:
- operazioni su workspace utente (installazione pacchetti SCF, setup progetto)
- sviluppo feature non legate al motore SCF
- operazioni su altri repository

Per richieste user-facing o di orientamento operativo sul framework, usa invece @spark-guide.

## Sezione 4 - Riferimenti istruzioni operative

- Convenzioni motore: .github/instructions/spark-engine-maintenance.instructions.md
- Skill disponibili: .github/skills/scf-*/SKILL.md

## Sezione 5 - Update Policy e Ownership

- Il motore espone anche `scf_get_update_policy()` e `scf_set_update_policy(...)` per governare il comportamento di update del workspace.
- `scf_install_package(...)`, `scf_update_package(...)` e `scf_bootstrap_workspace(...)` possono ricevere `update_mode` e restituire `diff_summary`, `authorization_required` e `action_required` quando il workflow richiede un passaggio esplicito.
- I file condivisi con `scf_merge_strategy: merge_sections` devono passare dal percorso canonico `_scf_section_merge()`; i file `user_protected` non vanno sovrascritti implicitamente.
- Le scritture sotto `.github/` dipendono dallo stato sessione `github_write_authorized` in `.github/runtime/orchestrator-state.json`.
