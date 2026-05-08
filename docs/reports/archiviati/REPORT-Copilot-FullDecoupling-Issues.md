# REPORT — Analisi Full Decoupling Architecture v1.0 (CASO B)

**Autore:** GitHub Copilot (spark-engine-maintainer)
**Data:** 2026-05-08
**Branch:** `feature/dual-mode-manifest-v3.1`
**Documento analizzato:** `docs/SPARK-DESIGN-FullDecoupling-v1.0.md`
**Esito validazione:** CASO B — Design parzialmente incompatibile

---

## Premessa metodologica

L'analisi è stata condotta in sola lettura su 8 file sorgente + 3 file di test + 2 package-manifest.
Nessun file è stato modificato. I problemi rilevati sono errori di analisi nel design doc rispetto allo
stato reale del codebase sul branch `feature/dual-mode-manifest-v3.1`.

---

## Sezione 1 — Lista dei problemi

### PROBLEMA-1 — Path dei moduli errati in §4 e §5

**Categoria:** ARCHITETTURALE
**Gravità:** BLOCCANTE

Il design doc elenca 5 file come invarianti architetturali (§5) da analizzare (Fase 2 del prompt):

| Percorso nel design doc (§4/§5)      | Percorso reale nel codebase           |
|--------------------------------------|---------------------------------------|
| `spark/core/workspace_write_gateway.py` | `spark/manifest/gateway.py`        |
| `spark/core/manifest_manager.py`     | `spark/manifest/manifest.py`          |
| `spark/core/registry_client.py`      | `spark/registry/client.py`            |
| `spark/core/framework_inventory.py`  | `spark/inventory/framework.py`        |
| `spark/core/workspace_locator.py`    | `spark/workspace/locator.py`          |

Nessuno dei 5 path esiste. La directory `spark/core/` contiene solo `constants.py`,
`models.py`, `utils.py`. Le classi corrispondenti vivono in sub-package specializzati
(`manifest/`, `registry/`, `inventory/`, `workspace/`), frutto del refactoring Phase 0
che ha modulare il codebase prima di questo branch.

**Impatto:** qualsiasi istruzione di implementazione che citi questi path produce errori
di import garantiti e non è eseguibile as-is.

---

### PROBLEMA-2 — Nome funzione errato in §4.2

**Categoria:** ARCHITETTURALE
**Gravità:** BLOCCANTE

Il design doc §4.2 afferma:

> "Modifica: rimuovere le funzioni `_install_workspace_files_v3` e
> `_install_plugin_files_v3` da `lifecycle.py`"

La funzione `_install_plugin_files_v3` **non esiste** nel codebase.
La funzione reale che gestisce sia `standalone_files` sia `plugin_files` si chiama:

```python
# spark/boot/lifecycle.py — metodo del mixin _V3LifecycleMixin
def _install_standalone_files_v3(
    self,
    package_id: str,
    pkg_version: str,
    pkg_manifest: Mapping[str, Any],
    manifest: ManifestManager,
) -> dict[str, Any]:
```

Questa funzione gestisce internamente entrambi i campi:
- `deployment_modes.standalone_files` (file Categoria B con `standalone_copy=True`)
- `plugin_files` (campo separato del manifest, introdotto dal branch corrente)

Il design doc non ha rilevato la rinomina avvenuta durante l'implementazione.
Il Passo 3 della migrazione (rimozione logica ibrida) si basa su questa funzione
con il nome sbagliato, rendendo il piano non eseguibile direttamente.

---

### PROBLEMA-3 — Snippet di init in §4.3 usa attributi inesistenti

**Categoria:** ARCHITETTURALE
**Gravità:** BLOCCANTE

Il design doc §4.3 propone questo snippet per `engine.py`:

```python
# Nel design doc (NON eseguibile):
self._plugin_manager = PluginManagerFacade(
    workspace_path=self._workspace_locator.workspace_path,
    registry_url=self._config.registry_url
)
```

**Due attributi inesistenti:**

1. `self._workspace_locator` — non esiste. Il workspace path è accessibile tramite
   `self._ctx.workspace_root` (`WorkspaceContext.workspace_root`).
