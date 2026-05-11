<!-- markdownlint-disable MD022 MD031 MD040 MD060 -->

# SPARK Framework Engine

Motore MCP universale per il **SPARK Code Framework (SCF)**.
Espone agenti, skill, instruction e prompt di qualsiasi progetto SCF-compatibile
come Resources e Tools consumabili da GitHub Copilot in Agent mode.

Il motore legge il `.github/` del progetto attivo dinamicamente —
non contiene dati di dominio, si adatta a qualsiasi progetto.

> **Versione corrente:** 3.3.0 (09 maggio 2026). Per le note di migrazione
> consultare il [CHANGELOG.md](CHANGELOG.md).

---

## Requisiti

- Python 3.11 o superiore
- VS Code con estensione GitHub Copilot
- Dipendenza runtime: `mcp` (include FastMCP)

---

## Installazione e Primo Avvio

Per la guida completa all'installazione, al primo avvio e alla
configurazione del workspace, consulta:

→ **[docs/getting-started.md](docs/getting-started.md)**

---

## Come Funziona

Il motore legge la cartella `.github/` del workspace attivo in VS Code
e serve on-demand al modello AI (in Agent mode) tutto il contenuto SCF trovato.

| Meccanismo | Gestito da | Chi lo invoca |
|---|---|---|
| Slash command `/scf-*` | VS Code nativo da `.github/prompts/` | L'utente |
| Tool e Resource MCP | Questo motore | Il modello AI autonomamente |

---

## Resources Disponibili (19)

```
agents://list             agents://{name}
skills://list             skills://{name}
instructions://list       instructions://{name}
prompts://list            prompts://{name}
engine-skills://list      engine-skills://{name}       (alias deprecato → skills://)
engine-instructions://list engine-instructions://{name} (alias deprecato → instructions://)
scf://global-instructions
scf://project-profile
scf://model-policy
scf://agents-index
scf://framework-version
scf://workspace-info
scf://runtime-state
```

> Il conteggio 19 si riferisce alle resources engine-side registrate staticamente.
> Il numero effettivo a runtime è superiore perché i pacchetti installati registrano
> risorse aggiuntive al boot tramite `_v3_repopulate_registry()`.

## Tools Disponibili (50)

```
scf_list_overrides(resource_type=None)
scf_read_resource(uri, source="auto")
scf_get_skill_resource(name)
scf_get_instruction_resource(name)
scf_get_agent_resource(name)
scf_get_prompt_resource(name)
scf_override_resource(uri, content)
scf_drop_override(uri)
scf_list_agents           scf_get_agent(name)
scf_list_skills           scf_get_skill(name)
scf_list_instructions     scf_get_instruction(name)
scf_list_prompts          scf_get_prompt(name)
scf_get_project_profile   scf_get_global_instructions
scf_get_model_policy      scf_get_framework_version (restituisce `engine_version` e le versioni dei pacchetti installati)
scf_get_workspace_info
scf_verify_workspace()
scf_verify_system()
scf_get_runtime_state()
scf_update_runtime_state(patch)
scf_get_update_policy()
scf_set_update_policy(auto_update, default_mode=None, mode_per_package=None, mode_per_file_role=None)
scf_bootstrap_workspace(install_base=False, conflict_mode="abort", update_mode="", migrate_copilot_instructions=False, force=False, dry_run=False)
scf_migrate_workspace(dry_run=True, force=False)
scf_list_available_packages()
scf_get_package_info(package_id)
scf_list_installed_packages()
scf_install_package(package_id)
scf_plan_install(package_id)
scf_check_updates()
scf_update_package(package_id, conflict_mode, update_mode="")
scf_update_packages()
scf_apply_updates(package_id | None)
scf_remove_package(package_id)
scf_get_package_changelog(package_id)
scf_finalize_update(session_id)
scf_resolve_conflict_ai(session_id, conflict_id)
scf_approve_conflict(session_id, conflict_id)
scf_reject_conflict(session_id, conflict_id)
scf_plugin_install(pkg_id)
scf_plugin_remove(pkg_id)
scf_plugin_update(pkg_id)
scf_plugin_list()
scf_list_plugins()
scf_install_plugin(package_id, version="latest", workspace_root="", overwrite=False)
```

### Nota sui tool legacy

