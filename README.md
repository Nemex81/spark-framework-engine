# SPARK Framework Engine

Motore MCP universale per il **SPARK Code Framework (SCF)**.
Espone agenti, skill, instruction e prompt di qualsiasi progetto SCF-compatibile
come Resources e Tools consumabili da GitHub Copilot in Agent mode.

Il motore legge il `.github/` del progetto attivo dinamicamente —
non contiene dati di dominio, si adatta a qualsiasi progetto.

---

## Requisiti

- Python 3.10 o superiore
- Dipendenza runtime: `mcp` (include FastMCP)

---

## Installazione

```bash
# 1. Clona il repo
git clone https://github.com/Nemex81/spark-framework-engine
cd spark-framework-engine

# 2. Installa la dipendenza
pip install mcp
```

## Primo avvio

### Scenario A - Progetto nuovo, nessun .code-workspace

1. Apri un terminale nella cartella del tuo progetto.
2. Esegui:

```bash
python /path/to/spark-framework-engine/spark-init.py
```

3. Apri VS Code.
4. Usa File > Apri area di lavoro dal file.
5. Seleziona il file .code-workspace appena creato.
6. Riavvia il server MCP dal pannello MCP di VS Code.

### Scenario B - Progetto esistente con .code-workspace gia presente

Aggiungi manualmente questo blocco al tuo file .code-workspace, dentro "settings": {} allo stesso livello:

```json
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
```

In alternativa, esegui spark-init.py che lo aggiunge in automatico.

### Scenario C - Aperta solo la cartella senza workspace file

Se nel log del server vedi:

```text
WARNING: WORKSPACE_FOLDER env var not set
```

significa che il server non sa dove sei. Hai due opzioni:

- Opzione rapida: esegui spark-init.py nella cartella del progetto.
- Opzione manuale: crea il file .code-workspace come da Scenario B.

## Prima Configurazione

Per usare SPARK la prima volta in un workspace utente:

1. Registra il motore MCP in VS Code come descritto sotto.
1. Apri il progetto target in VS Code con la variabile `WORKSPACE_FOLDER` valorizzata dal server MCP.
1. Esegui `scf_bootstrap_workspace()` per creare il set base sotto `.github/`.

Il bootstrap crea questi asset:

- 8 prompt `scf-*.prompt.md`
- `spark-assistant.agent.md`
- `spark-assistant-guide.instructions.md`

1. Usa `spark-assistant` come punto di ingresso operativo nel workspace.
1. Per installare il primo plugin SCF, usa questo flusso:

- consulta il catalogo con `scf_list_available_packages()`
- controlla dettaglio, dipendenze e compatibilita con `scf_get_package_info(package_id)`
- installa con `scf_install_package(package_id)`

1. Dopo l'installazione, verifica lo stato locale con `scf_verify_workspace()`.

Il bootstrap non registra file nel manifest runtime dei pacchetti: prepara solo gli asset minimi di ingresso al sistema.

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

## Tools Disponibili (28)

```
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
scf_bootstrap_workspace()
scf_list_available_packages()
scf_get_package_info(package_id)
scf_list_installed_packages()
scf_install_package(package_id)
scf_check_updates()
scf_update_package(package_id)
scf_update_packages()
scf_apply_updates(package_id | None)
scf_remove_package(package_id)
scf_get_package_changelog(package_id)
```

`scf_bootstrap_workspace()` copia nel workspace utente il set base di bootstrap:
gli 8 prompt `scf-*.prompt.md`, l'agente `spark-assistant.agent.md` e
l'instruction `spark-assistant-guide.instructions.md`. Se il workspace e gia
bootstrap-pato ma manca qualche asset base, il tool copia solo i file mancanti.

`scf_get_package_info(package_id)` espone anche i campi del `package-manifest.json`
schema `2.0`, inclusi `min_engine_version`, `dependencies`, `conflicts`,
`file_ownership_policy` e `changelog_path`, insieme a una sezione di
compatibilita calcolata sul workspace attivo.

`scf_install_package(package_id)` esegue un preflight prima di scrivere file:
verifica compatibilita del motore, dipendenze dichiarate, conflitti di package
e ownership dei path gia tracciati nel manifest runtime. In caso di errore in
scrittura, tenta il rollback dei file appena toccati e non aggiorna il manifest
in modo parziale.

`scf_check_updates()` restituisce solo i pacchetti installati che risultano
aggiornabili rispetto al registry, con versione installata e versione disponibile.

`scf_update_package(package_id)` aggiorna un singolo pacchetto installato,
preservando i file modificati dall'utente e aggiornando il manifest locale con
nuove versioni e SHA-256 dei file sovrascritti.

`scf_update_packages()` non si limita piu a segnalare i delta di versione: costruisce
anche una preview ordinata del piano di update, includendo dipendenze tra package,
blocchi operativi e ordine di applicazione previsto.

`scf_apply_updates(package_id | None)` usa lo stesso piano dependency-aware per
aggiornare i package in ordine topologico. Se il piano e bloccato, il tool si ferma
prima di modificare il workspace e restituisce i motivi del blocco.

---

## Architettura SCF

Questo motore è il Livello 1 dell’ecosistema SPARK Code Framework.
Per la documentazione completa del progetto vedi [SCF-PROJECT-DESIGN.md](SCF-PROJECT-DESIGN.md).

```
Livello 1 — spark-framework-engine   ← questo repo (motore universale)
Livello 2 — scf-pack-*               (pacchetti dominio, repo separati)
Livello 3 — scf-registry             (indice centralizzato dei pacchetti)
```

---

## Progetto Correlati

- [SCF-PROJECT-DESIGN.md](SCF-PROJECT-DESIGN.md) — documento di progettazione completo
- `scf-registry` — in sviluppo
- `scf-pack-gamedev` — in sviluppo