2. `self._config.registry_url` — non esiste. `SparkFrameworkEngine` non ha un
   attributo `_config`. L'URL del registry è una costante (`_REGISTRY_URL` da
   `spark.core.constants`) iniettata nel costruttore di `RegistryClient`.

Lo snippet corretto sarebbe:

```python
# Versione corretta (per reference, non implementare ora):
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
    registry_url=_REGISTRY_URL,
)
```

Nota: `PluginManagerFacade` riceve `workspace_root` (non `workspace_path`) per
coerenza con la nomenclatura di `WorkspaceWriteGateway.__init__`.

---

### PROBLEMA-4 — `RegistryClient` ha firma diversa da quella implicita in §5

**Categoria:** DIPENDENZA
**Gravità:** RILEVANTE

Il design doc §5 afferma che `RegistryClient` "viene riutilizzato dentro
`spark/plugins/registry.py` senza modifiche". Tuttavia il costruttore attuale è:

```python
# Firma reale (spark/registry/client.py)
def __init__(
    self,
    github_root: Path,
    registry_url: str = _REGISTRY_URL,
    cache_path: Path | None = None,
) -> None:
```

Riceve `github_root` come primo parametro (obbligatorio) per il file di cache locale
(`.github/.scf-registry-cache.json`). Il Plugin Manager userebbe un `workspace_root`
differente da quello dell'engine; se il `PluginManagerFacade` usa il workspace dell'utente
come `github_root`, i file di cache vengono scritti nel workspace utente (ok) ma il
costruttore richiede il path alla root `.github/`, non al workspace root.

Non è un problema insormontabile, ma il riutilizzo non è "senza modifiche":
`RegistryClient(github_root=workspace_root / ".github")` funziona, ma il design
non lo documenta esplicitamente.

---

### PROBLEMA-5 — Dual-tracking state risk

**Categoria:** ARCHITETTURALE
**Gravità:** RILEVANTE

Il design doc §3.2 introduce `.github/.spark-plugins` come file di stato interno del
Plugin Manager, distinto dall'esistente `.github/.spark-manifest.json` gestito da
`ManifestManager`.

**Il problema:** i due sistemi traccerebbero gli stessi file (workspace_files dei pacchetti)
in due strutture separate senza protocollo di coordinamento. Scenari critici non coperti
dal design:

- Un `scf_install_plugin` scrive un file e registra in `.spark-plugins`. Il file viene
  poi rimosso tramite `scf_remove_plugin`. Ma `.spark-manifest.json` è ancora aggiornato?
  Se no, i comandi di audit (es. `scf_verify_workspace`) rilevano divergenze fantasma.
- Un `scf_install_package` (path legacy v2) scrive un file. `PluginRegistry` non sa nulla
  di quel file. Al primo `scf_remove_plugin`, il Plugin Manager non rimuove quel file.
- La §6.1 descrive la migrazione come "scansiona .github/ e registra i file esistenti
  come installati senza metadati". Ma il manifest `.spark-manifest.json` contiene già
  sha256 e owner per quei file. La migrazione corretta dovrebbe leggere
  `.spark-manifest.json` per importare l'ownership esistente, non riscoprire da zero.

---

### PROBLEMA-6 — Boundary "engine-embedded vs plugin" non definito

**Categoria:** ARCHITETTURALE
**Gravità:** RILEVANTE

Il design doc §4.1 afferma: "il vecchio `scf_install_package` rimane per i pacchetti
engine embedded (spark-base e simili)". Tuttavia `spark-base` ha `min_engine_version: 3.1.0`
e `workspace_files` con 2 file Cat. A (`copilot-instructions.md`, `project-profile.md`).
Questi file vengono già scritti nel workspace dal path v3 di `scf_install_package`.

