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