I tool `scf_list_plugins()` e `scf_install_plugin()` sono **deprecati** a favore
di `scf_plugin_list()` e `scf_plugin_install()` (introdotti nella v3.0).
Rimangono disponibili per retrocompatibilità ma con la segnalazione nei payload
`deprecated: true` e `removal_target_version: "3.4.0"` (due minor release dopo
l'attuale 3.2.0). Il campo `migrate_to` nei return block specifica il tool
sostitutivo esplicito. I client dovrebbero transitare verso i nuovi tool nelle
prossime versioni.

## Architettura — Pacchetti interni vs Plugin Workspace

Il motore espone due **Universi** distinti di componenti:

- **Universo A (MCP-Only)**: i pacchetti `spark-base`, `spark-ops`,
  `scf-master-codecrafter` e `scf-pycode-crafter` sono serviti esclusivamente via MCP dallo store engine
  centralizzato. Non generano file nel workspace utente. Accesso tramite
  resource URI `agents://`, `skills://`, `instructions://`, `prompts://`.
  `spark-base` copre bootstrap/onboarding/workflow utente; `spark-ops` copre
  orchestrazione E2E, framework docs e release coordination.
- **Universo B (Plugin Workspace)**: i plugin esterni (category "plugin") e i
  pacchetti con `delivery_mode: "file"` possono installare file fisici nel
  workspace utente tramite `scf_plugin_install()` o `scf_install_package()`.
  Il file editing avviene direttamente nel filesystem di VS Code.

Per il dettaglio operativo dei flussi e l'elenco dei tool MCP correlati a
ciascun Universo, consulta l'agente `spark-assistant`: la sezione
"Architettura — pacchetti interni vs plugin workspace" è la fonte canonica
per questo argomento.

## Migrazione Da Workspace Pre-Ownership

Se il workspace e stato inizializzato con una versione precedente del sistema ownership-aware, il motore entra in modalita migrazione controllata.

- Se manca `.github/user-prefs.json`, il primo `scf_update_package(...)` o `scf_bootstrap_workspace(...)` restituisce `action_required: configure_update_policy` e propone la configurazione iniziale della policy.
- I file provenienti da pacchetti legacy che non hanno metadata `scf_*` vengono trattati in modo retrocompatibile come `scf_merge_strategy: replace`.
- Se `.github/copilot-instructions.md` esiste senza marker SCF completi, il motore non inietta marker automaticamente: restituisce `action_required: migrate_copilot_instructions` e attende una conferma esplicita.
- La migrazione del file richiede sempre autorizzazione attiva per scrivere sotto `.github/`.
- Il testo utente fuori dai marker `SCF:BEGIN/END` viene preservato durante la migrazione esplicita.

FAQ rapida:

- Cosa succede ai miei file personalizzati?
  I file gia modificati dall'utente restano preservati dai flussi `integrative` e `conservative`. In `replace` viene creato prima un backup in `.github/runtime/backups/`.
- Il motore modifica da solo `copilot-instructions.md` legacy?
  No. Il file viene migrato solo se il chiamante passa una conferma esplicita nel flusso di tool.

`scf_get_update_policy()` restituisce la policy update del workspace, con source
(`file`, `default_missing`, `default_corrupt`) e configurazione effettiva.

`scf_set_update_policy(auto_update, default_mode=None, mode_per_package=None, mode_per_file_role=None)`
aggiorna `.github/user-prefs.json` senza toccare i file dei pacchetti e
prepara il comportamento di installazione, update e bootstrap esteso.

`scf_bootstrap_workspace(install_base=False, conflict_mode="abort", update_mode="", migrate_copilot_instructions=False, force=False, dry_run=False)` copia nel workspace utente il set base di bootstrap:
i 13 prompt `scf-*.prompt.md`, gli agenti `spark-assistant.agent.md` e
`spark-guide.agent.md`, e l'instruction `spark-assistant-guide.instructions.md`.
Se il workspace e gia bootstrap-pato ma manca qualche asset base, il tool copia
solo i file mancanti.

Il bootstrap non copia il file assemblato `.github/copilot-instructions.md` del motore.
Quel file arriva nel workspace solo tramite installazione o update dei pacchetti
SCF che contribuiscono sezioni `merge_sections`; il blocco interno
`spark-framework-engine` resta quindi confinato al repository del motore.

Con `scf_bootstrap_workspace(install_base=True, conflict_mode=..., update_mode=...)` il motore puo
anche installare `spark-base` usando il normale preflight del registry e del manifest.
Se `spark-base` e gia installato, il passo viene saltato senza reinstallazione.
Quando `install_base=True`, il `conflict_mode` viene inoltrato a `scf_install_package`
cosi il bootstrap puo scegliere se preservare, sostituire o fondere i file gia presenti.
Se il workspace ha gia una policy esplicita, oppure il caller passa `update_mode`, il bootstrap
esteso costruisce anche il `diff_summary` di `spark-base`, verifica `github_write_authorized`
in `.github/runtime/orchestrator-state.json` e puo' richiedere prima l'autorizzazione o la
configurazione iniziale della policy.

Se `install_base=True`, l'eventuale creazione o aggiornamento di `.github/copilot-instructions.md`
avviene nel flusso di installazione del pacchetto tramite merge delle sezioni distribuite dal package,
non tramite copia del file assemblato del motore.

**Nota payload:** il dizionario di ritorno non è uniforme tra tutti i rami di esecuzione.
I campi garantiti in ogni ramo sono: `success`, `status`, `files_written`, `preserved` e `workspace`.
I campi estesi (`action_required`, `authorization_required`, `github_write_authorized`,
`diff_summary`, `phase6_assets`, `base_install`, `policy_created`) sono presenti solo
nei rami pertinenti (flusso autorizzazione, bootstrap esteso, installazione base).

`scf_get_package_info(package_id)` espone anche i campi del `package-manifest.json`
schema `2.0`, inclusi `min_engine_version`, `dependencies`, `conflicts`,
`file_ownership_policy` e `changelog_path`, insieme a una sezione di
compatibilita calcolata sul workspace attivo.

`scf_install_package(package_id, conflict_mode="abort", update_mode="")` esegue un preflight
prima di scrivere file: verifica compatibilita del motore, dipendenze dichiarate,
conflitti di package, ownership dei path gia tracciati nel manifest runtime e
collisioni con file `.github/` esistenti ma non tracciati. Il `conflict_mode`
controlla il comportamento in caso di conflitto:

- `abort` (default): blocca i conflitti irrisolti.
- `replace`: sovrascrive i file in conflitto in modo esplicito.
- `manual`: apre una sessione interattiva per risolvere ogni conflitto singolarmente.
- `auto`: il motore tenta una risoluzione best-effort deterministica e degrada a `manual` se il caso non e sicuro.
- `assisted`: apre una sessione con marker su disco e permette approvazione/rifiuto per singolo conflitto.

Il parametro `update_mode` governa invece la strategia package-level nel nuovo sistema
ownership-aware:

- `integrative`: prova a integrare i file compatibili con merge o sezione condivisa.
- `replace`: forza il percorso sostitutivo e crea un backup automatico dei file toccati.
- `conservative`: privilegia la preservazione dei file gia modificati localmente.
- `selective`: segnala che il workspace richiede una scelta esplicita prima di procedere.
- stringa vuota: usa la policy del workspace (`mode_per_package` → `mode_per_file_role` → `default_mode`).

In caso di errore in scrittura, il tool tenta il rollback dei file appena toccati
e non aggiorna il manifest in modo parziale.

Quando il flusso policy e attivo, il payload include anche:

- `resolved_update_mode` e `update_mode_source`
- `diff_summary` senza i file `unchanged`
- `authorization_required` / `github_write_authorized`
- `backup_path` per i percorsi `replace`

Per i package manifest schema `3.1`, l'installazione distingue esplicitamente
tre categorie nel payload v3:

- `mcp_services_activated`: URI MCP attivati dal package (`agents://`,
  `skills://`, `instructions://`, `prompts://`)
- `workspace_files_written`: file editor-binding dichiarati in `workspace_files`
- `plugin_files_installed`: file fisici dichiarati in `plugin_files`, installati
  nel workspace con lo stesso preservation gate dei `workspace_files`

La chiave `installed` resta presente come alias deprecato dei file fisici scritti
nel workspace per compatibilita con client esistenti.

`scf_plan_install(package_id)` restituisce un'anteprima read-only del risultato
di installazione: file scrivibili, file da preservare, conflitti che richiedono
una decisione esplicita e, per i merge mode, una preview del piano di merge.

`scf_check_updates()` restituisce solo i pacchetti installati che risultano
aggiornabili rispetto al registry, con versione installata e versione disponibile.

`scf_update_package(package_id, conflict_mode, update_mode="")` aggiorna un singolo pacchetto
installato, preservando i file modificati dall'utente. Supporta gli stessi
`conflict_mode` di `scf_install_package`: `abort`, `replace`, `manual`, `auto`,
`assisted`, e usa lo stesso `update_mode` package-level del flusso di installazione.

`scf_update_packages()` non si limita piu a segnalare i delta di versione: costruisce
anche una preview ordinata del piano di update, includendo dipendenze tra package,
blocchi operativi e ordine di applicazione previsto.

`scf_apply_updates(package_id | None, conflict_mode="abort")` usa lo stesso piano dependency-aware per
aggiornare i package in ordine topologico. Prima di scrivere, esegue un preflight
su tutti i target del batch e si ferma se rileva conflitti irrisolti, restituendo
il dettaglio dei package bloccati. Il `conflict_mode` viene poi inoltrato a ogni
installazione del batch, cosi gli update possono usare `replace` per sovrascrivere
o `manual` / `auto` / `assisted` per fondere i file utente modificati.

`scf_finalize_update(session_id)` finalizza una sessione di merge aperta in modo
`manual` o `assisted`, applicando le decisioni confermate ai file del workspace e
aggiornando il manifest.

`scf_resolve_conflict_ai(session_id, conflict_id)` propone automaticamente una
risoluzione conservativa per un singolo conflitto aperto, validandola prima di
renderla approvabile.

`scf_approve_conflict(session_id, conflict_id)` approva la risoluzione proposta
per un conflitto nella sessione, marcandolo come risolto.

`scf_reject_conflict(session_id, conflict_id)` rifiuta la risoluzione proposta,
lasciando il file in fallback manuale con marker di conflitto.

## Gestione Update Workspace

Il nuovo sistema di ownership e update policy usa i seguenti file runtime:

- `.github/user-prefs.json` — policy update del workspace
- `.github/runtime/orchestrator-state.json` — autorizzazione sessione alle scritture protette
- `{engine_root}/runtime/{hash[:12]}/` — directory engine-local per snapshot, sessioni di merge e backup (path calcolato da `resolve_runtime_dir` in `spark/boot/validation.py`; sovrascrivibile con la variabile d'ambiente `SPARK_RUNTIME_DIR`)

### Flusso a 6 step

1. Lettura della policy workspace con fallback sicuro ai default.
2. Costruzione del `diff_summary` sui file target, escludendo gli `unchanged`.
3. Verifica dell'autorizzazione `.github` tramite `github_write_authorized`.
4. Risoluzione del `update_mode` effettivo o richiesta di scelta esplicita.
5. Backup automatico prima dei percorsi `replace`.
6. Scrittura file-level con `replace`, 3-way merge oppure `_scf_section_merge()` sui file condivisi.

### Modalita di aggiornamento

| update_mode | Effetto principale |
|---|---|
| `integrative` | Integra i file quando possibile e usa i merge gia supportati dal motore |
| `replace` | Sovrascrive i file target e salva backup automatici |
| `conservative` | Evita overwrite impliciti sui file toccati dall'utente |
| `selective` | Richiede una scelta esplicita prima della scrittura |
| `ask` | Default user-facing della policy: nessuna scrittura finche l'utente non sceglie |

Per i workspace nuovi o migrati, `scf_bootstrap_workspace(..., update_mode=...)` puo' creare la policy iniziale,
mentre `scf_set_update_policy(...)` permette di aggiornarla in seguito senza reinstallare pacchetti.

---

## Sistema di Merge a 3 Vie

A partire dalla versione `2.0.0`, il motore supporta il merge a 3 vie per file
markdown durante installazione e aggiornamento di pacchetti.

Il merge combina tre versioni: il **BASE** (snapshot salvato all'installazione
precedente), la **versione utente** (modifiche locali) e la **nuova versione
pacchetto** (contenuto aggiornato nel registry).

### Modalita disponibili

| conflict_mode | Comportamento |
|---|---|
| `abort` | Blocca se esistono conflitti irrisolti (default) |
| `replace` | Sovrascrive sempre con la versione pacchetto, anche sui file tracciati e modificati |
| `manual` | Apre sessione interattiva, decisione per ogni conflitto |
| `auto` | Il motore risolve in autonomia via euristiche AI |
| `assisted` | Proposta automatica, conferma utente per conflitti a bassa confidenza |

### Flusso sessione manual / assisted

```
scf_install_package / scf_update_package (conflict_mode="manual")
  → sessione aperta → session_id restituito

scf_approve_conflict(session_id, conflict_id)   ← accetta ogni conflitto
scf_reject_conflict(session_id, conflict_id)    ← rifiuta e mantieni versione utente
scf_resolve_conflict_ai(session_id, conflict_id) ← delega all'AI integrata

scf_finalize_update(session_id)  ← applica le decisioni e chiude la sessione
```

Per i merge `auto`, il motore chiude automaticamente solo i casi che passano le
euristiche conservative e i validator; i casi ambigui vengono degradati a una
sessione manuale attiva.

Lo script standalone `spark-init.py` usa il `package-manifest.json` di `spark-base`
come source of truth user-facing per la prima inizializzazione. Le risorse
operative opzionali sono invece fornite da `spark-ops`. Se trova file gia presenti ma
non tracciati, chiede all'utente se vuole `replace`, `preserve` oppure un'integrazione
best-effort `integrate` prima di toccare il workspace.

---
## Registry e Pacchetti (HTTPS-first)

Il motore ottiene il registro dei pacchetti SCF e i file dei pacchetti
esclusivamente via HTTPS da GitHub. Non è necessario clonare i repository
dei pacchetti localmente — il motore gestisce tutto tramite tool MCP.

**Registry principale (fonte di verità per `scf_list_available_packages`):**

```
https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json
```

**Pacchetti disponibili (plugin indipendenti per il `.github/` dell'utente):**

| Pacchetto | Repository |
|---|---|
| `spark-base` | https://github.com/Nemex81/spark-base |
| `scf-master-codecrafter` | https://github.com/Nemex81/scf-master-codecrafter |
| `scf-pycode-crafter` | https://github.com/Nemex81/scf-pycode-crafter |

> Il motore scarica i file di ciascun pacchetto da `raw.githubusercontent.com`
> al momento dell'installazione e li memorizza nella store locale
> (`packages/{id}/.github/`). L'utente non deve gestire i repository dei
> pacchetti: usa `scf_install_package(id)`, `scf_update_package(id)` e
> `scf_remove_package(id)`.

---
## Architettura SCF

Questo motore è il Livello 1 dell’ecosistema SPARK Code Framework.
Per la documentazione completa del progetto vedi [SCF-PROJECT-DESIGN.md](docs/archivio/SCF-PROJECT-DESIGN.md) (documento di progettazione originale, archiviato).

```
Livello 1 — spark-framework-engine   ← questo repo (motore universale)
Livello 2 — scf-pack-*               (pacchetti dominio, repo separati)
Livello 3 — scf-registry             (indice centralizzato dei pacchetti)
```
### Ownership dei file `.github/` del motore

I file `.github/` di questo repo seguono lo stesso schema ownership che il motore applica ai workspace utente:

- **File nativi engine**: agenti, skill, instruction e prompt specifici del motore hanno `scf_owner: "spark-framework-engine"`.
- **File shadow di pacchetti**: i prompt `scf-*.prompt.md` e l'agente `spark-guide.agent.md` appartengono a `spark-base` e sono riallineati al contenuto del pacchetto sorgente con `scf_owner: "spark-base"`.
- **File condivisi**: `.github/copilot-instructions.md` è un file `merge_sections` con sezioni `SCF:BEGIN/END` per tutti i pacchetti installati e serve da implementazione di riferimento del formato canonico.

---

## Contribuire

Le procedure per rinominare agenti SCF, aggiungere/rimuovere tool MCP e gestire
fixture pytest condivise sono documentate in:

→ **[CONTRIBUTING.md](CONTRIBUTING.md)**

---

## Progetto Correlati

- [SCF-PROJECT-DESIGN.md](docs/archivio/SCF-PROJECT-DESIGN.md) — documento di progettazione originale (archiviato)
- `scf-registry` — in sviluppo
- `scf-pack-gamedev` — in sviluppo
