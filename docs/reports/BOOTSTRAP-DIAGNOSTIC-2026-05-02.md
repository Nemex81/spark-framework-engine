# SPARK — Analisi Diagnostica Bootstrap Workspace
**Data:** 2026-05-02  
**Versione engine:** 3.1.0  
**Commit di riferimento:** 0e24e17 (HEAD)  
**Modalità:** Analisi statica read-only — nessuna modifica apportata

---

## 1. Inventario file sorgenti analizzati

| File | Scopo |
|------|-------|
| `spark/boot/engine.py` | `SparkFrameworkEngine` — tool `scf_bootstrap_workspace` |
| `spark/boot/sequence.py` | `_build_app` — catena di avvio completa |
| `spark/workspace/locator.py` | `WorkspaceLocator.resolve()` — risoluzione workspace |
| `spark/core/constants.py` | Costanti globali, `_BOOTSTRAP_PACKAGE_ID` |
| `.github/agents/` | File agenti engine (sorgenti bootstrap) |
| `.github/instructions/` | File instruction engine (sorgenti bootstrap) |
| `.github/prompts/` | File prompt engine (sorgenti bootstrap) |
| `mcp-config-example.json` | Configurazione MCP di riferimento |
| `spark-framework-engine.py` | Entry point — `__main__` |

---

## 2. Inventario contenuto cartelle engine

### `.github/agents/` (4 file)

```
spark-assistant.agent.md    ← FILE SENTINELLA
spark-engine-maintainer.agent.md
spark-guide.agent.md
spark-welcome.agent.md
```

### `.github/instructions/` (9 file)

```
framework-guard.instructions.md
git-policy.instructions.md
model-policy.instructions.md
personality.instructions.md
project-reset.instructions.md
spark-assistant-guide.instructions.md   ← copiata da bootstrap
spark-engine-maintenance.instructions.md
verbosity.instructions.md
workflow-standard.instructions.md
```

### `.github/prompts/` (29 file — solo i `scf-*.prompt.md` vengono copiati)

I file che corrispondono al glob `scf-*.prompt.md` (11 file confermati):
```
scf-check-updates.prompt.md
scf-install.prompt.md
scf-list-available.prompt.md
scf-list-installed.prompt.md
scf-migrate-workspace.prompt.md
scf-package-info.prompt.md
scf-pre-implementation-audit.prompt.md
scf-remove.prompt.md
scf-status.prompt.md
scf-update-policy.prompt.md
scf-update.prompt.md
```

---

## 3. Costanti rilevanti (`spark/core/constants.py`)

| Costante | Valore |
|----------|--------|
| `_BOOTSTRAP_PACKAGE_ID` | `"scf-engine-bootstrap"` — owner manifest per i file copiati durante bootstrap |
| `ENGINE_VERSION` | `"3.1.0"` |
| `_MANIFEST_FILENAME` | `".scf-manifest.json"` |

---

## 4. Risposte alle domande diagnostiche

---

### D1 — Il bootstrap è automatico?

**Risposta: NO**

Il bootstrap non viene mai invocato automaticamente durante l'avvio del server.

**Evidenza — `spark/boot/sequence.py`, righe 119–155:**

```python
app = SparkFrameworkEngine(mcp, context, inventory, runtime_dir=runtime_dir)
app.register_resources()   # riga ~150
app.register_tools()       # riga ~151
_log.info("Tools registered: 44 total")
return mcp
```

La sequenza di boot (`_build_app`) costruisce `SparkFrameworkEngine`, registra
risorse e tool, e restituisce l'app MCP. Non c'è nessuna chiamata a
`scf_bootstrap_workspace` né a qualsiasi metodo che copi file nel workspace.

