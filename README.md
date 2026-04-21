# SPARK Framework Engine

Motore MCP universale per il **SPARK Code Framework (SCF)**.
Espone agenti, skill, instruction e prompt di qualsiasi progetto SCF-compatibile
come Resources e Tools consumabili da GitHub Copilot in Agent mode.

Il motore legge il `.github/` del progetto attivo dinamicamente —
non contiene dati di dominio, si adatta a qualsiasi progetto.

---

## Requisiti

- Python 3.10 o superiore
- VS Code con estensione GitHub Copilot
- Dipendenza runtime: `mcp` (include FastMCP)

---

## Quick Start (nuovo utente)

3 passi per iniziare da zero.

**Windows (PowerShell):**

```powershell
# 1. Clona il repo engine (una volta sola)
git clone https://github.com/Nemex81/spark-framework-engine
cd spark-framework-engine

# 2. Lancia setup puntando alla cartella del tuo progetto
.\setup.ps1 -Project "C:\percorso\mio-progetto"

# 3. Apri il progetto in VS Code
code "C:\percorso\mio-progetto"
```

**Mac / Linux (bash):**

```bash
# 1. Clona il repo engine (una volta sola)
git clone https://github.com/Nemex81/spark-framework-engine
cd spark-framework-engine

# 2. Lancia setup puntando alla cartella del tuo progetto
chmod +x setup.sh
./setup.sh /percorso/mio-progetto

# 3. Apri il progetto in VS Code
code /percorso/mio-progetto
```

Gli script `setup.ps1` / `setup.sh` eseguono in automatico:

- verifica Python 3.10+
- creazione del `.venv` locale nel repo engine (idempotente)
- `pip install mcp` nel venv
- esecuzione di `spark-init.py` nella cartella del progetto

Al termine VS Code avvierà il server SPARK automaticamente all'apertura del progetto.
Per orientarti nel repo engine usa la chat Copilot in Agent mode e scrivi `@spark-guide ciao`.

> Il progetto da inizializzare può essere una cartella vuota o un progetto esistente.
> `setup.ps1` / `setup.sh` sono idempotenti: possono essere rieseguiti senza danni.

---

## Installazione manuale

Se preferisci configurare senza gli script di setup:

```bash
# 1. Clona il repo engine in locale
git clone https://github.com/Nemex81/spark-framework-engine
cd spark-framework-engine

# 2. Installa la dipendenza
pip install mcp
```

## Primo avvio (manuale)

- Apri un terminale nella cartella del tuo progetto, non nella cartella
  del repo engine.

- Esegui `spark-init.py` puntando al clone locale dell'engine:

    ```bash
    python ../spark-framework-engine/spark-init.py
    ```

  Se il tuo progetto e il repo engine non sono allo stesso livello, usa il path
  assoluto al file `spark-init.py`.

- Lo script configura in autonomia il progetto utente:

  - crea o aggiorna `<progetto>.code-workspace`
  - crea o aggiorna `.vscode/mcp.json`
  - installa `spark-base` dal registry pubblico SCF e aggiorna `.github/.scf-manifest.json`

- Al termine stampa un riepilogo simile a questo:

    ```text
    [SPARK] .code-workspace → creato: mio-progetto.code-workspace
    [SPARK] .vscode/mcp.json → creato
    [SPARK] spark-base → installato
    ```

- Apri il progetto in VS Code in uno dei due modi supportati:

  - aprendo il file `.code-workspace` generato
  - oppure aprendo direttamente la cartella del progetto

  In entrambi i casi il server SPARK parte automaticamente.

- Se esegui di nuovo lo script sullo stesso progetto:

  - il `.code-workspace` viene aggiornato, non ricreato
  - `.vscode/mcp.json` viene aggiornato, non ricreato
  - `spark-base` viene rilevato dal manifest e non viene reinstallato
  - i warning e i dettagli operativi vengono inviati su `stderr`

### Configurazione manuale alternativa

Se preferisci non usare `spark-init.py`, puoi configurare il file
`.code-workspace` manualmente aggiungendo questo blocco alla radice
dell'oggetto JSON, fuori da `settings`:

```json
{
  "settings": {},
  "mcp": {
    "servers": {
      "sparkFrameworkEngine": {
        "type": "stdio",
        "command": "<path-python-venv>",
        "args": ["<path-spark-framework-engine.py>"],
        "env": {
          "WORKSPACE_FOLDER": "<path-assoluto-progetto>"
        }
      }
    }
  }
}
```

