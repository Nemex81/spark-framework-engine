# SPARK Init Wizard — Guida Utente

## Panoramica

`scf init` e' il comando zero-touch per inizializzare un workspace SPARK in meno di 2 minuti.
Esegui un solo comando dopo `git clone` e il wizard ti guida in modo interattivo attraverso
i passi di configurazione obbligatori.

---

## Avvio rapido

### Linux / macOS

```bash
git clone <tuo-repo>
cd <tuo-repo>
python scripts/scf init
```

### Windows (PowerShell)

```powershell
git clone <tuo-repo>
cd <tuo-repo>
py scripts/scf init
# oppure
python scripts/scf init
```

---

## Passi guidati

Il wizard propone 3 passi in sequenza. Per ogni passo puoi scegliere:

| Input | Azione         |
|-------|----------------|
| `1`   | Esegui il passo |
| `0`   | Salta il passo  |
| `q`   | Esci dal wizard |

### Passo 1 — Lista pacchetti remoti

```
[1/3] Lista pacchetti remoti disponibili
    Comando: mcp scf_plugin_list_remote
Scelta (1/0/q): 1
```

Interroga il registry SCF per mostrare i pacchetti disponibili.

### Passo 2 — Installa scf-master-codecrafter

```
[2/3] Installa scf-master-codecrafter
    Comando: mcp scf_plugin_install_remote scf-master-codecrafter
Scelta (1/0/q): 1
```

Installa il pacchetto master che attiva tutti gli agenti code nel workspace.

### Passo 3 — Apri VSCode in Agent Mode

```
[3/3] Apri VSCode in Agent Mode
    Comando: code .
Scelta (1/0/q): 1
```

Apre VS Code nella directory corrente, pronto per usare Copilot Agent Mode.

---

## Idempotenza

Il wizard e' idempotente: una volta completato, crea il file sentinel `.scf-init-done`
nella root del workspace. Le esecuzioni successive si interrompono immediatamente
con il messaggio:

```
SPARK gia pronto! Usa: mcp scf_get_agent spark-assistant
```

Per forzare una nuova esecuzione, rimuovi manualmente il sentinel:

```bash
rm .scf-init-done          # Linux/macOS
Remove-Item .scf-init-done # Windows PowerShell
```

---

## Accessibilita' NVDA

Il wizard e' progettato per essere pienamente navigabile con screen reader NVDA su Windows:

- Tutti i messaggi usano `print()` testuale puro (nessun carattere unicode decorativo).
- Ogni passo mostra etichetta e comando su righe separate.
- I prompt `input()` usano opzioni numeriche esplicite `(1/0/q)`.

---

## Struttura dei file

| File                        | Scopo                                      |
|-----------------------------|--------------------------------------------|
| `scripts/scf`               | Launcher eseguibile (entry point CLI)      |
| `spark/boot/wizard.py`      | Logica wizard interattiva (testabile)      |
| `spark/cli/__init__.py`     | Bridge dispatcher CLI                      |
| `.scf-init-done`            | Sentinel di idempotenza (generato dal wizard) |

---

## Dipendenze

Nessuna dipendenza esterna. Il wizard usa solo moduli della stdlib Python:
`os`, `sys`, `pathlib`.

---

## Esecuzione diretta di wizard.py

Il modulo `spark/boot/wizard.py` puo' essere eseguito anche direttamente:

```bash
python spark/boot/wizard.py
py spark/boot/wizard.py    # Windows
```

---

## Riferimento API (uso nei test)

```python
from spark.boot.wizard import run_wizard

# Esecuzione in directory temporanea con input fittizio
result = run_wizard(cwd=some_path, _input=lambda _: "0")
# result == {"step_1": "skipped", "step_2": "skipped", "step_3": "skipped"}
```
