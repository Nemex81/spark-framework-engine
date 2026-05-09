# SPARK Framework — Design Document: Full Decoupling Architecture v2.0

**Stato:** PROPOSTA v2.0 — In attesa di approvazione da Nemex81
**Autore originale:** Perplexity AI (Coordinatore)
**Validazione e redazione v2.0:** GitHub Copilot (spark-engine-maintainer)
**Data:** 2026-05-08
**Branch di riferimento:** `feature/dual-mode-manifest-v3.1` (base tecnica)
**Sostituisce:** `docs/SPARK-DESIGN-FullDecoupling-v1.0.md`
**Report di validazione:** `docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md`

---

## Note di versione

La v2.0 corregge tutti e tre i problemi BLOCCANTI identificati nel report
`docs/reports/REPORT-Copilot-FullDecoupling-Issues.md`:

- **PROBLEMA-1** (path moduli errati): §5 ora riporta i path reali del codebase
- **PROBLEMA-2** (nome funzione errato): §4.2 usa il nome reale `_install_standalone_files_v3`
- **PROBLEMA-3** (snippet init errato): §4.3 usa `self._ctx.workspace_root` e `_REGISTRY_URL`

Introduce inoltre:

- Sezione §0 "Stato Attuale vs Stato Target" con path reali verificati
- Descrizione completa dei due universi A e B (§2.1)
- Specifica del meccanismo `#file:` per istruzioni plugin (§2.4)
- Semplificazione manifest (§3.2 e §6.2)
- Piano di migrazione aggiornato in 4 step (§6.3)

---

## 0. Stato Attuale vs Stato Target

### 0.1 Struttura codebase attuale (branch `feature/dual-mode-manifest-v3.1`)

```text
spark-framework-engine/
├── spark-framework-engine.py          # Entry point MCP (avvio, registrazione tools)
├── spark/
│   ├── core/
│   │   ├── constants.py               # _MANIFEST_FILENAME, _REGISTRY_URL, ENGINE_VERSION
│   │   ├── models.py                  # WorkspaceContext, FrameworkFile, ecc.
│   │   └── utils.py                   # helpers condivisi
│   ├── boot/
│   │   ├── engine.py                  # SparkFrameworkEngine(_V3LifecycleMixin)
│   │   ├── lifecycle.py               # _V3LifecycleMixin: _install_workspace_files_v3,
│   │   │                              #   _install_standalone_files_v3, _remove_workspace_files_v3
│   │   ├── tools_packages_install.py  # scf_install_package (tool MCP, ~300 righe)
│   │   ├── tools_packages.py          # scf_remove_package, scf_update_package, ecc.
│   │   └── tools_bootstrap.py        # scf_bootstrap_workspace, scf_verify_workspace
│   ├── manifest/
│   │   ├── gateway.py                 # WorkspaceWriteGateway
│   │   └── manifest.py                # ManifestManager (.github/.scf-manifest.json)
│   ├── registry/
│   │   └── client.py                  # RegistryClient
│   ├── inventory/
│   │   └── framework.py               # FrameworkInventory
│   ├── workspace/
│   │   └── locator.py                 # WorkspaceLocator
│   ├── packages/
│   │   └── lifecycle.py               # _install_package_v3_into_store, _get_deployment_modes
│   ├── assets/
│   │   └── phase6.py                  # _apply_phase6_assets (AGENTS.md, .clinerules, ecc.)
│   └── merge/
│       └── sections.py                # _scf_section_merge, SCF:BEGIN/END marker logic
│
│   # NON ESISTE YET:
│   └── plugins/                       # <- da creare (Passo 1 della migrazione)
```

### 0.2 Stato target (post-migrazione v2.0)

```text
spark/
└── plugins/                           # NUOVO package
    ├── __init__.py                    # esporta PluginManagerFacade
    ├── facade.py                      # PluginManagerFacade
    ├── installer.py                   # PluginInstaller (eredita logica da lifecycle.py)
    ├── remover.py                     # PluginRemover (eredita logica da lifecycle.py)
    ├── updater.py                     # PluginUpdater
    ├── registry.py                    # PluginRegistry (stato: .github/.spark-plugins)
    └── schema.py                      # PluginManifest, PluginRecord (dataclass)
```

**Componenti modificati:**

