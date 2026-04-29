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