Il design non risponde alla domanda: `spark-base` è un pacchetto "engine embedded" gestito
da `scf_install_package`, oppure un "plugin" gestito da `scf_install_plugin`?
Se la risposta è "engine embedded", allora `scf_install_package` continua a scrivere file
nel workspace, contraddicendo il principio di §2.1 ("il Server MCP NON scrive mai nel
workspace utente"). Se la risposta è "plugin", allora tutta la logica di `spark-base`
deve migrare nel Plugin Manager, inclusi gli asset di bootstrap (§6.3 del design doc
non lo prevede).

---

### PROBLEMA-7 — Test da riscrivere in modo non minimale

**Categoria:** TEST
**Gravità:** RILEVANTE

Il design doc §7 afferma che i test del branch "rimangono validi con minime modifiche ai
fixture". Non è corretto per i test seguenti:

| File test | Test case rilevanti | Impatto atteso |
|-----------|---------------------|----------------|
| `test_standalone_files_v3.py` | 5 test, tutti chiamano `_install_standalone_files_v3` direttamente su `SparkFrameworkEngine` | Il metodo sparisce dall'engine, migra in `spark/plugins/installer.py` → i test devono istanziare `PluginInstaller` direttamente |
| `test_install_workspace_files.py` | 3+ test su `_install_workspace_files_v3` direttamente sull'engine | Stessa situazione: il metodo migra; fixture da riscrivere |
| `test_deployment_modes.py` | 4 test su `scf_install_package` con `deployment_mode` e `plugin_files` | Il tool `scf_install_plugin` ha firma diversa; il test `test_auto_mode_installs_plugin_files_without_standalone_notice` è specifico per `plugin_files` nel tool attuale |

"Modifiche minime" = fix ai nomi di metodo/classe nei fixture. Non è accurato:
i test più impattati istanziano direttamente metodi del mixin che sparirebbero.

---

### PROBLEMA-8 — `plugin_files` non presente in nessun package-manifest.json reale

**Categoria:** NAMING
**Gravità:** MINORE

Né `scf-master-codecrafter` né `scf-pycode-crafter` hanno il campo `plugin_files`
nei loro `package-manifest.json` sul branch corrente. Entrambi usano `workspace_files`.

```json
// scf-master-codecrafter/package-manifest.json
"workspace_files": [
  ".github/copilot-instructions.md",
  ".github/instructions/mcp-context.instructions.md"
]
// campo "plugin_files": ASSENTE
```

Il design doc §6.2 afferma che `plugin_files` diventa "l'unico modo per dichiarare
i file fisici del plugin" e che `workspace_files` viene deprecato. Ma nessun pacchetto
reale usa `plugin_files` oggi, quindi la migrazione (Passo 3 del design) richiede anche
l'aggiornamento di entrambi i `package-manifest.json` nei repo esterni. Questo è un
side-effect non dichiarato nel piano di migrazione.

---

## Sezione 2 — Analisi causa radice (problemi BLOCCANTI)

### PROBLEMA-1 (path errati)

**Causa:** Il design doc è stato redatto su una rappresentazione del codebase
precedente al refactoring Phase 0 modulare, che ha spostato le classi da
`spark-framework-engine.py` monolitico a sub-package specializzati. La struttura
`spark/core/` nel design doc rispecchia una convenzione di naming proposta, non la
struttura reale. Il design doc avrebbe dovuto leggere la directory `spark/` per
identificare i sub-package prima di catalogare i path.

### PROBLEMA-2 (nome funzione errato)

**Causa:** Durante l'implementazione del branch, la funzione che gestisce sia
`standalone_files` sia `plugin_files` è stata chiamata `_install_standalone_files_v3`
(coerente con la voce chiave `standalone_files` del manifest `deployment_modes`).
Il design doc usa il nome `_install_plugin_files_v3` — probabilmente derivato da un
draft intermedio o da un'analisi del manifest field name (`plugin_files`) piuttosto
che dal nome del metodo effettivo.

### PROBLEMA-3 (snippet init errato)

**Causa:** Lo snippet di init è stato generato da reasoning diretto senza leggere
il costruttore `SparkFrameworkEngine.__init__`. Il design doc ha inferito l'esistenza
di `self._workspace_locator` e `self._config` da pattern comuni in framework simili
(Django, FastAPI), ma `SparkFrameworkEngine` usa un `WorkspaceContext` immutabile
passato al costruttore, non un config object separato. Il pattern di init reale
usa `self._ctx.workspace_root` e `_REGISTRY_URL` come costante.

---

## Sezione 3 — Proposta di correzione

### Correzione P1 — Path moduli in §4 e §5

**Modifica minima al design doc:**
Sostituire tutti i riferimenti `spark/core/X.py` con i path reali:

```
spark/core/workspace_write_gateway.py  →  spark/manifest/gateway.py   (classe: WorkspaceWriteGateway)
spark/core/manifest_manager.py         →  spark/manifest/manifest.py  (classe: ManifestManager)
spark/core/registry_client.py          →  spark/registry/client.py    (classe: RegistryClient)
spark/core/framework_inventory.py      →  spark/inventory/framework.py (classe: FrameworkInventory)
spark/core/workspace_locator.py        →  spark/workspace/locator.py  (classe: WorkspaceLocator)
```

Impatto: aggiornamento di §4.1, §4.2, §4.3, §5 con i path corretti.

### Correzione P2 — Nome funzione in §4.2

**Modifica minima al design doc:**
In §4.2, sostituire `_install_plugin_files_v3` con `_install_standalone_files_v3`
e aggiungere la nota: questa funzione gestisce sia `deployment_modes.standalone_files`
(Cat. B standalone) sia `plugin_files` (introdotto dal branch). Entrambe le logiche
migrano in `spark/plugins/installer.py`.

### Correzione P3 — Snippet init in §4.3

**Modifica al design doc:**

```python
# §4.3 — snippet corretto
# In SparkFrameworkEngine._init_runtime_objects(), dopo RegistryClient:
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
    registry_url=_REGISTRY_URL,  # costante da spark.core.constants
)
```

Note: `PluginManagerFacade` si inizializza come gli altri runtime objects,
in `_init_runtime_objects()` (non in `__init__`), per coerenza con il pattern lazy.

### Correzione P4 — RegistryClient constructor in §5 e §3

**Aggiunta al design doc §3.3 o §5:**
Documentare esplicitamente come `PluginManagerFacade` istanzia `RegistryClient`:

```python
# Dentro PluginManagerFacade.__init__:
self._registry = RegistryClient(
    github_root=workspace_root / ".github",
    registry_url=registry_url,
    cache_path=workspace_root / ".github" / ".scf-registry-cache.json",
)
```

Nessuna modifica a `RegistryClient` richiesta — solo il pattern di costruzione
deve essere documentato correttamente.

### Correzione P5 — Dual-tracking protocol in §3.2 e §6.1

**Aggiunta al design doc §6.1 (o nuova §6.4):**
Definire il contratto di coordinamento tra `PluginRegistry` e `ManifestManager`:

- Opzione A (consigliata): `PluginRegistry` wrappa `ManifestManager` per le scritture di
  ownership, eliminando il file `.spark-plugins` come store separato. Lo stato di installazione
  plugin (versione, source_repo, installed_at) viene aggiunto come campi extra nelle entry
  del manifest esistente. Un flag `installation_mode: plugin_manager` distingue le entry.
- Opzione B: mantiene `.spark-plugins` ma aggiorna ANCHE `.spark-manifest.json` ad ogni
  operazione `PluginRegistry.register()` e `PluginRegistry.unregister()`, usando
  `ManifestManager.upsert()` e `ManifestManager.remove_entry()`.

Opzione A è preferibile: elimina la duplicazione e sfrutta il preservation gate SHA già
implementato in `ManifestManager`.

### Correzione P6 — Boundary engine-embedded vs plugin in §4.1

**Aggiunta al design doc §4.1:**
Definire esplicitamente:
- `spark-base` è un **plugin** (gestito da `scf_install_plugin`, ha file Cat. A nel workspace).
- Non esiste un "pacchetto engine embedded" nel senso di spark-base. I file "embedded" sono
  quelli dell'engine stesso (template bootstrap, assets fase 6) dichiarati in `engine-manifest.json`.
- `scf_install_package` diventa un alias deprecated di `scf_install_plugin` (v3) o mantiene
  il path v2 legacy unchanged — uno dei due, non entrambi.

### Correzione P7 — Test impact in §7

**Modifica al design doc §7:**
Elencare esplicitamente i 3 file test con modifica NON minimale:
- `test_standalone_files_v3.py` — riscrivere fixture (nuovo target: `PluginInstaller`)
- `test_install_workspace_files.py` — riscrivere fixture (nuovo target: idem)
- `test_deployment_modes.py` — riscrivere i test `plugin_files` (nuovo tool: `scf_install_plugin`)

I restanti test (`test_package_lifecycle_v3.py`, `test_lifecycle.py`) richiedono solo
aggiornamento dei mock names.

---

## Sezione 4 — Versione v1.1 del design doc (sezioni modificate)

Le sezioni seguenti sostituiscono le corrispondenti sezioni del design doc v1.0.
Le sezioni non elencate (§1, §2, §6.2, §6.3, §8, §9) rimangono invariate.

### §4.2 (v1.1) — `spark/boot/lifecycle.py`

**Modifica:** rimuovere le funzioni `_install_workspace_files_v3` e
`_install_standalone_files_v3` dal mixin `_V3LifecycleMixin` in `spark/boot/lifecycle.py`.
Nota: non esiste una funzione chiamata `_install_plugin_files_v3` nel codebase.
La funzione `_install_standalone_files_v3` gestisce **sia** `deployment_modes.standalone_files`
**sia** `plugin_files` — entrambe le logiche migrano in `spark/plugins/installer.py`.

Le funzioni che rimangono in `lifecycle.py` (mixin `_V3LifecycleMixin`) sono:
- `_v3_runtime_state`
- `_is_github_write_authorized_v3`
- `_v3_repopulate_registry`
- `_remove_workspace_files_v3`
- `_install_package_v3` (orchestration level)
- `_remove_package_v3`
- `_update_package_v3`

### §4.3 (v1.1) — `spark/boot/engine.py`

**Modifica minima:** aggiungere l'inizializzazione di `PluginManagerFacade` come
runtime object in `_init_runtime_objects()`, dopo `RegistryClient`:

```python
# In SparkFrameworkEngine._init_runtime_objects():
# (aggiungere subito dopo self._registry_client = RegistryClient(...))
from spark.plugins import PluginManagerFacade  # noqa: PLC0415
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
    registry_url=_REGISTRY_URL,
)
```

Non aggiungere `_plugin_manager` al costruttore `__init__`: segue il pattern lazy
degli altri runtime objects.

### §5 (v1.1) — Invarianti Architetturali

Path corretti dei componenti da NON toccare:

| Componente          | Path reale                        | Metodo/classe              |
|---------------------|-----------------------------------|----------------------------|
| WorkspaceWriteGateway | `spark/manifest/gateway.py`     | `WorkspaceWriteGateway`    |
| ManifestManager     | `spark/manifest/manifest.py`      | `ManifestManager`          |
| RegistryClient      | `spark/registry/client.py`        | `RegistryClient`           |
| FrameworkInventory  | `spark/inventory/framework.py`    | `FrameworkInventory`       |
| WorkspaceLocator    | `spark/workspace/locator.py`      | `WorkspaceLocator`         |

Nota: nessun file in `spark/core/` va modificato (contiene solo constants, models, utils).

### §6.4 (v1.1) — Coordinamento `PluginRegistry` / `ManifestManager` (nuova sezione)

`PluginRegistry` NON gestisce un file di stato separato `.spark-plugins`.
Usa `ManifestManager.upsert()` / `ManifestManager.remove_entry()` per tracciare
ownership come avviene oggi per tutti i pacchetti, aggiungendo i metadati plugin
(source_repo, installed_at) come campi extra nelle entry del manifest.

Formato entry manifest per i plugin (campo `extras` aggiunto a `upsert()`):

```json
{
  "file": ".github/agents/code-Agent-Code.md",
  "owner": "scf-master-codecrafter",
  "version": "2.6.0",
  "sha256": "abc...",
  "installation_mode": "plugin_manager",
  "source_repo": "Nemex81/scf-master-codecrafter",
  "installed_at": "2026-05-08T09:00:00Z"
}
```

Il file `.github/.spark-plugins` descritto nella v1.0 non viene creato.

### §7 (v1.1) — Relazione con il Branch Corrente

Il branch `feature/dual-mode-manifest-v3.1` **non va mergiato su `main`** con
l'approccio attuale. Il lavoro esistente è riutilizzabile:

- `lifecycle.py` — `_install_standalone_files_v3` migra in `spark/plugins/installer.py`
  con refactoring minimo (estrae da mixin a classe standalone `PluginInstaller`)
- `tools_packages_install.py` — il payload response con `plugin_files_installed` e
  `standalone_files_written` rimane; cambia solo chi lo popola (`PluginManagerFacade`)
- **Test da aggiornare significativamente** (non solo fixture):
  - `test_standalone_files_v3.py` — riscrivere per usare `PluginInstaller` direttamente
  - `test_install_workspace_files.py` — stesso approccio
  - `test_deployment_modes.py` — i test `plugin_files` useranno `scf_install_plugin`
- I restanti test (`test_lifecycle.py`, `test_package_lifecycle_v3.py`) hanno modifiche
  minimali (mock names).

Il branch diventa la base per il Passo 1 dopo l'approvazione della v1.1 del design.

---

## Sezione 5 — Raccomandazione finale

### PROCEDI CON CORREZIONI

Il design è recuperabile. Nessun problema è architetturalmente insuperabile.
I tre problemi BLOCCANTI sono tutti errori di analisi (path sbagliati, nome funzione
sbagliato, snippet errato) corretti dalla v1.1 proposta in Sezione 4.
I quattro problemi RILEVANTI hanno correzioni concrete descritte in Sezione 3.

**Procedura raccomandata:**
1. Nemex81 approva o modifica la v1.1 proposta in Sezione 4 di questo report.
2. Copilot aggiorna `docs/SPARK-DESIGN-FullDecoupling-v1.0.md` alle sezioni v1.1
   (il file diventa v1.1 in frontmatter).
3. Nemex81 approva la checklist §8 del design doc aggiornato.
4. Copilot procede con il Passo 1 (crea `spark/plugins/` senza rimuovere nulla).

**Rischio residuo principale:** il confine "engine-embedded vs plugin" per `spark-base`
(PROBLEMA-6) deve essere chiarito da Nemex81 prima del Passo 2 della migrazione,
non necessariamente prima del Passo 1.

---

## Appendice — Mappa funzioni impattate

| Funzione/metodo | File attuale | Azione proposta |
|-----------------|--------------|-----------------|
| `_install_workspace_files_v3` | `spark/boot/lifecycle.py` (_V3LifecycleMixin) | Migra in `spark/plugins/installer.py` (PluginInstaller) |
| `_install_standalone_files_v3` | `spark/boot/lifecycle.py` (_V3LifecycleMixin) | Migra in `spark/plugins/installer.py` |
| `_remove_workspace_files_v3` | `spark/boot/lifecycle.py` (_V3LifecycleMixin) | Migra in `spark/plugins/remover.py` (PluginRemover) |
| `_get_deployment_modes` | `spark/packages/lifecycle.py` | Migra o rimane come utility condivisa |
| `scf_install_package` (v3 path) | `spark/boot/tools_packages_install.py` | Diventa thin facade → `PluginManagerFacade.install()` |
| `RegistryClient` | `spark/registry/client.py` | NON modificata — riusata da `PluginManagerFacade` |
| `ManifestManager` | `spark/manifest/manifest.py` | NON modificata — `PluginRegistry` usa `upsert()` esistente |
| `WorkspaceWriteGateway` | `spark/manifest/gateway.py` | NON modificata — riusata da `PluginInstaller` |
| `WorkspaceLocator` | `spark/workspace/locator.py` | NON modificata |
| `FrameworkInventory` | `spark/inventory/framework.py` | NON modificata |