| File | Tipo modifica |
| --- | --- |
| `spark/boot/lifecycle.py` | Rimozione `_install_workspace_files_v3`, `_install_standalone_files_v3` (migrano in `spark/plugins/installer.py`) |
| `spark/boot/tools_packages_install.py` | Thin facade verso `PluginManagerFacade` per il path plugin |
| `spark/boot/engine.py` | Aggiunta inizializzazione `_plugin_manager` in `_init_runtime_objects()` |
| `spark/boot/tools_bootstrap.py` | Bootstrap aggiornato: `copilot-instructions.md` + `AGENTS.md` base, con conferma per aggiornamenti |

**Componenti invariati (non si toccano):**

| Componente | Path reale | Motivo |
| --- | --- | --- |
| `WorkspaceWriteGateway` | `spark/manifest/gateway.py` | Riusata dal Plugin Manager |
| `ManifestManager` | `spark/manifest/manifest.py` | Riusata dal Plugin Manager |
| `RegistryClient` | `spark/registry/client.py` | Riusata dal Plugin Manager |
| `FrameworkInventory` | `spark/inventory/framework.py` | Gestisce solo risorse MCP interne |
| `WorkspaceLocator` | `spark/workspace/locator.py` | Non modificata |
| `_install_package_v3_into_store` | `spark/packages/lifecycle.py` | Store interno: invariato |

---

## 1. Contesto e Motivazione

### 1.1 Il problema dell'ibrido

Il branch `feature/dual-mode-manifest-v3.1` introduce il campo `plugin_files` nel
manifest per distinguere file fisici da risorse MCP pure. Questa soluzione funziona,
ma lascia in piedi una tensione architettuale fondamentale: il server MCP engine
continua a gestire entrambe le responsabilità — servire risorse via protocollo MCP
*e* scrivere file nel filesystem dell'utente.

Il risultato pratico è che ogni volta che si aggiunge un nuovo pacchetto bisogna
dichiarare esplicitamente come si comporta, e la logica condizionale su `plugin_files`
si accumula nei moduli `lifecycle.py` e `tools_packages_install.py`.

### 1.2 La soluzione: separazione per responsabilità e due universi

Questo documento descrive un'architettura alternativa basata sul principio di singola
responsabilità applicato a livello di sistema, con una separazione netta tra due
universi:

- **Universo A — Engine / MCP Services**: Il server MCP fa una cosa sola: esporre
  risorse interne via protocollo MCP. I pacchetti in questo universo sono servizi
  interni dell'engine, non toccano il workspace utente.

- **Universo B — Plugin / Workspace**: Il Plugin Manager fa una cosa sola: gestire
  file di plugin nel filesystem del workspace utente, comunicando direttamente con
  registro e repo GitHub.

I due sistemi sono indipendenti. Il Plugin Manager non dipende dal processo MCP per
funzionare. Il Server MCP non conosce i repo esterni né scrive nel workspace per i
pacchetti Universo A.

---

## 2. Architettura Target

### 2.1 Visione a due universi

#### UNIVERSO A — Engine / MCP Services (interno, sempre attivo)

I pacchetti attualmente presenti nell'engine nella loro versione embedded (spark-base,
scf-master-codecrafter, scf-pycode-crafter) vengono operati come **servizi MCP puri**.

Regole:

- Nessuna scrittura nel workspace utente per questa categoria.
- Nessun riferimento ai repository GitHub online.
- Serviti esclusivamente via URI MCP (`agents://`, `skills://`, `instructions://`, `prompts://`).
- Il registro (`scf-registry/registry.json`) NON li conosce e NON li elenca.
- Evolvono con il motore tramite versionamento SemVer indipendente.
- `FrameworkInventory` gestisce solo questo universo.

Eccezione bootstrap: al primo avvio, l'engine scrive `copilot-instructions.md`
(sezione SPARK core con marker `SCF:BEGIN:engine-bootstrap`) e `AGENTS.md` base.
Dopo il primo avvio, questi file appartengono all'utente — l'engine propone
aggiornamenti ma NON li applica senza conferma esplicita.

#### UNIVERSO B — Plugin / Workspace (esterni, autonomi, offline-first)

I plugin sono entità completamente indipendenti dall'engine.
Sorgente di verità: repository GitHub online, referenziati dal registro.

Regole:

