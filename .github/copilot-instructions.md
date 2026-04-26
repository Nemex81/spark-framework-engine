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
- Skill disponibili: resource `skills://{nome-skill}` oppure `.github/skills/`
- Agenti disponibili: resource `scf://agents-index`
- Stato runtime: resource `scf://runtime-state`

## Sezione 5 - Update Policy e Ownership

- Il motore espone anche `scf_get_update_policy()` e `scf_set_update_policy(...)` per governare il comportamento di update del workspace.
- `scf_install_package(...)`, `scf_update_package(...)` e `scf_bootstrap_workspace(...)` possono ricevere `update_mode` e restituire `diff_summary`, `authorization_required` e `action_required` quando il workflow richiede un passaggio esplicito.
- I file condivisi con `scf_merge_strategy: merge_sections` devono passare dal percorso canonico `_scf_section_merge()`; i file `user_protected` non vanno sovrascritti implicitamente.
- Le scritture sotto `.github/` dipendono dallo stato sessione `github_write_authorized` in `.github/runtime/orchestrator-state.json`.
<!-- SCF:END:spark-framework-engine -->
<!-- SCF:BEGIN:spark-base@1.5.0 -->
---
spark: true
scf_file_role: "config"
scf_version: "1.5.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---

# Copilot Instructions — SPARK Base Package

## Contesto

Questo pacchetto fornisce il layer fondazionale del framework SCF.
Definisce agenti base, skill comuni, instruction condivise e regole operative
riutilizzabili da tutti i plugin linguaggio-specifici.

## Regole base

- Leggi sempre `.github/project-profile.md` prima di assumere stack o architettura.
- Usa `.github/AGENTS.md` come indice canonico degli agenti installati.
- Se una capability richiesta non è coperta da plugin attivi, usa `scf://agents-index`
	per verificare gli agenti disponibili, poi delega all'agente ricerca installato.
- Non modificare `.github/runtime/` tramite sistemi di manifest o ownership package.
- Per operazioni git, proponi i comandi senza eseguirli direttamente;
	delega all'agente git installato tramite `scf://agents-index`.
- Le capability language-specific devono essere fornite dai plugin installati sopra `spark-base`.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 2.4.0`; i tool e le resource runtime seguenti sono stati introdotti a partire da `1.5.0`:
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

- `@spark-assistant` — operazioni workspace: bootstrap, install/update/remove
	pacchetti, diagnostica stato framework.
- `@spark-engine-maintainer` — manutenzione motore: audit coerenza engine,
	aggiunta/rimozione tool MCP, revisione prompt, checklist pre-release.
- `@spark-guide` — orientamento: quale agente usare, quale pacchetto installare,
	routing verso spark-assistant per operazioni operative.

Gli agenti plugin (language-specific) vengono scoperti dinamicamente via
`scf://agents-index` che aggrega `AGENTS.md` e tutti i file `AGENTS-{plugin-id}.md`
presenti in `.github/`. Non referenziare agenti plugin per nome in questo file.

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.

## Tool MCP SPARK — Guida Operativa

Quando il server MCP SPARK è attivo, usa i tool seguenti invece di leggere
file direttamente o modificare `.github/` a mano.

### Lettura risorse framework

- Leggere stato runtime:
	→ `scf_get_runtime_state()`  oppure resource `scf://runtime-state`
- Leggere indice agenti installati:
	→ resource `scf://agents-index`
- Leggere un agente specifico:
	→ resource `agents://{nome-file-agente}`  (es. `agents://spark-assistant`)
- Leggere una skill specifica:
	→ resource `skills://{nome-skill}`  (es. `skills://conventional-commit`)
- Leggere un prompt specifico:
	→ resource `prompts://{nome-prompt}`
- Leggere una instruction specifica:
	→ resource `instructions://{nome-instruction}`
- Stato pacchetti installati:
	→ `scf_list_packages()`  oppure resource `scf://packages`
- Pacchetti disponibili nel registry:
	→ `scf_list_available_packages()`  oppure resource `scf://registry`

### Operazioni workspace

- Bootstrap workspace nuovo (prima installazione):
	→ `scf_bootstrap_workspace()`
	Sentinella di idempotenza: `.github/agents/spark-assistant.agent.md`
	Se la sentinella esiste, il bootstrap non sovrascrive file utente modificati.

- Installare un pacchetto:
	→ `scf_install_package(package_id)`
	Dopo l'esecuzione: il motore aggiorna automaticamente `copilot-instructions.md`
	aggiungendo il blocco `SCF:BEGIN:{package_id}` con `merge_sections`.

- Aggiornare un pacchetto:
	→ `scf_update_package(package_id)`
	Dopo l'esecuzione: il motore riscrive il blocco `SCF:BEGIN:{package_id}` esistente
	preservando i blocchi degli altri owner e il testo utente fuori dai marker.

- Rimuovere un pacchetto:
	→ `scf_remove_package(package_id)`
	Dopo l'esecuzione: il motore elimina il blocco `SCF:BEGIN:{package_id}` dal file.

- Verificare aggiornamenti disponibili:
	→ `scf_check_updates()`

- Leggere policy di update del workspace:
	→ `scf_get_update_policy()`

- Modificare policy di update:
	→ `scf_set_update_policy(mode)`  dove mode è: `"auto"` | `"confirm"` | `"manual"`

### Autorizzazione scritture su `.github/`

Prima di qualsiasi scrittura sotto `.github/`, verifica:
→ `scf_get_runtime_state()` → campo `github_write_authorized`

Se il campo è `false`, esegui:
→ `scf_update_runtime_state({"github_write_authorized": true})`

