# MCP Setup

## Sezione 1 — Uso per singolo progetto
Configurazione in `.vscode/mcp.json` del workspace. Esempio:

```json
{
  "servers": {
    "sparkFrameworkEngine": {
      "type": "stdio",
      "command": "python",
      "args": [
        "${env:USERPROFILE}/.spark/spark-framework-engine.py"
      ]
    }
  }
}
```
Per Linux/macOS sostituire `${env:USERPROFILE}` con `${env:HOME}`.

## Sezione 2 — Uso globale su tutti i progetti
Configurare tramite comando VS Code `MCP: Open User Configuration`.
Path assoluto all'engine. Nessuna variabile d'ambiente richiesta.
Nota: in questa modalità `${workspaceFolder}` non viene interpolato da VS Code — SPARK usa MCP Roots automaticamente.

## Sezione 3 — Requisiti
- Python 3.10+
- `pip install mcp`
- Path engine corretto