- Una volta installati nel workspace (`.github/`), funzionano anche senza engine attivo.
- Copilot li legge direttamente dai file fisici, senza passare per MCP.
- `ManifestManager` (`.github/.scf-manifest.json`) traccia SOLO i plugin installati.
- Il registro (`scf://registry`) è esclusivamente il catalogo dei plugin scaricabili
  da GitHub.
- `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter` esistono come plugin
  autonomi nei loro repository GitHub — distinti dalla loro versione embedded nell'engine.

### 2.2 Visione a due livelli (architettura componenti)

```text
+----------------------------------------------------------+
|  LIVELLO 1 — Server MCP (spark-framework-engine.py)     |
|                                                          |
|  Responsabilità UNICA: esporre risorse interne via MCP   |
|                                                          |
|  Universo A (sola lettura, embedded):                    |
|    agents://*, skills://*, instructions://*, prompts://* |
|    scf://runtime-state, scf://agents-index, ecc.         |
|                                                          |
|  Tool MCP esposti:                                       |
|    scf_get_resource, scf_list_resources                  |
|    scf_runtime_status, scf_bootstrap_workspace           |
|    scf_install_plugin (thin facade → Livello 2)          |
|    scf_remove_plugin  (thin facade → Livello 2)          |
|    scf_update_plugin  (thin facade → Livello 2)          |
|    scf_list_plugins, scf_plugin_status                   |
|                                                          |
|  NON scrive mai nel workspace per Universo A.            |
|  NON conosce registry.json ne repo GitHub per Universo A.|
+--------------------+-------------------------------------+
                     |  delega chiamate plugin via
                     |  PluginManagerFacade (interfaccia pub.)
                     v
+----------------------------------------------------------+
|  LIVELLO 2 — Plugin Manager (spark/plugins/)             |
|                                                          |
|  Responsabilità UNICA: gestire plugin nel workspace      |
|                                                          |
|  Componenti interni:                                     |
|    PluginRegistry    -> stato locale .spark-plugins      |
|    PluginInstaller   -> scarica da repo, scrive .github/ |
|    PluginRemover     -> rimozione simmetrica             |
|    PluginUpdater     -> confronto versioni, aggiorna     |
|    RegistryClient    -> parla con registry.json remoto   |
|                                                          |
|  NON dipende dal processo MCP per funzionare.            |
|  Usa WorkspaceWriteGateway e ManifestManager esistenti.  |
|  Aggiorna copilot-instructions.md via #file: reference.  |
+----------------------------------------------------------+
```

### 2.3 Flusso di installazione plugin (comportamento nuovo)

```text
Utente -> Copilot Agent -> scf_install_plugin (tool MCP)
    |
    +-> PluginManagerFacade.install(pkg_id)
           |
           +-- RegistryClient.fetch()        # via spark/registry/client.py
           |       +-> HTTP GET registry.json -> raw.githubusercontent.com
           |
           +-- PluginInstaller.download(manifest, workspace_root)
           |       +-> HTTP GET asset files da source_repo GitHub
           |
           +-- WorkspaceWriteGateway.write_many(plugin_files)
           |       # via spark/manifest/gateway.py
           |       +-> preservation gate SHA-256 (invariante ManifestManager)
           |
           +-- PluginInstaller._add_instruction_reference(pkg_id)
           |       +-> aggiunge #file:.github/instructions/{pkg_id}.md
           |           in copilot-instructions.md
           |
           +-- PluginRegistry.register(pkg_id, version, files)
                   +-> aggiorna .github/.spark-plugins (JSON)
                   +-> ManifestManager.upsert_many() per ogni file
                       # ownership tracciata in .github/.scf-manifest.json
```

### 2.4 Meccanismo `#file:` per istruzioni plugin

Ogni plugin porta il proprio file di istruzioni:

- **Path nel workspace**: `.github/instructions/{plugin-id}.md`
- **Contenuto**: istruzioni operative specifiche del plugin (equivalente all'attuale
  blocco `SCF:BEGIN:{plugin-id}` in `copilot-instructions.md`)

Quando il plugin viene installato, `PluginInstaller._add_instruction_reference()`
aggiunge una riga in `copilot-instructions.md`:

```markdown
# Plugin instructions (managed by SPARK Plugin Manager — do not edit manually)
#file:.github/instructions/scf-master-codecrafter.md
#file:.github/instructions/scf-pycode-crafter.md
```

Quando il plugin viene rimosso, `PluginRemover._remove_instruction_reference()`
rimuove la riga corrispondente.