Il tool `scf_bootstrap_workspace` è registrato come normale tool MCP (riga
`3748` di `spark/boot/engine.py`) ed è puramente passivo: deve essere
invocato esplicitamente da Copilot (tramite l'agente `spark-assistant`) o
dall'utente tramite prompt `/scf-install`.

**Impatto:** Se il workspace utente non ha ancora `.github/`, il server si
avvia correttamente ma non crea nulla. Copilot non troverà nessun agente
perché `.github/agents/` non esiste nel workspace.

---

### D2 — `engine_root` vs `workspace_root`: sono distinti?

**Risposta: SÌ — sono path separati e indipendenti**

**Evidenza — `spark/workspace/locator.py`, righe 207–220:**

```python
github_root = workspace_root / ".github" if workspace_root else None
# engine_root è sempre la directory del file engine, indipendente dal workspace.
# Valore passato esplicitamente dal chiamante (nessun Path(__file__) qui).
engine_root: Path = self._engine_root

return WorkspaceContext(
    workspace_root=workspace_root,   # ← cartella progetto aperto in VS Code
    github_root=github_root,         # ← workspace/.github/
    engine_root=engine_root,         # ← directory dove risiede spark-framework-engine.py
)
```

**Evidenza — `spark-framework-engine.py`, riga ~194:**

```python
if __name__ == "__main__":
    _build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")
```

`engine_root` è sempre la directory del file `spark-framework-engine.py`.
`workspace_root` è la directory del progetto utente, determinata da
`WorkspaceLocator.resolve()`. Sono **due path distinti**.

**In `scf_bootstrap_workspace` (`spark/boot/engine.py`, righe ~3805–3812):**

```python
engine_github_root = self._ctx.engine_root / ".github"     # sorgente
workspace_github_root = self._ctx.github_root              # destinazione
```

La direzione di copia è inequivocabile: da `engine_root/.github/` (sorgente)
a `workspace_root/.github/` (destinazione).

**Impatto:** La separazione è corretta. Il problema non è architetturale qui,
ma legato alla risoluzione del `workspace_root` (vedi D6).

---

### D3 — La sorgente del bootstrap esiste?

**Risposta: SÌ — i file sorgente sono presenti**

Tutti i file che `scf_bootstrap_workspace` dovrebbe copiare esistono fisicamente
nell'engine:

| File sorgente | Presente |
|---------------|----------|
| `.github/agents/spark-assistant.agent.md` | ✓ |
| `.github/agents/spark-guide.agent.md` | ✓ |
| `.github/instructions/spark-assistant-guide.instructions.md` | ✓ |
| `.github/prompts/scf-*.prompt.md` (11 file) | ✓ |

Il bootstrap verifica le sorgenti prima di copiare (righe `4101–4113`):

```python
missing_sources = [
    str(source_path)
    for source_path, _ in bootstrap_targets
    if not source_path.is_file()
]
if missing_sources:
    return { "success": False, "status": "error", ... }
```

**Impatto:** La sorgente è integra. Il problema non sta qui.

---

### D4 — Il tool conosce la destinazione giusta?

**Risposta: SÌ — teoricamente, ma condizionato alla corretta risoluzione del workspace**

**Evidenza — `spark/boot/engine.py`, righe ~3805–3813:**

```python
engine_github_root = self._ctx.engine_root / ".github"           # riga 3805
# ...
workspace_github_root = self._ctx.github_root                    # riga 3809
sentinel = workspace_github_root / "agents" / "spark-assistant.agent.md"
```

La destinazione è `self._ctx.github_root`, che a sua volta è
`workspace_root / ".github"` (dalla `WorkspaceContext`).

**Il gap critico:** se `workspace_root` è stato risolto come la directory
dell'engine stesso (es. perché `WorkspaceLocator` ha trovato `.vscode/`
o `.scf-manifest.json` nella directory dell'engine durante il CWD fallback),
allora `workspace_github_root` punta all'interno del repo engine — non al
progetto utente.

---

### D5 — Esiste un hook di auto-bootstrap?

**Risposta: NO — nessun meccanismo automatico**

Ricerca esaustiva in `spark/boot/engine.py`, `spark/boot/sequence.py` e
`spark-framework-engine.py` per: `startup`, `on_startup`, `lifespan`,
`auto_bootstrap`, `_boot_hook`, callback su eventi FastMCP.

**Risultato:** nessuna corrispondenza trovata.

L'unico punto dove il bootstrap potrebbe avvenire in modo "parzialmente
automatico" è la Fase 6 (`_apply_phase6_assets`) che viene chiamata come
post-step all'interno di `_finalize_bootstrap_result`  
(righe ~3996–4015, `spark/boot/engine.py`). Ma tale funzione è chiamata
**solo** all'interno di `scf_bootstrap_workspace`, non durante il boot.

**Non esiste nessun listener FastMCP che triggeri il bootstrap all'avvio.**

**Impatto:** Il server è passivo. L'utente (o Copilot tramite un agente già
presente) deve invocare esplicitamente `scf_bootstrap_workspace`. Senza
un agente installato, Copilot non ha modo di invocare il tool.

