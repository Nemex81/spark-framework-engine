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