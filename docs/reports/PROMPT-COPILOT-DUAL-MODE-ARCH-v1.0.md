# PROMPT COPILOT — SPARK Dual-Mode Architecture v1.0
**Progetto:** spark-framework-engine
**Emesso da:** Perplexity (Coordinatore)
**Approvato da:** Luca (Nemex81) — 2026-05-08
**Priorità:** ALTA
**Branch di lavoro:** `feat/dual-mode-architecture`

---

## CONTESTO E DECISIONI ARCHITETTURALI APPROVATE

Questo prompt implementa una rearchitettura approvata dal coordinatore che separa completamente i due sistemi di distribuzione delle risorse SPARK. Le decisioni sono vincolanti e non richiedono ulteriore validazione prima dell'implementazione.

**Documento di riferimento:** `docs/reports/SPARK-REPORT-DualMode-Architecture-v1.0.md`

### Decisione D1 — Niente scrittura workspace da parte dell'engine MCP
Il sistema MCP (pacchetti in `packer/`) smette di scrivere qualsiasi file nel workspace utente. L'unica eccezione esplicita è `scf_bootstrap_workspace`, che continua a gestire i file Tier 1 (file di integrazione editor: `copilot-instructions.md`, `AGENTS.md`) perché VS Code li richiede fisicamente sul filesystem. Qualsiasi campo `workspace_files` nei manifest dei pacchetti built-in viene svuotato. I pacchetti built-in espongono solo risorse MCP via URI (`agents://`, `skills://`, `instructions://`, `prompts://`).

