# Getting Started — SPARK Framework Engine

Guida completa all'installazione e alla prima configurazione del motore SPARK.

Per una panoramica del sistema, dei tool disponibili e dell'architettura,
consulta il [README.md](../README.md).

***

## Scelta di Percorso

- **Preferisci eseguire da qualsiasi directory senza cd manuali?**
  → Vedi [SCF Universal Launcher v5.1](#scf-universal-launcher-v51)

- **Preferisci setup classico con script dedicato?**
  → Vedi [Quick Start Classico](#quick-start-classico)

***

## SCF Universal Launcher v5.1

**Esecuzione zero-touch da QUALSIASI directory:**

```bash
cd /qualsiasi/percorso/mio-progetto
scf init
```

### Setup (una volta sola)

**Linux/macOS:**

```bash
# Aggiungi a PATH
ln -sf /path/to/spark-framework-engine/scripts/scf_universal.py /usr/local/bin/scf
# Verifica
which scf
```

**Windows (PowerShell):**

```powershell
# Opzione 1: Aggiungi a $PROFILE
$env:PATH += ";C:\path\to\spark-framework-engine\scripts"

# Opzione 2: Usa alias
function scf {
    python C:\path\to\spark-framework-engine\scripts\scf_universal.py @args
}

# Verifica
scf --help  # (opzionale, il comando esiste)
```

### Come Funziona

Il launcher `scf init`:
1. Trova automaticamente il motore SPARK risalendo la directory tree
2. Rileva il workspace attivo (cwd, env var, markers locali)
3. Esegue la wizard interattiva 3-step
4. Crea `.scf-init-done` al termine (idempotente)

Per documenti dettagliato → [docs/SCF-GLOBAL.md](SCF-GLOBAL.md)

***

## Quick Start Classico

### Requisiti

- Python 3.11 o superiore
- VS Code con estensione GitHub Copilot
- Git

### Nuovi Utenti — 3 Passi

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

***

## Installazione manuale

Se preferisci configurare senza gli script di setup:

```bash
# 1. Clona il repo engine in locale
git clone https://github.com/Nemex81/spark-framework-engine
cd spark-framework-engine

# 2. Avvia l'inizializzazione dal tuo progetto con Python 3.10+
python /percorso/al/repo/spark-framework-engine/spark-init.py
```

Se `.venv` non esiste ancora nel repo engine, `spark-init.py` la crea al volo e installa
automaticamente `mcp` nel runtime locale prima di scrivere la configurazione MCP.

***

## Primo avvio (manuale)

- Apri un terminale nella cartella del tuo progetto, non nella cartella
  del repo engine.

- Esegui `spark-init.py` puntando al clone locale dell'engine:

    ```bash
    python ../spark-framework-engine/spark-init.py
    ```

  Se il tuo progetto e il repo engine non sono allo stesso livello, usa il path
  assoluto al file `spark-init.py`.

  Se il repo engine non ha ancora `.venv`, lo script prepara automaticamente il
  runtime locale richiesto dal server SPARK usando l'interprete Python con cui lo avvii.

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

***

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

### MCP Service Mode e Plugin Mode

I pacchetti SCF schema `3.1` possono usare due modalita contemporaneamente:

- **MCP Service Mode**: agenti, skill, instruction e prompt restano nello store
  dell'engine e vengono serviti via URI MCP come `agents://...` o `skills://...`.
- **Plugin Mode**: i file dichiarati in `workspace_files` e `plugin_files` vengono
  scritti fisicamente nel workspace sotto `.github/`, tracciati dal manifest e
  protetti dal preservation gate se l'utente li modifica.

Nel risultato di `scf_install_package`, `mcp_services_activated` mostra le risorse
MCP attivate, `workspace_files_written` mostra gli editor-binding scritti e
`plugin_files_installed` mostra i file plugin fisici installati.

- Dopo l'installazione, verifica lo stato locale con `scf_verify_workspace()`.
  I file condivisi intenzionalmente tra piu' pacchetti con `scf_merge_strategy: merge_sections`
  non vengono trattati come conflitti di ownership dal report di integrita'.

Il bootstrap eseguito da `spark-init.py` installa `spark-base` e registra i file
nel manifest runtime dei pacchetti. Per il bootstrap orchestrato dal motore MCP
e l'onboarding in un passo dall'interno di VS Code, usa
`scf_bootstrap_workspace(install_base=True)` una volta aperto il workspace.

***

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
