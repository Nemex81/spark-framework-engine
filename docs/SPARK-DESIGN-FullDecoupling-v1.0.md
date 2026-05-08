# SPARK Framework — Design Document: Full Decoupling Architecture v1.0

**Stato:** PROPOSTA — In attesa di approvazione da Nemex81
**Autore:** Perplexity AI (Coordinatore)
**Data:** 2026-05-08
**Branch di riferimento:** `feature/dual-mode-manifest-v3.1` (base tecnica)
**Sostituisce:** approccio Dual-Mode Manifest v3.1 (non mergiare su main)

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

### 1.2 La soluzione: separazione per responsabilità

Questo documento descrive un'architettura alternativa basata sul principio di singola
responsabilità applicato a livello di sistema:

- Il **Server MCP** fa una cosa sola: esporre risorse interne via protocollo MCP.
- Il **Plugin Manager** fa una cosa sola: gestire file di plugin nel filesystem
  del workspace utente, comunicando direttamente con registro e repo GitHub.

I due sistemi sono indipendenti. Il Plugin Manager non dipende dal processo MCP per
funzionare. Il Server MCP non conosce i repo esterni né scrive nel workspace.

---

## 2. Architettura Target

### 2.1 Visione a due livelli

```
+----------------------------------------------------------+
|  LIVELLO 1 — Server MCP (spark-framework-engine.py)     |
|                                                          |
|  Responsabilità UNICA: esporre risorse interne via MCP   |
|                                                          |
|  Pacchetti embedded (sola lettura, non modificabili):    |
|    spark-base/     -> agenti base, istruzioni bootstrap  |
|    (futuri pack interni engine)                          |
|                                                          |
|  Tool MCP esposti:                                       |
|    scf://runtime, agents://, skills://, instructions://  |
|    prompts://, scf_get_resource, scf_list_resources      |
|    scf_runtime_status, scf_bootstrap_workspace           |
|    + tool facade Plugin Manager (delega al Livello 2)    |
|                                                          |
|  NON scrive mai nel workspace utente.                    |
|  NON conosce registry.json ne repo GitHub.               |
+--------------------+-------------------------------------+
                     |  delega chiamate plugin via
                     |  interfaccia pubblica PluginManagerFacade
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
|  Ha un proprio file di stato: .github/.spark-plugins     |
+----------------------------------------------------------+
```

### 2.2 Flusso di una installazione plugin (nuovo comportamento)

```
Utente -> Copilot Agent -> scf_install_plugin (tool MCP)
    |
    +-> PluginManagerFacade.install(pkg_id, workspace_path)
           |
           +-- RegistryClient.fetch_manifest(pkg_id)
           |       +-> HTTP GET registry.json -> GitHub repo
           |
           +-- PluginInstaller.download(manifest, workspace_path)
           |       +-> HTTP GET asset file da repo sorgente
           |
           +-- WorkspaceWriteGateway.write_files(plugin_files)
           |       +-> preservation gate SHA-256 (invariante)
           |
           +-- PluginRegistry.register(pkg_id, version, files)
                   +-> aggiorna .github/.spark-plugins (JSON)
```

### 2.3 Flusso di lettura risorsa MCP (comportamento invariato)