---

### D6 — Il workspace utente è raggiungibile?

**Risposta: SÌ — ma con risoluzione fragile e ordine di priorità a rischio**

`WorkspaceLocator.resolve()` usa questa sequenza di priorità  
(`spark/workspace/locator.py`, righe 172–215):

| Priorità | Metodo | Nota |
|----------|--------|------|
| ~~1~~ | MCP Roots (protocollo standard) | **ASSENTE nel codice** |
| 2 | Env var `ENGINE_WORKSPACE` | Non esposta nel `mcp-config-example.json` |
| 3 | Env var `WORKSPACE_FOLDER` | Non esposta nel `mcp-config-example.json` |
| 4 | CWD + discovery `.vscode/` / `.github/` | **Fallback attivo** |

**Gap critico:** Il `mcp-config-example.json` non passa nessuna variabile
d'ambiente:

```json
{
  "servers": {
    "sparkFrameworkEngine": {
      "type": "stdio",
      "command": "python",
      "args": ["/path/to/spark-framework-engine/spark-framework-engine.py"]
    }
  }
}
```

Senza `ENGINE_WORKSPACE` o `WORKSPACE_FOLDER`, il server ricade sul **CWD
fallback**. Il CWD di un processo MCP stdio avviato da VS Code è tipicamente
la directory dell'engine o la home dell'utente — **non** la cartella del
progetto aperto.

**Nota aggiuntiva sul "priority 1 mancante":** Il commento in `resolve()`
salta direttamente a `# 2. ENGINE_WORKSPACE env var` — la priorità 1
(MCP Roots, introdotta nel protocollo MCP per comunicare al server quale
workspace è aperto) non è implementata.

---

## 5. Riepilogo gap architetturali (per priorità)

---

### GAP-1 — CRITICO: Nessun auto-bootstrap all'avvio

**Impatto:** senza `.github/agents/spark-assistant.agent.md` nel workspace,
Copilot non mostra nessun agente SPARK. Il tool che crea quel file deve
essere invocato dall'utente, ma l'utente non sa farlo perché gli agenti
non sono ancora visibili. **Dipendenza circolare.**

**Dove intervenire:**
- File: `spark/boot/sequence.py`
- Metodo: `_build_app()`, dopo `app.register_tools()` (riga ~151)
- Soluzione proposta: aggiungere un hook di auto-bootstrap condizionale
  che verifichi la presenza della sentinella e, se assente, esegua il
  bootstrap di sola Fase 0 (senza `install_base`). Il check è un semplice:
  ```python
  sentinel = context.github_root / "agents" / "spark-assistant.agent.md"
  if context.github_root and not sentinel.is_file():
      # esegui bootstrap minimale
  ```

---

### GAP-2 — CRITICO: Workspace non identificato senza configurazione esplicita

**Impatto:** il server non sa quale cartella è aperta in VS Code. Nel caso
tipico (avvio MCP senza env vars), il CWD fallback risolve la directory
dell'engine o la home, non il progetto utente. Il bootstrap copia i file nel
posto sbagliato o fallisce silenziosamente.