**Perché questo approccio è preferibile al SCF section merge attuale:**

- Il plugin possiede il proprio file di istruzioni — è indipendente da `copilot-instructions.md`
- L'aggiornamento di un plugin aggiorna solo il suo file `.github/instructions/{plugin-id}.md`
- Non richiede `_scf_section_merge` né la gestione dei marker `SCF:BEGIN/END`
- I file `.github/instructions/*.md` sono già nel workspace e funzionano offline
  (Copilot li legge come file fisici con `applyTo`)

**Coesistenza con SCF section merge:**

- La sezione di bootstrap engine (Universo A) usa ancora il meccanismo
  `SCF:BEGIN:engine-bootstrap / SCF:END:engine-bootstrap` in `copilot-instructions.md`
  per il contenuto minimo dell'engine
- I plugin (Universo B) usano `#file:` references — nessun overlap

**Nota implementativa (Fase 3 — verifica codebase):**
Il meccanismo `#file:` è nativo di VS Code Copilot e non richiede alcuna modifica al
codice Python del motore per la lettura. Il motore scrive/rimuove solo la riga
`#file:...` dal file `copilot-instructions.md`. La logica di inserimento/rimozione
è implementata come string manipulation semplice in `PluginInstaller._add_instruction_reference()`
e `PluginRemover._remove_instruction_reference()`.

### 2.5 Flusso di lettura risorsa MCP (comportamento invariato)

```text
Copilot Agent -> scf_get_resource("agents://spark-assistant")
    |
    +-> FrameworkInventory.get_resource(uri)
           +-> engine store embedded (memoria, read-only)
                   -> restituisce contenuto via MCP
                   -> ZERO scritture filesystem
```

---

## 3. Moduli da Creare

### 3.1 Nuovo package: `spark/plugins/`

Questo è il cuore del disaccoppiamento. Non modifica nulla di esistente —
aggiunge un package autonomo con interfaccia pubblica definita.

```text
spark/plugins/
├── __init__.py           # esporta PluginManagerFacade
├── facade.py             # PluginManagerFacade — punto di accesso unico
├── registry.py           # PluginRegistry — stato locale .spark-plugins
├── installer.py          # PluginInstaller — download + scrittura workspace
│                         #   Eredita logica da lifecycle._install_standalone_files_v3
│                         #   e lifecycle._install_workspace_files_v3
├── remover.py            # PluginRemover — rimozione simmetrica
│                         #   Eredita logica da lifecycle._remove_workspace_files_v3
├── updater.py            # PluginUpdater — confronto versioni, aggiornamento
└── schema.py             # dataclass PluginManifest, PluginRecord
```

### 3.2 File di stato locale: `.github/.spark-plugins`

Formato JSON, gestito da `PluginRegistry`. Parallelo a `.github/.scf-manifest.json`.

**Nota:** `.github/.scf-manifest.json` (gestito da `ManifestManager`) traccia i file
singoli con owner e SHA per la preservation gate. `.github/.spark-plugins` traccia i
**pacchetti** installati con metadati di installazione (versione, source, data).
I due file sono complementari: `ManifestManager` gestisce il livello file,
`PluginRegistry` gestisce il livello pacchetto.

```json
{
  "schema_version": "1.0",
  "installed": {
    "scf-master-codecrafter": {
      "version": "2.6.0",
      "source_repo": "Nemex81/scf-master-codecrafter",
      "installed_at": "2026-05-08T09:00:00Z",
      "files": [
        ".github/instructions/scf-master-codecrafter.md",
        ".github/agents/code-Agent-Code.agent.md"
      ],
      "file_hashes": {
        ".github/instructions/scf-master-codecrafter.md": "sha256:abc123..."
      }
    }
  }
}
```

### 3.3 Interfaccia pubblica `PluginManagerFacade`

