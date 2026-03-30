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

## Resources Disponibili (14)

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
```

## Tools Disponibili (20)

```
scf_list_agents           scf_get_agent(name)
scf_list_skills           scf_get_skill(name)
scf_list_instructions     scf_get_instruction(name)
scf_list_prompts          scf_get_prompt(name)
scf_get_project_profile   scf_get_global_instructions
scf_get_model_policy      scf_get_framework_version
scf_get_workspace_info
scf_list_available_packages()
scf_get_package_info(package_id)
scf_list_installed_packages()
scf_install_package(package_id)
scf_update_packages()
scf_apply_updates(package_id | None)
scf_remove_package(package_id)
```

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
