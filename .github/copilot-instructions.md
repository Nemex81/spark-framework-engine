---
spark: true
scf_file_role: "config"
scf_version: "1.4.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

<!-- SCF:HEADER generato da SPARK Framework Engine -->
<!-- NON modificare i marker SCF. Il contenuto tra i marker è gestito dal sistema. -->
<!-- Il testo fuori dai marker è tuo: SPARK non lo tocca mai in nessuna modalità. -->

# Copilot Instructions — Workspace

<!-- Le tue istruzioni custom personali vanno QUI, sopra i blocchi SCF -->

<!-- SCF:BEGIN:spark-framework-engine@2.3.2 -->
---
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.2"
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
<!-- SCF:END:spark-framework-engine -->
<!-- SCF:BEGIN:spark-base@1.2.0 -->
---
spark: true
scf_file_role: "config"
scf_version: "1.2.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

# Copilot Instructions — spark-base

## Contesto

Questo pacchetto fornisce il layer fondazionale del framework SCF.
Definisce agenti base, skill comuni, instruction condivise e regole operative
riutilizzabili da tutti i plugin linguaggio-specifici.

## Regole base

- Leggi sempre `.github/project-profile.md` prima di assumere stack o architettura.
- Usa `.github/AGENTS.md` come indice canonico degli agenti installati.
- Se una capability richiesta non e coperta da plugin attivi, delega ad Agent-Research.
- Non modificare `.github/runtime/` tramite sistemi di manifest o ownership package.
- Per operazioni git, usa Agent-Git o proponi i comandi senza eseguirli direttamente.
- Le capability language-specific devono essere fornite dai plugin installati sopra `spark-base`.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 1.9.0`; i tool e le resource runtime seguenti sono stati introdotti a partire da `1.5.0`:
- `scf_get_runtime_state()`
- `scf_update_runtime_state(patch)`
- `scf://runtime-state`
- `scf://agents-index` in modalita multi-file `AGENTS*.md`

Quando il task tocca tool MCP o codice engine, mantieni separati `stdout` e `stderr` e verifica che i tool pubblici siano registrati con il decorator corretto.

## Ownership e Update Policy

- `copilot-instructions.md` di questo pacchetto e' un file condiviso con `scf_merge_strategy: merge_sections`: le modifiche devono preservare le sezioni degli altri owner.
- Il comportamento di installazione e update del workspace e' governato dai tool engine `scf_get_update_policy()` e `scf_set_update_policy(...)` e dal parametro `update_mode` dei tool pubblici.
- Se il motore restituisce `authorization_required` o `action_required`, il flusso corretto e' completare quel passaggio prima di promettere scritture sotto `.github/`.

## Routing degli agenti

- Agenti executor base: orchestrazione, git, release, framework docs, onboarding, ricerca.
- Agenti dispatcher base: analyze, plan, docs, validate.
- Agenti plugin: dichiarano `plugin`, `capabilities`, `languages` e vengono scoperti via `AGENTS-{plugin-id}.md`.

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.
<!-- SCF:END:spark-base -->
<!-- SCF:BEGIN:scf-master-codecrafter@2.1.0 -->
---
spark: true
scf_file_role: "config"
scf_version: "2.1.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_merge_priority: 20
---

# Copilot Instructions — SCF Master CodeCrafter

## Contesto

Questo pacchetto fornisce il layer master del framework SCF.
Definisce agenti trasversali, dispatcher, skill comuni e regole operative
riutilizzabili da tutti i plugin linguaggio-specifici.

## Regole base

- Leggi sempre `.github/project-profile.md` prima di assumere stack o architettura.
- Usa `.github/AGENTS.md` come indice canonico degli agenti installati.
- Se una capability richiesta non e coperta da plugin attivi, delega ad Agent-Research.
- Non modificare `.github/runtime/` tramite sistemi di manifest o ownership package.
- Per operazioni git, usa Agent-Git o proponi i comandi senza eseguirli direttamente.
- Per task su codice Python, test Python o contesto MCP, applica anche `.github/instructions/python.instructions.md`, `.github/instructions/tests.instructions.md` e `.github/instructions/mcp-context.instructions.md` quando pertinenti.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 2.1.0`; i tool e le resource runtime seguenti sono stati introdotti a partire da `1.5.0`:
- `scf_get_runtime_state()`
- `scf_update_runtime_state(patch)`
- `scf://runtime-state`
- `scf://agents-index` in modalita multi-file `AGENTS*.md`

Quando il task tocca tool MCP o codice engine, mantieni separati `stdout` e `stderr` e verifica che i tool pubblici siano registrati con il decorator corretto.

## Ownership e Update Policy

- `copilot-instructions.md` di questo pacchetto viene integrato nel workspace tramite `merge_sections`; non trattarlo come file single-owner sostitutivo.
- I flussi `scf_install_package(...)`, `scf_update_package(...)` e `scf_bootstrap_workspace(...)` possono richiedere `update_mode`, autorizzazione `.github` e policy workspace prima delle scritture effettive.
- Quando descrivi o usi il sistema di update del workspace, fai riferimento ai tool `scf_get_update_policy()` e `scf_set_update_policy(...)` invece di suggerire modifiche manuali a `.github/runtime/`.

## Routing degli agenti

- Agenti executor master: orchestrazione, git, release, framework docs, onboarding, ricerca.
- Agenti dispatcher master: analyze, design, plan, docs, code-ui, code-router.
- Agenti plugin: dichiarano `plugin`, `capabilities`, `languages` e vengono scoperti via `AGENTS-{plugin-id}.md`.

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.
<!-- SCF:END:scf-master-codecrafter -->
<!-- SCF:BEGIN:scf-pycode-crafter@2.0.1 -->
---
spark: true
scf_file_role: "config"
scf_version: "2.0.1"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_merge_priority: 30
---
## Istruzioni SCF Python CodeCrafter

Questo pacchetto aggiunge al framework le regole operative e gli agenti Python-specifici.

- Usa gli agenti `py-Agent-*` per analisi, design, code, plan e validate su task Python.
- Applica sempre `.github/instructions/python.instructions.md` per file `*.py`.
- Applica anche `.github/instructions/tests.instructions.md` quando lavori in `tests/`.
- Mantieni type hints, docstring, `pathlib.Path`, pytest e gestione esplicita delle eccezioni.
- Nei test privilegia fixture pytest, isolamento dei casi e mock limitati alle dipendenze esterne.
<!-- SCF:END:scf-pycode-crafter -->
# Copilot Instructions — SPARK Base Package
Questo layer richiede `spark-framework-engine >= 2.4.0`; i tool e le resource runtime seguenti sono stati introdotti a partire da `1.5.0`:
Nota cross-layer: alcuni agenti con prefisso `code-` (ad es. `code-Agent-Code`,
`code-Agent-CodeRouter`, `code-Agent-CodeUI`, `code-Agent-Design`) sono forniti
dal pacchetto `scf-master-codecrafter`. In un workspace dove `scf-master-codecrafter`
non è installato, i riferimenti a questi agenti saranno link morti — questo è il
comportamento atteso per agenti di layer superiore. Per comportamenti runtime
corretti, installa `scf-master-codecrafter` o aggiorna i riferimenti locali.