```python
class PluginManagerFacade:
    """Punto di accesso unico al Plugin Manager dal Server MCP.

    Args:
        workspace_root: Path assoluto alla root del workspace utente.
                        (corrisponde a self._ctx.workspace_root nel motore)
        registry_url: URL del registry.json remoto.
                      (default: _REGISTRY_URL da spark.core.constants)

    Note:
        Tutti i metodi sono sincroni e restituiscono dict serializzabili
        in JSON per essere usati direttamente come payload MCP tool response.
    """

    def __init__(
        self,
        workspace_root: Path,
        registry_url: str = _REGISTRY_URL,  # costante da spark.core.constants
    ) -> None:
        github_root = workspace_root / ".github"
        self._workspace_root = workspace_root
        self._registry = RegistryClient(
            github_root=github_root,
            registry_url=registry_url,
        )
        self._manifest = ManifestManager(github_root)
        self._plugin_registry = PluginRegistry(github_root)
        self._installer = PluginInstaller(workspace_root, self._manifest)
        self._remover = PluginRemover(workspace_root, self._manifest)
        self._updater = PluginUpdater(workspace_root, self._manifest)

    def install(self, pkg_id: str) -> dict:
        """Scarica e installa un plugin dal registry remoto."""

    def remove(self, pkg_id: str) -> dict:
        """Rimuove un plugin installato e i suoi file dal workspace."""

    def update(self, pkg_id: str) -> dict:
        """Aggiorna un plugin alla versione piu recente disponibile."""

    def list_installed(self) -> dict:
        """Elenca i plugin installati con versione e stato file."""

    def list_available(self) -> dict:
        """Elenca i pacchetti disponibili nel registry remoto."""

    def status(self, pkg_id: str) -> dict:
        """Stato di un singolo plugin: versione, integrita file, aggiornamenti."""
```

**Nota:** `RegistryClient` costruito con `github_root = workspace_root / ".github"` perché
il costruttore reale è `RegistryClient(github_root: Path, registry_url: str, cache_path: Path | None)`.
Il file di cache viene scritto in `.github/.scf-registry-cache.json` (default del costruttore).

---

## 4. Moduli da Modificare

### 4.1 `spark/boot/tools_packages_install.py`

**Modifica:** aggiungere il nuovo tool MCP `scf_install_plugin` come **thin facade**
che delega a `PluginManagerFacade`. Il vecchio `scf_install_package` rimane invariato
per lo store interno dell'engine (pacchetti Universo A).

**Prima (Dual-Mode ibrido in lifecycle.py):**

```python
# logica workspace, plugin_files, preservation gate — tutto dentro scf_install_package
async def scf_install_package(pkg_id: str, ...):
    result = _install_package_v3_into_store(...)
    if manifest.get("plugin_files"):
        self._install_standalone_files_v3(...)  # via _V3LifecycleMixin
    return build_response(result)
```

**Dopo (Full Decoupling):**

```python
# Nuovo tool — thin facade
@mcp.tool()
async def scf_install_plugin(pkg_id: str) -> dict:
    """Installa un plugin dal registry SCF nel workspace utente."""
    return engine._plugin_manager.install(pkg_id)

# Vecchio tool — rimane per store interno engine (Universo A)
@mcp.tool()
async def scf_install_package(pkg_id: str, ...) -> dict:
    """Installa un pacchetto nello store interno dell'engine (Universo A)."""
    result = _install_package_v3_into_store(...)
    # NESSUNA logica workspace_files, plugin_files o standalone_files qui
    return build_response(result)
```

### 4.2 `spark/boot/lifecycle.py`

**Modifica:** le funzioni che gestiscono file nel workspace utente migrano in
`spark/plugins/installer.py` e `spark/plugins/remover.py`. Rimangono nel mixin
solo le funzioni relative allo store interno dell'engine.

**Funzioni che MIGRANO in `spark/plugins/installer.py`:**

- `_install_workspace_files_v3` — diventa `PluginInstaller._write_files()`
- `_install_standalone_files_v3` — diventa `PluginInstaller.install_files()`
  (nota: il nome reale nel codebase è `_install_standalone_files_v3`, non
  `_install_plugin_files_v3` come indicato erroneamente in §4.2 della v1.0)

**Funzioni che MIGRANO in `spark/plugins/remover.py`:**

- `_remove_workspace_files_v3` — diventa `PluginRemover.remove_files()`

**Funzioni che RIMANGONO in `_V3LifecycleMixin` (spark/boot/lifecycle.py):**

- `_v3_runtime_state`
- `_is_github_write_authorized_v3`
- `_v3_repopulate_registry`
- `_install_package_v3` (orchestrazione store — Universo A)
- `_remove_package_v3` (orchestrazione store — Universo A)
- `_update_package_v3` (orchestrazione store — Universo A)

### 4.3 `spark/boot/engine.py`

**Modifica:** aggiungere l'inizializzazione di `PluginManagerFacade` in
`_init_runtime_objects()`, dopo `RegistryClient`.