Se apri solo la cartella e non esegui `spark-init.py`, il server non parte
automaticamente perche manca la configurazione MCP nel progetto. In quel caso,
la soluzione consigliata resta eseguire `spark-init.py` dalla cartella utente.

Se nel log del server vedi comunque:

```text
WARNING: WORKSPACE_FOLDER env var not set
```

significa che il server non sa dove si trova il progetto attivo.

Da `1.8.1` il resolver del motore e piu difensivo: se `WORKSPACE_FOLDER`
manca o punta a una cartella palesemente non valida, il motore prova prima a
ricostruire il workspace dai marker locali (`.vscode/mcp.json`, `*.code-workspace`)
e poi dai marker SCF in `.github/`
prima di fare fallback sul `cwd`.

## Prima Configurazione

Per usare SPARK la prima volta in un workspace utente:

- Registra il motore MCP in VS Code come descritto sotto.
- Esegui `spark-init.py` nella cartella del progetto target.
- Apri il progetto target in VS Code usando il file `.code-workspace`
  generato oppure aprendo direttamente la cartella.

  Lo script prepara gia il set base sotto `.github/`:

  - installa il pacchetto `spark-base` dal registry pubblico
  - registra i file installati nel manifest runtime `.github/.scf-manifest.json`
  - lascia al motore MCP il caricamento dinamico di agenti, skill, instruction e prompt

- Usa `spark-assistant` come punto di ingresso operativo nel workspace bootstrap-pato.
- Usa `spark-guide` nel repo engine quando ti serve orientamento sul sistema e routing verso l'agente corretto.
- Per installare il primo plugin SCF, usa questo flusso:

  - consulta il catalogo con `scf_list_available_packages()`
  - controlla dettaglio, dipendenze e compatibilita con `scf_get_package_info(package_id)`
  - installa con `scf_install_package(package_id)`

- Dopo l'installazione, verifica lo stato locale con `scf_verify_workspace()`.
  I file condivisi intenzionalmente tra piu' pacchetti con `scf_merge_strategy: merge_sections`
  non vengono trattati come conflitti di ownership dal report di integrita'.

Il bootstrap eseguito da `spark-init.py` installa `spark-base` e registra i file
nel manifest runtime dei pacchetti. Per il bootstrap orchestrato dal motore MCP
e l'onboarding in un passo dall'interno di VS Code, usa
`scf_bootstrap_workspace(install_base=True)` una volta aperto il workspace.

---

## Registrazione in VS Code (globale)

Per usare il motore su tutti i tuoi progetti, registralo nelle impostazioni
utente globali di VS Code invece che nel singolo `.vscode/mcp.json`.

Aggiungi il blocco seguente al tuo `settings.json` utente
(`Ctrl+Shift+P` → "Open User Settings JSON"):

```json
"mcp": {
  "servers": {
    "sparkFrameworkEngine": {
      "type": "stdio",
      "command": "python",
      "args": [
        "/path/assoluto/spark-framework-engine/spark-framework-engine.py"
      ],
      "env": {
        "WORKSPACE_FOLDER": "${workspaceFolder}"
      }
    }
  }
}
```

Sostituisci `/path/assoluto/` con il percorso reale dove hai clonato il repo.

Per la registrazione per singolo progetto, vedi `mcp-config-example.json`.

---

## Come Funziona

Il motore legge la cartella `.github/` del workspace attivo in VS Code
e serve on-demand al modello AI (in Agent mode) tutto il contenuto SCF trovato.

| Meccanismo | Gestito da | Chi lo invoca |
|---|---|---|
| Slash command `/scf-*` | VS Code nativo da `.github/prompts/` | L'utente |
| Tool e Resource MCP | Questo motore | Il modello AI autonomamente |

---

## Resources Disponibili (15)

```
agents://list             agents://{name}
skills://list             skills://{name}
instructions://list       instructions://{name}
prompts://list            prompts://{name}
scf://global-instructions
scf://project-profile
scf://model-policy
scf://agents-index
scf://framework-version
scf://workspace-info
scf://runtime-state
```

## Tools Disponibili (35)