```
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

```
spark/plugins/
+-- __init__.py           # esporta PluginManagerFacade
+-- facade.py             # PluginManagerFacade — punto di accesso unico
+-- registry.py           # PluginRegistry — stato locale .spark-plugins
+-- installer.py          # PluginInstaller — download + scrittura workspace
+-- remover.py            # PluginRemover — rimozione simmetrica
+-- updater.py            # PluginUpdater — confronto versioni
+-- schema.py             # dataclass PluginManifest, PluginRecord
```

### 3.2 File di stato locale: `.github/.spark-plugins`

Formato JSON, gestito esclusivamente da `PluginRegistry`. Non è un file di
configurazione utente — è lo stato interno del Plugin Manager.

```json
{
  "schema_version": "1.0",
  "installed": {
    "scf-master-codecrafter": {
      "version": "2.6.0",
      "source_repo": "Nemex81/scf-master-codecrafter",
      "installed_at": "2026-05-08T09:00:00Z",
      "files": [
        ".github/agents/copilot-orchestrator.agent.md",
        ".github/agents/spark-assistant.agent.md"
      ],
      "file_hashes": {
        ".github/agents/copilot-orchestrator.agent.md": "sha256:abc123..."
      }
    }
  }
}
```

### 3.3 Interfaccia pubblica `PluginManagerFacade`

Questa è la superficie di contatto tra il Server MCP (Livello 1) e il Plugin Manager
(Livello 2). È l'unico punto che il codice dell'engine deve conoscere.

```python
class PluginManagerFacade:
    """Punto di accesso unico al Plugin Manager dal Server MCP.

    Args:
        workspace_path: Path assoluto alla root del workspace utente.
        registry_url: URL del registry.json remoto (dal config engine).

    Note:
        Tutti i metodi sono sincroni e restituiscono dict serializzabili
        in JSON per essere usati direttamente come payload MCP tool response.
    """

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

---

## 4. Moduli da Modificare

### 4.1 `spark/boot/tools_packages_install.py`

**Modifica:** i tool MCP `scf_install_package`, `scf_remove_package`,
`scf_update_package` diventano **facade thin** che delegano a `PluginManagerFacade`.
Tutta la logica di scrittura filesystem esce da questo file.

**Prima (Dual-Mode ibrido):**

```python
# logica workspace, plugin_files, preservation gate — tutto qui dentro
async def scf_install_package(pkg_id: str, ...):
    result = _install_package_v3_into_store(...)
    if manifest.get("plugin_files"):
        _install_workspace_files_v3(...)
    return build_response(result)
```

**Dopo (Full Decoupling):**

```python
# thin facade — zero logica filesystem
async def scf_install_plugin(pkg_id: str, ...):
    result = _plugin_manager.install(pkg_id)
    return result  # dict gia serializzabile
```

**Nota:** il vecchio `scf_install_package` rimane per i pacchetti engine embedded
(spark-base e simili) che non sono plugin — sono risorse MCP interne e non vanno
nel workspace utente. I due tool hanno nomi diversi per distinguere il contesto.

### 4.2 `spark/boot/lifecycle.py`

**Modifica:** rimuovere le funzioni `_install_workspace_files_v3`,
`_install_plugin_files_v3` e la logica `plugin_files` introdotta da Copilot nel
branch corrente. Quella logica migra in `spark/plugins/installer.py`.

Le funzioni che rimangono in `lifecycle.py` sono solo quelle relative allo store
interno dell'engine: `_install_package_v3_into_store`, `_load_package_from_store`,
`_unload_package_from_store`.

### 4.3 `spark/boot/engine.py`

**Modifica minima:** inizializzazione di `PluginManagerFacade` durante il boot,
passata come dipendenza ai tool che la usano. Una riga nel costruttore dell'engine.

```python
# In SparkEngine.__init__ o equivalente, dopo WorkspaceLocator:
self._plugin_manager = PluginManagerFacade(
    workspace_path=self._workspace_locator.workspace_path,
    registry_url=self._config.registry_url
)
```

---

## 5. Invarianti Architetturali (non si toccano)

Questi componenti non vengono modificati in nessun task:

- `WorkspaceWriteGateway` — il Plugin Manager la usa tramite interfaccia pubblica
- `ManifestManager` — il Plugin Manager la usa tramite interfaccia pubblica
- `RegistryClient` — viene riutilizzato dentro `spark/plugins/registry.py`
- `FrameworkInventory` — gestisce solo risorse MCP interne, non sa dei plugin
- `WorkspaceLocator` — fornisce il `workspace_path` al Plugin Manager via engine

---

## 6. Compatibilità e Migrazione

### 6.1 Gestione backward compatibility

