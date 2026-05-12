# SCF Universal Launcher v5.2 — Global Command Anywhere

## Panoramica

`scf` è disponibile globalmente da QUALSIASI directory senza import path manuali.
Funziona trovando automaticamente il motore SPARK Framework risalendo la directory tree.

---

## Installazione Symlink

### Linux / macOS

```bash
# Aggiungi /usr/local/bin/scf
sudo ln -sf /path/to/spark-framework-engine/scripts/scf_universal.py /usr/local/bin/scf
chmod +x /usr/local/bin/scf

# Oppure in .bashrc / .zshrc:
export PATH="/path/to/spark-framework-engine/scripts:$PATH"
```

### Windows (PowerShell)

Tre opzioni:

#### Opzione 1: Aggiungi PATH (consigliato)

```powershell
# In $PROFILE (PowerShell profile):
$env:PATH += ";C:\path\to\spark-framework-engine\scripts"

# Esegui da qualsiasi directory:
py scf_universal.py init
```

#### Opzione 2: Crea alias PowerShell

```powershell
# In $PROFILE:
function scf {
    python C:\path\to\spark-framework-engine\scripts\scf_universal.py @args
}

# Usa:
scf init
```

#### Opzione 3: Symlink (su Windows con permessi admin)

```powershell
# Come Administrator:
New-Item -ItemType SymbolicLink -Path "C:\Program Files\scf.py" `
  -Target "C:\path\to\spark-framework-engine\scripts\scf_universal.py"

py scf.py init
```

---

## Utilizzo

### Scenario 1: Workspace Vuoto (v5.2 — Auto-Setup Deps)

```powershell
# Da un workspace completamente vuoto (nessun .venv, nessun mcp installato)
cd C:\fightmanager
python ..\spark-framework-engine\scripts\scf_universal.py init

# Output automatico:
# Dipendenze SPARK non trovate nell'ambiente corrente.
# Configurazione automatica workspace: C:\fightmanager
# Creazione ambiente virtuale in C:\fightmanager\.venv ...
# Installazione dipendenze engine ...
# Setup dipendenze completato!
# Riavvio con ambiente configurato ...
# ============================================================
# SPARK Framework - Wizard di Onboarding v5.0
# ...
```

Il launcher:
1. Rileva che `mcp` non è disponibile
2. Crea `.venv` locale nel workspace
3. Installa deps engine (`requirements.txt` + editable install)
4. Riavvia se stesso con il Python del venv
5. Prosegue con la wizard

Idempotente: il sentinel `.scf-deps-ready` + `.venv` prevenuto reinstallazioni.

### Scenario 2: Primo Avvio (Ambiente con Deps)

```bash
cd /any/path/MyProject
scf init

# Output:
# SPARK Framework - Wizard di Onboarding v5.0
# [1/3] Lista pacchetti remoti disponibili
#   Comando: mcp scf_plugin_list_remote
# Scelta (1/0/q): 1
# ...
```

### Scenario 3: Workspace Esterno

```bash
cd ~/Progetti/MyApp
scf init --target .github

# Crea MyApp/.github/ + esegue wizard
```

### Scenario 4: Nested Directory

```bash
cd ~/Progetti/MyApp/src/components
scf init

# Auto-detect: workspace = ~/Progetti/MyApp
# Crea MyApp/.scf-init-done se completo
```

---

## Come Funziona (v5.2)

### Auto-Setup Dipendenze

Prima di qualsiasi import pesante, il launcher v5.2 controlla se `mcp` è disponibile:

1. `mcp` importabile → procede normalmente
2. `mcp` assente + `.scf-deps-ready` + `.venv/python` → riavvia con venv Python
3. `mcp` assente, nessun setup → crea `.venv`, installa deps, crea `.scf-deps-ready`, riavvia

Sentinel files nel workspace utente:
- `.scf-deps-ready` — dipendenze già installate
- `.scf-init-done` — wizard già completata

### Auto-Detection Cascata

1. **CLI flag** `--workspace /path` → directory esplicita
2. **ENV** `ENGINE_WORKSPACE` → env var
3. **ENV** `WORKSPACE_FOLDER` → Copilot/MCP
4. **Local Discovery** → `.vscode/settings.json`, `.github/agents` markers
5. **Fallback** → current working directory

### Engine Discovery

Il launcher risale l'albero directory fino a trovare `spark-framework-engine.py`:

```
/my/nested/project/src/components
  ↑
  └─ /my/nested/project
     └─ /my/nested
        └─ /my
           └─ / (filesystem root)  ← cerca spark-framework-engine.py
```

Quando trovato: aggiunge engine root a `sys.path`, importa `WorkspaceLocator`.

---

## Idempotenza

Il wizard crea il sentinel `.scf-init-done` nella root del workspace.
Le esecuzioni successive si interrompono immediatamente:

```
SPARK gia pronto! Usa: mcp scf_get_agent spark-assistant
```

---

## Troubleshooting

### "Engine non trovato"

**Causa**: Esecuzione da directory disconnessa dal repository SPARK.

**Soluzione**:
- Esegui da una directory dentro il repository
- Oppure imposta `ENGINE_WORKSPACE` o `--workspace` esplicitamente

```bash
export ENGINE_WORKSPACE=/path/to/workspace
scf init
```

### scf: command not found

**Causa**: Symlink o PATH non configurato.

**Soluzione**:
- Verifica symlink: `ls -la /usr/local/bin/scf` (Linux)
- Verifica PATH: `echo $PATH` (Linux) o `$env:PATH` (Windows)
- Riconfigurabella: vedi sezione "Installazione Symlink"

---

## Compatibilità

- **Python**: 3.8+ (scf_universal.py, stdlib only)
- **Windows**: ✓ py launcher, PowerShell native
- **Linux/macOS**: ✓ shebang native
- **Accessibilità**: NVDA-friendly (print() testuale, input() numerato)

---

## Referenza API

Per automazione:

```python
from pathlib import Path
import sys

# 1. Aggiungi engine a path
engine_root = find_engine_root()  # Tua implementazione
sys.path.insert(0, str(engine_root))

# 2. Importa e risolvi workspace
from spark.workspace.locator import WorkspaceLocator
locator = WorkspaceLocator(engine_root=engine_root)
context = locator.resolve()
workspace_root = context.workspace_root

# 3. Esegui wizard
from spark.boot.wizard import run_wizard
run_wizard(cwd=workspace_root)
```