### Decisione D2 — spark-base diventa servizio MCP puro
Il pacchetto `spark-base` (presente in `packer/`) viene convertito allo stesso modello degli altri pacchetti built-in: le sue risorse sono servite esclusivamente via URI MCP, il campo `workspace_files` nel suo `package-manifest.json` viene svuotato, il campo `plugin_files` rimane vuoto (non è un plugin scaricabile dall'utente).

### Decisione D3 — Plugin Manager indipendente per pacchetti remoti
I pacchetti presenti nei repository GitHub remoti (scf-registry) vengono gestiti come plugin indipendenti. L'engine li scarica direttamente nella cartella `.github/` del progetto utente su richiesta esplicita, senza passare per lo store interno. Questi pacchetti sono di proprietà dell'utente: l'engine non li gestisce dopo il download.

---

## ARCHITETTURA TARGET

```
┌─────────────────────────────────────────────────────────┐
│                  SPARK Engine (processo locale)          │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Sistema B — MCP Pure Services                    │   │
│  │  Pacchetti: spark-base, scf-master-codecrafter,   │   │
│  │  scf-pycode-crafter (tutti in packer/)            │   │
│  │  → Servono risorse via URI MCP                    │   │
│  │  → ZERO scrittura workspace                       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Sistema A — Plugin Manager                       │   │
│  │  Fonte: scf-registry + repository GitHub          │   │
│  │  → Scarica plugin in .github/ del progetto utente │   │
│  │  → Gestione completamente autonoma post-download  │   │
│  │  → Engine non mantiene stato su questi file       │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Bootstrap (eccezione esplicita)                  │   │
│  │  scf_bootstrap_workspace → scrive SOLO:           │   │
│  │  - .github/copilot-instructions.md (Tier 1)       │   │
│  │  - .github/AGENTS.md (Tier 1)                     │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## TASK LIST — Implementazione per step indipendenti

Ogni task è autonomo e può essere eseguito e committato separatamente. In caso di imprevisti o ambiguità su un task, documenta il problema in un commento inline nel codice con il tag `# SPARK-ISSUE:` e procedi col task successivo senza bloccarti.

---

### TASK 1 — Aggiornamento schema `package-manifest.json` (tutti i pacchetti built-in)

**File coinvolti:**
- `packer/spark-base/package-manifest.json`
- `packer/scf-master-codecrafter/package-manifest.json`
- `packer/scf-pycode-crafter/package-manifest.json`

**Operazioni:**

Per ciascuno dei tre manifest:

1. Leggi il file `package-manifest.json` corrente.
2. Individua il campo `workspace_files` (può essere una lista o un dict). Svuotalo: imposta il valore a lista vuota `[]`.
3. Se il campo non esiste, crealo con valore `[]`.
4. Aggiungi (o aggiorna se già presente) il campo `plugin_files` con valore `[]`.
5. Aggiungi il campo `delivery_mode` con valore `"mcp_only"` allo stesso livello di `workspace_files`.
6. Aggiorna il campo `schema_version` a `"3.1"` se era `"3.0"`. Se era già `"3.1"` o superiore, non modificarlo.
7. Non modificare nessun altro campo del manifest (versione pacchetto, risorse, dipendenze, ecc.).

**Verifica:** dopo la modifica, i tre manifest devono avere `workspace_files: []`, `plugin_files: []`, `delivery_mode: "mcp_only"`.

**Commit message:** `feat(manifests): set delivery_mode=mcp_only on all built-in packages [TASK-1]`

---

### TASK 2 — Freeze scrittura workspace in `_install_package_v3_into_store`

**File coinvolto:** `spark/packages/lifecycle.py`

**Contesto:** La funzione `_install_package_v3_into_store` gestisce l'installazione dei pacchetti nello store interno. Attualmente può scrivere `workspace_files` nel workspace utente. Con il dual-mode, i pacchetti `mcp_only` non devono mai scrivere nel workspace.

**Operazioni:**

1. Apri `spark/packages/lifecycle.py`.
2. Individua la funzione `_install_package_v3_into_store` (o il punto in cui avviene la scrittura dei `workspace_files`).
3. Prima del blocco che itera su `workspace_files` per scrivere file nel workspace, aggiungi un guard:

```python
# Se il pacchetto è dichiarato mcp_only, non scrivere nulla nel workspace.
# I file vengono serviti esclusivamente via URI MCP dall'engine.
delivery_mode = manifest.get("delivery_mode", "managed")
if delivery_mode == "mcp_only":
    _log.info(
        "[SPARK][TASK-2] Package '%s' is mcp_only — skipping workspace_files write.",
        package_id,
    )
    # Salta SOLO la scrittura workspace_files, non l'installazione nello store.
else:
    # blocco esistente di scrittura workspace_files qui
```

4. Se la struttura del codice è diversa da quella attesa (es. la logica è distribuita in più metodi), applica il guard nel punto più prossimo alla scrittura fisica sul filesystem, documentando la scelta con un commento `# SPARK-ISSUE:` se non è chiaro.
5. Non alterare la logica di installazione nello store interno (SHA, registry, ecc.) — quella rimane invariata per tutti i pacchetti.

**Commit message:** `feat(packages): skip workspace_files write for mcp_only packages [TASK-2]`

---

### TASK 3 — Nuovo modulo `spark/plugins/manager.py` — Plugin Manager

**File da creare:** `spark/plugins/__init__.py` e `spark/plugins/manager.py`

**Scopo:** Gestire il download e la distribuzione dei plugin remoti (pacchetti dai repository GitHub/scf-registry) direttamente nella cartella `.github/` del workspace utente. Il Plugin Manager è completamente indipendente dallo store interno dell'engine.

**Specifica `spark/plugins/__init__.py`:**
```python
from spark.plugins.manager import PluginManager, download_plugin, list_available_plugins

__all__ = ["PluginManager", "download_plugin", "list_available_plugins"]
```

**Specifica `spark/plugins/manager.py`:**

Implementa le seguenti funzioni pubbliche con docstring Google Style:

```python
def list_available_plugins(registry_client) -> list[dict]:
    """
    Recupera dal registry remoto la lista dei pacchetti disponibili come plugin.
    Filtra solo i pacchetti che hanno delivery_mode != 'mcp_only'
    (o che non hanno il campo delivery_mode, per backward-compat).

    Args:
        registry_client: istanza di RegistryClient già inizializzata.

    Returns:
        Lista di dict con almeno: id, version, description, repo_url.

    Raises:
        RuntimeError: se il registry non è raggiungibile e la cache è assente.
    """
    ...


def download_plugin(
    package_id: str,
    version: str,
    target_dir: Path,
    registry_client,
    *,
    overwrite: bool = False,
) -> dict:
    """
    Scarica un plugin dal repository remoto nella cartella target_dir.
    Il plugin viene estratto come file fisici in target_dir/.github/
    Non viene registrato nello store interno dell'engine.
    Operazione idempotente se overwrite=False: se i file esistono già, restituisce
    lo stato attuale senza sovrascrivere.

    Args:
        package_id: identificatore del pacchetto nel registry.
        version: versione da scaricare (es. '1.2.0'). Usa 'latest' per l'ultima.
        target_dir: Path radice del workspace utente (la cartella progetto).
        registry_client: istanza di RegistryClient già inizializzata.
        overwrite: se True, sovrascrive file esistenti senza chiedere conferma.

    Returns:
        Dict con: package_id, version, files_written (list), target_dir (str), status.

    Raises:
        FileExistsError: se overwrite=False e i file esistono già.
        ValueError: se package_id o version non esistono nel registry.
        RuntimeError: se il download fallisce per errore di rete.
    """
    ...


class PluginManager:
    """
    Facade che aggrega list_available_plugins e download_plugin.
    Usata dai tool MCP per esporre le operazioni plugin all'utente.
    """

    def __init__(self, registry_client, workspace_locator):
        ...

    def list(self) -> list[dict]:
        ...

    def install(self, package_id: str, version: str = "latest", *, overwrite: bool = False) -> dict:
        ...
```

**Note implementative:**
- Usa `RegistryClient` già presente in `spark/registry/` per il fetch remoto. Non reinventare la ruota.
- Il download dei file del plugin avviene via HTTP (gli URL raw sono costruibili da `_build_package_raw_url_base` già in `spark/registry/`).
- Logging esclusivamente su `sys.stderr` con formato `[SPARK-PLUGINS][INFO/ERROR] messaggio`.
- Non usare mai `print()` o `sys.stdout`.
- Se la struttura del registry remoto non espone `delivery_mode`, considera tutti i pacchetti remoti come plugin installabili (backward-compat).

**Commit message:** `feat(plugins): add PluginManager with download_plugin and list_available_plugins [TASK-3]`

---

### TASK 4 — Nuovi tool MCP per il Plugin Manager

**File coinvolto:** `spark/boot/tools.py` (o il file che registra i tool FastMCP — verifica il percorso esatto nell'engine)

**Scopo:** Esporre i due nuovi tool MCP `scf_list_plugins` e `scf_install_plugin` all'utente tramite Copilot Agent Mode.

**Tool 1 — `scf_list_plugins`:**
```python
@mcp.tool()
def scf_list_plugins() -> str:
    """
    Elenca i pacchetti disponibili come plugin nel registry SPARK.
    Questi pacchetti possono essere scaricati direttamente nella cartella
    .github/ del progetto utente come file fisici indipendenti dall'engine.
    Restituisce: lista formattata con id, versione, descrizione per ciascun plugin.
    """
    ...
```

**Tool 2 — `scf_install_plugin`:**
```python
@mcp.tool()
def scf_install_plugin(package_id: str, version: str = "latest") -> str:
    """
    Scarica un plugin SPARK dal repository remoto nella cartella .github/ del
    workspace corrente. Il plugin è indipendente dall'engine dopo il download:
    l'utente ne è il proprietario e può modificarlo liberamente.
    Operazione idempotente: non sovrascrive file già esistenti senza conferma.

    Args:
        package_id: ID del plugin da installare (es. 'scf-pycode-crafter').
        version: Versione da installare. Default: 'latest'.

    Returns:
        Report testuale con file scritti, percorso di destinazione e stato.
    """
    ...
```

**Note implementative:**
- Istanzia `PluginManager` passando il `RegistryClient` e `WorkspaceLocator` già disponibili nel contesto engine (vedi come gli altri tool accedono a queste istanze).
- I tool devono restituire stringhe leggibili da Copilot, non JSON grezzo.
- Gestisci eccezioni (`FileExistsError`, `ValueError`, `RuntimeError`) con messaggi chiari e non con eccezioni non gestite verso stdout.
- Se il workspace corrente non è rilevabile da `WorkspaceLocator`, restituisci un errore MCP esplicito: `"Workspace non rilevato. Apri una cartella progetto in VS Code prima di usare questo tool."`.

**Commit message:** `feat(tools): add scf_list_plugins and scf_install_plugin MCP tools [TASK-4]`

---

### TASK 5 — Aggiornamento CHANGELOG e README

**File coinvolti:**
- `CHANGELOG.md`
- `README.md`

**Operazioni CHANGELOG:**

Aggiungi una sezione `## [Unreleased]` in cima (o aggiorna quella esistente) con:

```markdown
## [Unreleased] — Dual-Mode Architecture

### Changed
- Tutti i pacchetti built-in (`spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`) ora operano esclusivamente come servizi MCP (`delivery_mode: mcp_only`). Nessuna scrittura nel workspace utente.
- Schema manifest aggiornato a v3.1: nuovo campo `delivery_mode`.

### Added
- **Plugin Manager** (`spark/plugins/manager.py`): gestione indipendente dei plugin remoti dal registry SPARK.
- Tool MCP `scf_list_plugins`: elenca plugin disponibili nel registry remoto.
- Tool MCP `scf_install_plugin`: scarica un plugin nella cartella `.github/` del progetto utente.

### Migration Notes
- I workspace esistenti con `workspace_files` scritti da versioni precedenti non vengono modificati automaticamente. Eseguire `scf_bootstrap_workspace` per allineare i file Tier 1.
```

**Operazioni README:**

Individua la sezione che descrive i tool MCP disponibili (o l'elenco dei tool). Aggiungi `scf_list_plugins` e `scf_install_plugin` con una riga di descrizione ciascuno. Non riscrivere l'intera sezione — inserimento chirurgico.

**Commit message:** `docs: update CHANGELOG and README for dual-mode architecture [TASK-5]`

---

## GESTIONE IMPREVISTI

Se durante un task incontri una condizione non prevista da questo prompt:

1. **Non bloccarti.** Documenta l'imprevisto con un commento `# SPARK-ISSUE: [descrizione breve]` nel codice interessato.
2. **Implementa la soluzione più conservativa** (es. se non trovi il punto esatto di scrittura workspace, aggiungi il guard al livello più alto disponibile).
3. **Prosegui con il task successivo.**
4. **Nel commit message del task**, aggiungi una riga: `NOTE: SPARK-ISSUE rilevato — vedi commenti inline`.

### Scenari specifici anticipati:

**Scenario A — `lifecycle.py` ha struttura diversa da quella attesa:**
Se la funzione `_install_package_v3_into_store` non esiste o la scrittura `workspace_files` è distribuita in più funzioni, applica il guard `delivery_mode == "mcp_only"` in ogni punto in cui si chiama `Path.write_text()` o equivalente sui `workspace_files`. Documenta ogni punto con `# SPARK-ISSUE:`.

**Scenario B — `spark-base/package-manifest.json` non ha `workspace_files`:**
Se il campo non esiste, crealo con `[]` e aggiungi `delivery_mode: "mcp_only"`. Non alterare gli altri campi.

**Scenario C — Il file dei tool MCP non è `spark/boot/tools.py`:**
Individua il file corretto cercando le definizioni `@mcp.tool()` nell'engine. Usa quello. Non creare un nuovo file per i tool se ne esiste già uno.

**Scenario D — `RegistryClient` non espone il metodo necessario per `list_available_plugins`:**
Implementa `list_available_plugins` usando il metodo pubblico più vicino disponibile in `RegistryClient`. Aggiungi un `# SPARK-ISSUE:` che documenta cosa manca e qual è il workaround usato.

---

## CRITERI DI ACCETTAZIONE GLOBALI

Al termine di tutti i task, la PR deve soddisfare questi criteri:

- [ ] Nessun `print()` aggiunto (verifica con `grep -r "print(" spark/plugins/`).
- [ ] Nessuna scrittura su `sys.stdout` nelle nuove classi o funzioni.
- [ ] I tre manifest built-in hanno `delivery_mode: "mcp_only"` e `workspace_files: []`.
- [ ] `_install_package_v3_into_store` non scrive workspace_files per pacchetti `mcp_only`.
- [ ] `scf_list_plugins` e `scf_install_plugin` sono registrati come tool MCP e restituiscono stringhe leggibili.
- [ ] `scf_bootstrap_workspace` è invariato (non modificato da questa PR).
- [ ] CHANGELOG aggiornato con sezione `[Unreleased]`.
- [ ] Tutti i docstring sono Google Style.
- [ ] Nessun file di test, log o debug committato.

---

## NOTE FINALI

Questa PR non include la migrazione dei workspace utente esistenti — quella è pianificata come step separato. L'obiettivo è solo l'infrastruttura del dual-mode. Non implementare funzionalità non descritte in questo prompt. In caso di dubbio su scope, implementa meno e documenta.