**Dove intervenire:**
- File: `mcp-config-example.json` (documentazione / template)
- Soluzione proposta: aggiungere la variabile `WORKSPACE_FOLDER` al template
  con placeholder `${workspaceFolder}` (VS Code lo espande automaticamente):
  ```json
  "env": {
    "WORKSPACE_FOLDER": "${workspaceFolder}"
  }
  ```
- File secondario: `spark/workspace/locator.py`
- Metodo: `resolve()`, riga 172
- Soluzione secondaria: implementare la Priority 1 (MCP Roots) leggendo
  `roots` dal contesto MCP quando disponibile.

---

### GAP-3 — MEDIO: MCP Roots (priority 1) non implementata

**Impatto:** il protocollo MCP permette al client (VS Code) di comunicare
esplicitamente al server quale workspace è aperto tramite `roots`. Ignorare
questo meccanismo standard rende la risoluzione del workspace dipendente
da configurazione manuale (env vars) anziché automatica.

**Dove intervenire:**
- File: `spark/workspace/locator.py`
- Metodo: `resolve()`, da aggiungere come priority 1 prima di
  `ENGINE_WORKSPACE` (attuale riga 172)
- Richiede accesso al contesto FastMCP per leggere `roots` — da valutare
  se passare il contesto MCP a `WorkspaceLocator` o usare un parametro
  opzionale.

---

### GAP-4 — BASSO: Bootstrap bloccato da gate di autorizzazione in workspace vergine

**Impatto:** per un workspace nuovo (no `policy_source == "file"`, no
`orchestrator-state.json`), `scf_bootstrap_workspace` richiede
`update_mode` esplicito E `github_write_authorized == True` prima di
scrivere qualsiasi file. In modalità `legacy_bootstrap_mode` (no
`update_mode` e no `policy_source`) i file vengono copiati, ma questo path
è deprecato e non documentato.

**Dove intervenire:**
- File: `spark/boot/engine.py`
- Funzione: `scf_bootstrap_workspace()`, riga ~3857
- Soluzione proposta: il bootstrap **minimale** di Layer 0 (solo sentinella
  + agenti gateway, senza `install_base`) non dovrebbe richiedere
  `github_write_authorized`. I file Layer 0 non provengono da pacchetti
  cross-owner e non modificano `copilot-instructions.md`. Il gate di
  autorizzazione dovrebbe applicarsi solo al flusso esteso (`install_base=True`).

---

### GAP-5 — INFORMATIVO: `_parse_workspace_flag(--workspace)` implementato ma non usato

**Impatto:** `WorkspaceLocator` ha un metodo statico `_parse_workspace_flag`
(riga ~107, `locator.py`) che legge `--workspace VALUE` da `sys.argv`, ma
`resolve()` non lo chiama mai. La funzione è dead code.

**Dove intervenire:**
- File: `spark/workspace/locator.py`
- Metodo: `resolve()`, riga 172
- Soluzione: aggiungere come priority 1 la lettura di `--workspace` da argv.
  Questo permetterebbe l'override da CLI senza modificare la configurazione MCP.

---

## 6. Schema riepilogativo: flusso attuale vs flusso atteso

```
FLUSSO ATTUALE
==============
VS Code avvia MCP                → cwd = dir engine (non progetto utente)
WorkspaceLocator.resolve()       → workspace_root = dir engine [GAP-2]
_build_app() completa            → nessun bootstrap automatico [GAP-1]
Copilot cerca .github/agents/    → ASSENTE → nessun agente SPARK visibile

FLUSSO ATTESO (con fix GAP-1 + GAP-2)
======================================
VS Code avvia MCP con WORKSPACE_FOLDER=${workspaceFolder}
WorkspaceLocator.resolve()       → workspace_root = progetto utente ✓
_build_app() dopo register_tools → check sentinella → bootstrap auto Layer 0
Copilot cerca .github/agents/    → spark-assistant.agent.md PRESENTE ✓
Agenti SPARK visibili nel dropdown
```

---

*Report generato da: Agent-Analyze — modalità read-only, nessuna modifica al codebase.*