I workspace utente esistenti che hanno gia file installati tramite `workspace_files`
(schema v3.0) non vengono rotti. Al primo avvio post-migrazione, `PluginRegistry`
scansiona `.github/` e ricostruisce `.github/.spark-plugins` se assente, registrando
i file esistenti come "installati senza metadati" con flag `migrated: true`.

### 6.2 Schema manifest dei pacchetti repo

I `package-manifest.json` nei repo `scf-master-codecrafter` e `scf-pycode-crafter`
vengono semplificati: il campo `plugin_files` (introdotto da Copilot nel branch
corrente) diventa l'unico modo per dichiarare i file fisici del plugin. Il campo
`workspace_files` viene deprecato con un warning nel PluginInstaller se trovato
in un manifest v3.0.

### 6.3 Ordine di migrazione raccomandato

La migrazione si esegue in tre passi graduali, ognuno deployabile indipendentemente:

**Passo 1 — Crea `spark/plugins/` senza rimuovere nulla** (rischio: BASSO)

Il Plugin Manager esiste e funziona in parallelo al sistema esistente.
I test passano perché non si tocca nulla di attivo.

**Passo 2 — Collega i tool MCP al Plugin Manager** (rischio: MEDIO)

I tool `scf_install_plugin` e `scf_remove_plugin` delegano al Plugin Manager.
I vecchi `scf_install_package` rimangono come alias deprecated sui pacchetti engine.

**Passo 3 — Rimuovi la logica ibrida da `lifecycle.py`** (rischio: MEDIO)

Le funzioni `plugin_files` escono dal lifecycle e vengono rimosse.
Questo è il passo che chiude la separazione.

---

## 7. Relazione con il Branch Corrente

Il branch `feature/dual-mode-manifest-v3.1` **non va mergiato su `main`** con
l'approccio attuale. Il lavoro di Copilot non è pero sprecato:

- `lifecycle.py` — la logica `_install_plugin_files_v3` migra in `spark/plugins/installer.py`
- `tools_packages_install.py` — il payload response con `plugin_files_written` rimane,
  cambia solo chi lo popola
- I nuovi test (`test_standalone_files_v3.py`, `test_install_workspace_files.py`,
  `test_deployment_modes.py`) rimangono validi con minime modifiche ai fixture

Il branch diventa la base di sviluppo per il Passo 1 della migrazione.

---

## 8. Checklist Approvazione (per Nemex81)

Prima che Copilot proceda con l'implementazione, approvare esplicitamente:

- [ ] Struttura del package `spark/plugins/` con i 6 moduli descritti in §3.1
- [ ] Formato di `.github/.spark-plugins` descritto in §3.2
- [ ] Firma pubblica di `PluginManagerFacade` descritta in §3.3
- [ ] Distinzione `scf_install_package` (engine) vs `scf_install_plugin` (workspace) in §4.1
- [ ] Strategia migrazione a 3 passi in §6.3
- [ ] Branch `feature/dual-mode-manifest-v3.1` come base per il Passo 1

---

## 9. Decisioni Aperte (richiedono input di Nemex81)

**D1 — Nome del file di stato locale**

`.github/.spark-plugins` è nascosto e nella cartella già monitorata da SPARK.
Alternativa: `spark-plugins.lock` nella root del workspace (più visibile, stile npm).
Impatto: nessuno sul codice, solo convenzione.

**D2 — Comportamento in assenza di connessione internet**

Il Plugin Manager scarica da GitHub. Se offline:

- Opzione A: fallisce con errore chiaro `NO_CONNECTIVITY`
- Opzione B: usa una cache locale degli ultimi manifest scaricati

Impatto: complessità del `RegistryClient`.

**D3 — Autenticazione repo privati**

I repo `scf-*` sono pubblici oggi. Se diventassero privati, il Plugin Manager
avrebbe bisogno di un token GitHub. Gestirlo ora o rimandare?
Impatto: aggiunta di un parametro `github_token` opzionale a `PluginManagerFacade`.