```python
# In SparkFrameworkEngine._init_runtime_objects():
# Aggiungere subito dopo self._registry_client = RegistryClient(self._ctx.github_root)

from spark.plugins import PluginManagerFacade  # noqa: PLC0415

self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,  # WorkspaceContext.workspace_root
    # registry_url usa default _REGISTRY_URL da spark.core.constants
)
```

**Note critiche:**

- `self._ctx` è il `WorkspaceContext` passato al costruttore — attributo esistente
- `self._ctx.workspace_root` è il path reale del workspace utente — attributo esistente
- NON esiste `self._config` né `self._workspace_locator` in `SparkFrameworkEngine`
- L'inizializzazione è lazy (in `_init_runtime_objects()`, non in `__init__`) per
  coerenza con il pattern esistente degli altri runtime objects

### 4.4 `spark/boot/tools_bootstrap.py`

**Modifica:** aggiornare `scf_bootstrap_workspace` per il comportamento v2.0:

1. Al primo avvio: scrive `copilot-instructions.md` (con sezione
   `SCF:BEGIN:engine-bootstrap`) e `AGENTS.md` base. Questi file vanno nel workspace.
2. Agli avvii successivi: se i file di bootstrap sono già presenti e modificati
   dall'utente (SHA mismatch in `ManifestManager`), il tool propone l'aggiornamento
   ma NON lo applica automaticamente — restituisce un diff e attende conferma.
3. Il `ManifestManager` continua a tracciare i file di bootstrap con owner
   `"engine-bootstrap"`.

---

## 5. Invarianti Architetturali (non si toccano)

I componenti seguenti non vengono modificati in nessun task. Path reali verificati
nel codebase (branch `feature/dual-mode-manifest-v3.1`):

| Componente | Path nel codebase | Package | Note |
| --- | --- | --- | --- |
| `WorkspaceWriteGateway` | `spark/manifest/gateway.py` | `spark.manifest` | Riusata da PluginInstaller/Remover |
| `ManifestManager` | `spark/manifest/manifest.py` | `spark.manifest` | Traccia ownership file workspace |
| `RegistryClient` | `spark/registry/client.py` | `spark.registry` | Constructor: `(github_root, registry_url, cache_path)` |
| `FrameworkInventory` | `spark/inventory/framework.py` | `spark.inventory` | Solo risorse MCP Universo A |
| `WorkspaceLocator` | `spark/workspace/locator.py` | `spark.workspace` | Risolve workspace path |
| `_scf_section_merge` | `spark/merge/sections.py` | `spark.merge` | Usata solo per bootstrap engine |
| `_install_package_v3_into_store` | `spark/packages/lifecycle.py` | `spark.packages` | Store interno engine |

**Nota:** `spark/core/` contiene SOLO `constants.py`, `models.py`, `utils.py`.
Nessuna classe del livello 2 vive in `spark/core/`.

---

## 6. Compatibilità e Migrazione

### 6.1 Gestione backward compatibility

I workspace utente esistenti che hanno già file installati tramite `workspace_files`
(schema v3.0, campo in `package-manifest.json`) non vengono rotti. Al primo avvio
post-migrazione, `PluginRegistry` scansiona `.github/.scf-manifest.json` (usando
`ManifestManager.load()`) e ricostruisce `.github/.spark-plugins` se assente,
registrando i file esistenti come "installati senza metadati" con flag
`migrated: true`.

Questo approccio è preferibile al rilevamento da filesystem perché importa
l'ownership e gli SHA già tracciati nel manifest — evitando falsi positivi nel
preservation gate.

### 6.2 Schema manifest dei pacchetti repo

I `package-manifest.json` nei repo `scf-master-codecrafter` e `scf-pycode-crafter`
vengono aggiornati per v2.0. Le modifiche sono nei repository remoti, non nel
codebase del motore. Stato attuale (verificato):

- Nessuno dei due repo ha il campo `plugin_files` (introdotto solo nel branch corrente)
- Entrambi hanno `workspace_files` con 2-3 file Cat. A

La migrazione v2.0 richiede che i repo sostituiscano `workspace_files` con
`plugin_files` e aggiungano il file di istruzioni dedicato:

