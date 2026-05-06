# Getting Started — SPARK Framework Engine

Guida completa all'installazione e alla prima configurazione del motore SPARK.

Per una panoramica del sistema, dei tool disponibili e dell'architettura,
consulta il [README.md](../README.md).

***

## Requisiti

> Vedi la sezione [Requisiti](../README.md#requisiti) nel README.

***

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