```
scf_list_agents           scf_get_agent(name)
scf_list_skills           scf_get_skill(name)

## Migrazione Da Workspace Pre-Ownership

Se il workspace e stato inizializzato con una versione precedente del sistema ownership-aware, il motore entra in modalita migrazione controllata.

- Se manca `.github/runtime/spark-user-prefs.json`, il primo `scf_update_package(...)` o `scf_bootstrap_workspace(...)` restituisce `action_required: configure_update_policy` e propone la configurazione iniziale della policy.
- I file provenienti da pacchetti legacy che non hanno metadata `scf_*` vengono trattati in modo retrocompatibile come `scf_merge_strategy: replace`.
- Se `.github/copilot-instructions.md` esiste senza marker SCF completi, il motore non inietta marker automaticamente: restituisce `action_required: migrate_copilot_instructions` e attende una conferma esplicita.
- La migrazione del file richiede sempre autorizzazione attiva per scrivere sotto `.github/`.
- Il testo utente fuori dai marker `SCF:BEGIN/END` viene preservato durante la migrazione esplicita.

FAQ rapida:

- Cosa succede ai miei file personalizzati?
  I file gia modificati dall'utente restano preservati dai flussi `integrative` e `conservative`. In `replace` viene creato prima un backup in `.github/runtime/backups/`.
- Il motore modifica da solo `copilot-instructions.md` legacy?
  No. Il file viene migrato solo se il chiamante passa una conferma esplicita nel flusso di tool.
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
scf_bootstrap_workspace(install_base=False)
scf_list_available_packages()
scf_get_package_info(package_id)
scf_list_installed_packages()
scf_install_package(package_id)
scf_plan_install(package_id)
scf_check_updates()
scf_update_package(package_id)
scf_update_packages()
scf_apply_updates(package_id | None)
scf_remove_package(package_id)
scf_get_package_changelog(package_id)
scf_finalize_update(session_id)
scf_resolve_conflict_ai(session_id, conflict_id)
scf_approve_conflict(session_id, conflict_id)
scf_reject_conflict(session_id, conflict_id)
```

`scf_get_update_policy()` restituisce la policy update del workspace, con source
(`file`, `default_missing`, `default_corrupt`) e configurazione effettiva.

`scf_set_update_policy(auto_update, default_mode=None, mode_per_package=None, mode_per_file_role=None)`
aggiorna `.github/runtime/spark-user-prefs.json` senza toccare i file dei pacchetti e
prepara il comportamento di installazione, update e bootstrap esteso.

`scf_bootstrap_workspace(install_base=False, conflict_mode="abort", update_mode="")` copia nel workspace utente il set base di bootstrap:
gli 9 prompt `scf-*.prompt.md`, gli agenti `spark-assistant.agent.md` e
`spark-guide.agent.md`, e l'instruction `spark-assistant-guide.instructions.md`.
Se il workspace e gia bootstrap-pato ma manca qualche asset base, il tool copia
solo i file mancanti.

Con `scf_bootstrap_workspace(install_base=True, conflict_mode=..., update_mode=...)` il motore puo
anche installare `spark-base` usando il normale preflight del registry e del manifest.
Se `spark-base` e gia installato, il passo viene saltato senza reinstallazione.
Quando `install_base=True`, il `conflict_mode` viene inoltrato a `scf_install_package`
cosi il bootstrap puo scegliere se preservare, sostituire o fondere i file gia presenti.
Se il workspace ha gia una policy esplicita, oppure il caller passa `update_mode`, il bootstrap
esteso costruisce anche il `diff_summary` di `spark-base`, verifica `github_write_authorized`
in `.github/runtime/orchestrator-state.json` e puo' richiedere prima l'autorizzazione o la
configurazione iniziale della policy.

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

Il nuovo sistema di ownership e update policy si appoggia a tre file runtime sotto `.github/runtime/`:

- `spark-user-prefs.json` per la policy del workspace
- `orchestrator-state.json` per l'autorizzazione sessione alle scritture protette
- `backups/<timestamp>/` per i backup automatici dei percorsi sostituiti

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
come source of truth per la prima inizializzazione. Se trova file gia presenti ma
non tracciati, chiede all'utente se vuole `replace`, `preserve` oppure un'integrazione
best-effort `integrate` prima di toccare il workspace.

---

## Architettura SCF

Questo motore è il Livello 1 dell’ecosistema SPARK Code Framework.
Per la documentazione completa del progetto vedi [SCF-PROJECT-DESIGN.md](SCF-PROJECT-DESIGN.md).

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

## Progetto Correlati

- [SCF-PROJECT-DESIGN.md](SCF-PROJECT-DESIGN.md) — documento di progettazione completo
- `scf-registry` — in sviluppo
- `scf-pack-gamedev` — in sviluppo