```json
{
  "schema_version": "3.1",
  "plugin_files": [
    ".github/instructions/scf-master-codecrafter.md",
    ".github/agents/code-Agent-Code.agent.md",
    ".github/agents/code-Agent-Design.agent.md"
  ]
}
```

Il campo `workspace_files` è deprecato con warning nel `PluginInstaller` se trovato
in un manifest v3.0/v3.1 durante l'installazione.

### 6.3 Piano di migrazione in 4 step

**Step 1 — Crea `spark/plugins/` senza rimuovere nulla** (rischio: BASSO)

*Criteri di accettazione:*

- `spark/plugins/__init__.py` esportato correttamente
- `PluginManagerFacade` instanziabile con `workspace_root` e `registry_url`
- I test esistenti passano senza modifiche (`pytest -q --ignore=tests/test_integration_live.py`)
- Nessun tool MCP cambiato in questo step

*Note:* il Plugin Manager esiste in parallelo al sistema esistente.
`PluginInstaller._write_files()` è una riscrittura di `_install_workspace_files_v3`
nel nuovo contesto — non un refactor del codice originale. I due metodi coesistono.

**Step 2 — Collega i tool MCP al Plugin Manager** (rischio: MEDIO)

*Criteri di accettazione:*

- Tool `scf_install_plugin` e `scf_remove_plugin` registrati e funzionanti
- Il tool `scf_install_package` rimane invariato (Universo A, store interno)
- Contatore tool `Tools registered: N total` aggiornato nel log di avvio
- Test di integrazione per `scf_install_plugin` scritti e passanti

*Note:* `scf_install_plugin` ha firma semplificata rispetto a `scf_install_package`
(no `conflict_mode`, no `update_mode` — gestiti dal Plugin Manager internamente).

**Step 3 — Rimuovi la logica ibrida da `lifecycle.py`** (rischio: MEDIO)

*Criteri di accettazione:*

- `_install_workspace_files_v3`, `_install_standalone_files_v3`,
  `_remove_workspace_files_v3` rimosse da `_V3LifecycleMixin`
- Test `test_standalone_files_v3.py`, `test_install_workspace_files.py`,
  `test_deployment_modes.py` aggiornati per usare `PluginInstaller` direttamente
- Suite completa passa: `pytest -q --ignore=tests/test_integration_live.py`

*Note:* questo è il passo che chiude la separazione. I test citati richiedono
fixture rewrite significativo (non solo nominale) — vedere §7.

**Step 4 — Aggiorna bootstrap per comportamento v2.0** (rischio: BASSO)

*Criteri di accettazione:*

- `scf_bootstrap_workspace` scrive solo `copilot-instructions.md` e `AGENTS.md`
- Gli aggiornamenti ai file di bootstrap richiedono conferma esplicita
- `ManifestManager` traccia i file di bootstrap con owner `"engine-bootstrap"`
- Test bootstrap aggiornati e passanti

### 6.4 Coordinamento `PluginRegistry` / `ManifestManager`

`PluginRegistry` (`.github/.spark-plugins`) e `ManifestManager`
(`.github/.scf-manifest.json`) sono complementari:

- **`ManifestManager`**: granularità file. Traccia ogni singolo file con owner,
  versione, SHA e flag di modifica utente. Fondamentale per il preservation gate.
- **`PluginRegistry`**: granularità pacchetto. Traccia il pacchetto installato con
  metadati di installazione (source_repo, versione, data). Usato per aggiornamenti
  e rimozioni.

A ogni operazione del Plugin Manager:

1. `ManifestManager.upsert_many()` viene chiamato per ogni file scritto (ownership)
2. `PluginRegistry.register()` viene chiamato per il pacchetto (metadati installazione)

Non c'è conflitto di write: le due strutture hanno chiavi diverse
(path file vs package_id).

### 6.5 deprecated_tools

La famiglia direct-download nata nel percorso Dual-Mode v1.0 resta disponibile
solo come compatibilita temporanea. Il percorso target per i plugin workspace e
`PluginManagerFacade`, perche registra ownership file-level in `ManifestManager`
e stato package-level in `PluginRegistry`.

| Tool legacy | Sostituto target | Stato | Rimozione prevista |
| --- | --- | --- | --- |
| `scf_list_plugins` | `scf_plugin_list` | Deprecated | 2026-06-30 |
| `scf_install_plugin` | `scf_plugin_install` | Deprecated | 2026-06-30 |