Non modificare `.github/runtime/orchestrator-state.json` direttamente.

### Regola invariante sul file `copilot-instructions.md`

Questo file è gestito con `scf_merge_strategy: merge_sections`.
Ogni blocco delimitato da `SCF:BEGIN:{owner}` / `SCF:END:{owner}` è di
proprietà esclusiva del pacchetto dichiarato nell'owner.
Il testo fuori dai marker è dello sviluppatore: il motore non lo tocca mai.
Non scrivere mai direttamente dentro un blocco di un altro owner.
Non generare blocchi SCF a mano: usa i tool engine sopra.
<!-- SCF:END:spark-base -->
<!-- SCF:BEGIN:scf-master-codecrafter@2.3.0 -->
---
spark: true
scf_file_role: "config"
scf_version: "2.3.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_merge_priority: 20
---

# Copilot Instructions — SCF Master CodeCrafter

## Contesto

Questo pacchetto fornisce il layer master programmatico del framework SCF.
Definisce gli agenti esclusivi di implementazione, design e routing del layer
master, insieme a skill contestuali e regole operative riutilizzabili dai
plugin linguaggio-specifici sopra `spark-base`.

## Regole base

- Leggi sempre `.github/project-profile.md` prima di assumere stack o architettura.
- Usa `.github/AGENTS.md` come indice canonico degli agenti installati.
- Se una capability richiesta non è coperta da plugin attivi, usa `scf://agents-index`
	per verificare gli agenti disponibili, poi delega all'agente ricerca installato.
- Non modificare `.github/runtime/` tramite sistemi di manifest o ownership package.
- Per operazioni git, proponi i comandi senza eseguirli direttamente;
	delega all'agente git installato tramite `scf://agents-index`.
- Per task su codice Python, test Python o contesto MCP, applica anche `.github/instructions/python.instructions.md`, `.github/instructions/tests.instructions.md` e `.github/instructions/mcp-context.instructions.md` quando pertinenti.

Queste instruction Python sono disponibili solo se il pacchetto `scf-pycode-crafter` e installato nel workspace.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 2.4.0`; i tool e le resource runtime seguenti sono stati introdotti a partire da `1.5.0`:
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

- Agenti condivisi da `spark-base`: scoperti tramite `scf://agents-index`.
	Coprono orchestrazione, git, release, framework docs, onboarding, ricerca,
	analyze, plan, docs e validate.
- Agente executor master: `code-Agent-Code` — implementazione codice.
- Agenti dispatcher master: `code-Agent-Design`, `code-Agent-CodeUI`, `code-Agent-CodeRouter`.
- Agenti plugin (language-specific): dichiarano `plugin`, `capabilities`, `languages`
	e vengono scoperti via `AGENTS-{plugin-id}.md` o tramite `scf://agents-index`.

Per verificare quali agenti sono effettivamente installati nel workspace corrente:
→ resource `scf://agents-index`

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.
<!-- SCF:END:scf-master-codecrafter -->
<!-- SCF:BEGIN:scf-pycode-crafter@2.1.0 -->
---
spark: true
scf_file_role: "config"
scf_version: "2.1.0"
scf_merge_strategy: "merge_sections"
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_merge_priority: 30
---
# Copilot Instructions — SCF Python CodeCrafter

## Contesto

Questo pacchetto aggiunge al framework SPARK il layer Python-specifico.
Definisce agenti dedicati, instruction file e regole operative per sviluppo,
test e review di codice Python. Richiede `spark-base` e `scf-master-codecrafter`
come prerequisiti.

## Runtime MCP richiesto

Questo layer richiede `spark-framework-engine >= 2.4.0`.
Instruction file attivate automaticamente:
- `python.instructions.md` — attiva su `*.py`
- `tests.instructions.md` — attiva su `tests/**/*.py`
- `mcp-context.instructions.md` — attiva quando il task tocca codice engine MCP

## Regole operative Python

- Usa gli agenti `py-Agent-*` per analisi, design, code, plan e validate su task Python.
- Applica sempre `.github/instructions/python.instructions.md` per file `*.py`.
- Applica anche `.github/instructions/tests.instructions.md` quando lavori in `tests/`.
- Mantieni type hints, docstring Google-style, `pathlib.Path`, pytest
	e gestione esplicita delle eccezioni.
- Nei test privilegia fixture pytest, isolamento dei casi e mock
	limitati alle dipendenze esterne.
- Quando il task tocca codice MCP (tool FastMCP, resource, decorator),
	applica `.github/instructions/mcp-context.instructions.md`.

## Routing degli agenti

- `py-Agent-Analyze` — analisi codice Python esistente.
- `py-Agent-Design` — progettazione strutture e architettura Python.
- `py-Agent-Code` — implementazione e refactoring codice Python.
- `py-Agent-Plan` — pianificazione task Python con TODO strutturato.
- `py-Agent-Validate` — review, lint e verifica standard.

Per verificare quali agenti py-* sono installati:
→ resource `scf://agents-index`

## Ownership e Update Policy

- Questo blocco viene integrato nel workspace tramite `merge_sections`.
- Non trattarlo come file single-owner sostitutivo.
- Le scritture sotto `.github/` richiedono `github_write_authorized: true`
	nel runtime state; usa `scf_get_runtime_state()` per verificare.

## Output

- Mantieni output testuale navigabile e NVDA-friendly.
- Usa il prefisso `ERRORE:` per blocchi critici.
- Preferisci report brevi con cosa cambia, perche e impatto operativo.
<!-- SCF:END:scf-pycode-crafter -->