`scf_get_plugin_info` rimane il tool read-only dedicato ai dettagli di un plugin
workspace: usa il registry filtrato per plugin installabili e il manifest remoto,
senza installare o aggiornare file.

---

## 7. Relazione con il Branch Corrente

Il branch `feature/dual-mode-manifest-v3.1` **non va mergiato su `main`** con
l'approccio attuale. Il lavoro esistente è riutilizzabile:

**Codice riutilizzabile:**

- `lifecycle.py` — `_install_standalone_files_v3` (nome reale, non `_install_plugin_files_v3`)
  migra in `spark/plugins/installer.py` come `PluginInstaller.install_files()`
- `tools_packages_install.py` — il payload con `plugin_files_installed` e
  `standalone_files_written` rimane; cambia solo chi lo popola (`PluginManagerFacade`)

**Test da aggiornare (NON solo fixture minimali):**

| File test | Cosa cambia | Entità aggiornamento |
| --- | --- | --- |
| `tests/test_standalone_files_v3.py` | Target diventa `PluginInstaller` (non `_V3LifecycleMixin`) | Significativo (riscrittura fixture) |
| `tests/test_install_workspace_files.py` | Stessa situazione | Significativo |
| `tests/test_deployment_modes.py` | Test `plugin_files` usano `scf_install_plugin` | Significativo |
| `tests/test_lifecycle.py` | Aggiornamento mock names | Minimale |
| `tests/test_package_lifecycle_v3.py` | Aggiornamento mock names | Minimale |

---

## 8. Checklist Approvazione (per Nemex81)

Prima che Copilot proceda con l'implementazione del Step 1, approvare:

- [ ] Struttura del package `spark/plugins/` con i 7 moduli descritti in §3.1
- [ ] Formato di `.github/.spark-plugins` (§3.2) come stato pacchetto-level
- [ ] Firma di `PluginManagerFacade.__init__(workspace_root, registry_url)` (§3.3)
- [ ] Meccanismo `#file:` per istruzioni plugin (§2.4)
- [ ] Distinzione `scf_install_package` (store engine) vs `scf_install_plugin` (workspace) in §4.1
- [ ] Piano di migrazione a 4 step in §6.3
- [ ] Branch `feature/dual-mode-manifest-v3.1` come base per il Step 1
- [ ] Chiarimento boundary: `spark-base` è un plugin (Universo B) o un pacchetto
      engine embedded (Universo A)?

---

## 9. Decisioni Aperte (richiedono input di Nemex81)

**D1 — `spark-base` come Plugin o come Engine Embedded?**

La v2.0 suggerisce che `spark-base` sia un plugin (Universo B), ma il suo contenuto
attuale (agenti, istruzioni base, copilot-instructions.md core) è strettamente legato
al funzionamento del framework. Opzioni:

- **Opzione A (consigliata):** `spark-base` diventa plugin puro nel registro SCF.
  Il contenuto embedded nell'engine viene separato in un set minimale di template
  di bootstrap (solo `copilot-instructions.md` base + `AGENTS.md` base).
- **Opzione B:** `spark-base` rimane embedded nell'engine (Universo A). Gli agenti
  base sono sempre disponibili via MCP senza installazione. Il workspace utente ha
  ZERO file `spark-base` senza installazione esplicita.

Impatto del chiarimento: definisce il perimetro del Step 4 e il contenuto del
bootstrap al primo avvio.

### D2 — Nome del file di stato plugin

`.github/.spark-plugins` è nascosto e nella cartella già monitorata da SPARK.
Alternativa: `spark-plugins.lock` nella root del workspace (più visibile, stile npm).
Impatto: nessuno sul codice, solo convenzione.

### D3 — Comportamento offline

Il Plugin Manager scarica da GitHub. Se offline:

- Opzione A: fallisce con errore chiaro `NO_CONNECTIVITY`
- Opzione B: usa una cache locale degli ultimi manifest scaricati
  (`RegistryClient` ha già supporto per cache via `_cache_path` nel costruttore)

Opzione B è già parzialmente implementabile con il `RegistryClient` esistente
(che ha fallback alla cache in `fetch()`).

### D4 — Autenticazione repo privati

I repo `scf-*` sono pubblici. Se diventassero privati:
Rimandare — aggiungere `github_token: str | None = None` a `PluginManagerFacade`
quando necessario. `RegistryClient` valida già che l'URL sia
`raw.githubusercontent.com` (publico).
