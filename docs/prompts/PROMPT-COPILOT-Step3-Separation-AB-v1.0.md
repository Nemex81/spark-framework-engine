# PROMPT COPILOT — Step 3: Separazione Netta Universo A/B
## Validazione Reference End-to-End + PR Upstream

**Autore:** Perplexity AI (Coordinatore SPARK Council)
**Data:** 2026-05-08
**Branch target:** `feature/dual-mode-manifest-v3.1`
**Approvazione:** Nemex81 (coordinatore umano)
**Versione prompt:** 1.0
** mode: agent **
** execute_mode: autonomus **

---

## CONTESTO OBBLIGATORIO DA LEGGERE PRIMA DI QUALSIASI AZIONE

Prima di eseguire qualunque task, leggi integralmente i seguenti file in ordine:

1. `docs/reports/REPORT-Copilot-FullDecoupling-Issues.md` — 8 problemi rilevati nella v1.0 del design, con correzioni v1.1 approvate. **Questi path e nomi sono quelli reali da usare ovunque.**
2. `docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md` — stato dell'implementazione dopo Step 1 e Step 2.
3. `docs/reports/SPARK-REPORT-DualMode-Architecture-v1.0.md` — design architetturale approvato dal coordinatore.
4. `spark/plugins/__init__.py`, `spark/plugins/facade.py`, `spark/plugins/installer.py`, `spark/plugins/remover.py`, `spark/plugins/updater.py`, `spark/plugins/registry.py`, `spark/plugins/schema.py` — modulo Plugin Manager già implementato.
5. `spark/boot/lifecycle.py` — identifica le funzioni del mixin `_V3LifecycleMixin` ancora presenti.
6. `spark/boot/engine.py` — verifica l'attuale `_init_runtime_objects()`.
7. `spark/boot/tools_plugins.py` — tool MCP Plugin Manager già registrato.
8. `spark/manifest/gateway.py`, `spark/manifest/manifest.py`, `spark/registry/client.py` — componenti invarianti da NON modificare.

**REGOLA ASSOLUTA:** non usare mai i path `spark/core/workspace_write_gateway.py`, `spark/core/manifest_manager.py`, `spark/core/registry_client.py`, `spark/core/framework_inventory.py`, `spark/core/workspace_locator.py`. Non esistono. I path reali sono quelli elencati nel punto 8 e nel report Issues §5(v1.1).

---

## OBIETTIVO DELLO STEP 3

Completare la separazione netta tra i due universi:

- **Universo A — Plugin Manager** (`spark/plugins/`): unico responsabile della scrittura di file fisici nel workspace utente (`.github/`). Opera in modo completamente autonomo dall'engine MCP.
- **Universo B — Server MCP** (`spark/packages/`, `spark/boot/`): serve risorse embedded via URI MCP. Non scrive MAI file nel workspace utente dopo questo step.

Al termine dello Step 3 deve essere possibile:
1. Installare un plugin (`scf_install_plugin`) e trovare i file fisici in `.github/` nel workspace utente senza che l'engine abbia avviato alcun processo di bootstrap.
2. Servire risorse MCP (`agents://`, `skills://`, `instructions://`, `prompts://`) senza che il server scriva nulla nel filesystem del workspace.
3. Aprire una PR su `main` pulita, con tutti i test passanti.

---

## ARCHITETTURA TARGET — PATH REALI APPROVATI

Usa esclusivamente questi path (corretti post-report Issues):

| Componente | Path reale | Classe |
|---|---|---|
| WorkspaceWriteGateway | `spark/manifest/gateway.py` | `WorkspaceWriteGateway` |
| ManifestManager | `spark/manifest/manifest.py` | `ManifestManager` |
| RegistryClient | `spark/registry/client.py` | `RegistryClient` |
| FrameworkInventory | `spark/inventory/framework.py` | `FrameworkInventory` |
| WorkspaceLocator | `spark/workspace/locator.py` | `WorkspaceLocator` |
| PluginManagerFacade | `spark/plugins/facade.py` | `PluginManagerFacade` |
| PluginInstaller | `spark/plugins/installer.py` | `PluginInstaller` |
| PluginRemover | `spark/plugins/remover.py` | `PluginRemover` |
| PluginUpdater | `spark/plugins/updater.py` | `PluginUpdater` |
| PluginRegistry | `spark/plugins/registry.py` | `PluginRegistry` |

### Init corretto di PluginManagerFacade (approvato dalla v1.1)

```python
# In SparkFrameworkEngine._init_runtime_objects()
# Aggiungere DOPO self._registry_client = RegistryClient(...)
from spark.plugins import PluginManagerFacade  # noqa: PLC0415
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
    registry_url=_REGISTRY_URL,  # costante da spark.core.constants
)
```

### Init corretto di RegistryClient dentro PluginManagerFacade

```python
# Dentro PluginManagerFacade.__init__:
self._registry = RegistryClient(
    github_root=workspace_root / ".github",
    registry_url=registry_url,
    cache_path=workspace_root / ".github" / ".scf-registry-cache.json",
)
```

### Coordinamento PluginRegistry / ManifestManager (da PROBLEMA-5 v1.1)

`PluginRegistry` NON crea un file `.spark-plugins` separato.
Usa `ManifestManager.upsert()` e `ManifestManager.remove_entry()` per tracciare
ownership dei file plugin, aggiungendo i campi extra seguenti alle entry manifest:

```json
{
  "file": ".github/agents/xxx.agent.md",
  "owner": "scf-master-codecrafter",
  "version": "2.6.0",
  "sha256": "abc...",
  "installation_mode": "plugin_manager",
  "source_repo": "Nemex81/scf-master-codecrafter",
  "installed_at": "2026-05-08T09:00:00Z"
}
```

### Boundary spark-base (da PROBLEMA-6 v1.1)

`spark-base` è un **plugin** gestito da `scf_install_plugin`.
Non esiste categoria "engine embedded" nel senso di pacchetti con `workspace_files`.
`scf_install_package` (path v2 legacy) rimane invariato per compatibilità storica
ma NON scrive più file Cat. A/B nel workspace: quella responsabilità è di `scf_install_plugin`.

---

## TASK SEQUENZIALI — ESEGUIRE IN ORDINE

### TASK-1 — Verifica stato attuale (sola lettura, nessuna modifica)

**Azioni:**

1. Leggi `spark/boot/lifecycle.py` e identifica quali funzioni del mixin `_V3LifecycleMixin` scrivono ancora file nel workspace (target: `_install_workspace_files_v3`, `_install_standalone_files_v3`).
2. Leggi `spark/boot/engine.py` e verifica se `PluginManagerFacade` è già inizializzato in `_init_runtime_objects()`.
3. Leggi `spark/plugins/installer.py` e verifica se `_install_workspace_files_v3` e `_install_standalone_files_v3` sono già state migrate o se contiene una reimplementazione equivalente.
4. Leggi `spark/plugins/registry.py` e verifica se usa `ManifestManager.upsert()` oppure scrive un file `.spark-plugins` separato.
5. Leggi `spark/boot/tools_packages_install.py` e verifica se `scf_install_package` delega già a `PluginManagerFacade` oppure chiama ancora direttamente i metodi del mixin.

**Output atteso:** un elenco preciso di cosa è già allineato e cosa richiede intervento, prima di toccare qualsiasi file.

**Scrivi il risultato in:** `docs/reports/REPORT-Copilot-Step3-Audit.md`

---

### TASK-2 — Migrazione logica scrittura da lifecycle.py a spark/plugins/

**Condizione di partenza:** eseguire solo dopo che TASK-1 ha confermato cosa manca.

**Azioni (solo se necessario, basandoti sull'audit di TASK-1):**

1. Se `_install_workspace_files_v3` e/o `_install_standalone_files_v3` sono ancora in `lifecycle.py` e NON sono già in `spark/plugins/installer.py`:
   - Sposta la logica in `PluginInstaller` (classe in `spark/plugins/installer.py`).
   - Il metodo in `lifecycle.py` diventa uno stub vuoto con commento `# DEPRECATED: logica migrata in spark/plugins/installer.py`.
   - NON cancellare il metodo stub: serve per evitare crash negli import esistenti fino al cleanup finale.

2. Se `_remove_workspace_files_v3` è ancora in `lifecycle.py` e NON è già in `spark/plugins/remover.py`:
   - Stessa procedura: migra in `PluginRemover`, stub in `lifecycle.py`.

3. Verifica che `PluginInstaller` e `PluginRemover` usino `WorkspaceWriteGateway` (da `spark/manifest/gateway.py`) e `ManifestManager` (da `spark/manifest/manifest.py`) — **non reimplementare** la logica di write-gate e SHA256 già presente in queste classi.

**ATTENZIONE:** se durante questa fase rilevi dipendenze circolari o import rotti, trattali come anomalia (vedi sezione GESTIONE ANOMALIE a fondo prompt) prima di continuare.

---

### TASK-3 — Integrazione PluginManagerFacade in engine.py

**Condizione:** eseguire dopo TASK-2.

**Azioni:**

1. Aggiungi l'inizializzazione di `PluginManagerFacade` in `SparkFrameworkEngine._init_runtime_objects()` usando lo snippet approvato nella sezione ARCHITETTURA TARGET.
2. Verifica che `scf_install_plugin` in `spark/boot/tools_plugins.py` acceda a `self._plugin_manager` (istanza di `PluginManagerFacade`) e non chiami direttamente metodi di `lifecycle.py`.
3. Se `scf_install_package` in `tools_packages_install.py` chiama ancora direttamente `_install_workspace_files_v3` o `_install_standalone_files_v3`, aggiorna la chiamata per delegare a `self._plugin_manager.install()` passando il manifest package come input.

**REGOLA:** non modificare la firma pubblica MCP di `scf_install_package` né di `scf_install_plugin`. Solo il corpo interno.

---

### TASK-4 — Allineamento PluginRegistry / ManifestManager

**Condizione:** eseguire dopo TASK-3.

**Azioni:**

1. Leggi `spark/plugins/registry.py` e verifica se crea un file `.spark-plugins` separato.
2. Se sì: refactora `PluginRegistry` per eliminare il file `.spark-plugins` e usare invece `ManifestManager.upsert()` con i campi extra (`installation_mode`, `source_repo`, `installed_at`) come definito nella sezione ARCHITETTURA TARGET.
3. Assicurati che `PluginRegistry.unregister()` chiami `ManifestManager.remove_entry()` al posto di scrivere nel file separato.
4. La cache del registry upstream (`RegistryClient`) rimane su `.github/.scf-registry-cache.json` — questo è distinto dallo stato di installazione plugin.

---

### TASK-5 — Validazione reference end-to-end

**Condizione:** eseguire dopo TASK-4.

**Obiettivo:** verificare che un plugin installato tramite `scf_install_plugin` produca file fisici raggiungibili da Copilot via `#file:` reference senza dipendere dal server MCP attivo.

**Azioni:**

1. Esegui (o simula con test) il flusso completo:
   - `scf_install_plugin(package_id="scf-master-codecrafter", workspace_root=<path>)`
   - Verifica che i file dichiarati in `workspace_files` del `package-manifest.json` di `scf-master-codecrafter` siano scritti fisicamente in `.github/`.
   - Verifica che `.github/.spark-manifest.json` contenga le entry con `installation_mode: "plugin_manager"`.

2. Esegui il flusso server MCP puro:
   - Chiedi al server una risorsa `agents://spark-assistant` o equivalente.
   - Verifica che il serving avvenga senza scrivere nulla nel filesystem del workspace.

3. Aggiorna i test impattati identificati nel report Issues §7 (v1.1):
   - `test_standalone_files_v3.py` — riscrivere fixture per istanziare `PluginInstaller` direttamente.
   - `test_install_workspace_files.py` — stesso approccio.
   - `test_deployment_modes.py` — i test `plugin_files` devono usare `scf_install_plugin`.
   - `test_lifecycle.py`, `test_package_lifecycle_v3.py` — aggiornamento mock names minimale.

4. Tutti i test devono passare (`pytest` senza failure) prima di procedere al TASK-6.

---

### TASK-6 — Apertura PR su main

**Condizione:** eseguire SOLO se TASK-5 ha confermato tutti i test verdi.

**Azioni:**

1. Scrivi il report finale di Step 3 in `docs/reports/REPORT-Copilot-Step3-Final.md` con:
   - Lista file modificati con motivazione.
   - Lista test aggiornati con tipo di modifica (fixture / riscrittura).
   - Conferma esplicita: "il Server MCP non scrive più file nel workspace utente".
   - Conferma esplicita: "i plugin installati via scf_install_plugin producono file fisici in .github/ indipendentemente dal server MCP".
   - Eventuali work-in-progress o decisioni rimandate a Nemex81.

2. Apri la PR da `feature/dual-mode-manifest-v3.1` → `main` con titolo:
   `feat: Full Decoupling Architecture v2.0 — Plugin Manager autonomo + Server MCP puro`

3. Nel corpo della PR includi:
   - Link ai report: `REPORT-Copilot-FullDecoupling-Issues.md`, `REPORT-Copilot-FullDecoupling-v2.0-Validation.md`, `REPORT-Copilot-Step3-Final.md`.
   - Checklist degli obiettivi raggiunti (formato checkbox markdown).
   - Sezione "Decisioni aperte" per tutto ciò che richiede approvazione di Nemex81.

**NON mergiare la PR.** La decisione di merge spetta esclusivamente a Nemex81.

---

## GESTIONE ANOMALIE IN CORSO D'OPERA

Durante l'esecuzione dei task sopra, potresti incontrare problemi non previsti.
Usa questa procedura:

### Quando sospendere il task principale

Sospendi il task corrente e apri un **task parallelo di correzione** se incontri:

- Import rotto che causa `ModuleNotFoundError` o `ImportError` all'avvio dell'engine.
- Dipendenza circolare tra moduli (`spark/plugins/` → `spark/boot/` → `spark/plugins/`).
- Test che fallisce per motivi non correlati allo step corrente (test rotto preesistente).
- File mancante che era atteso dal codebase (es. un modulo referenziato ma non presente nel repo).
- Conflitto di stato tra `ManifestManager` e `PluginRegistry` che produce entry duplicate o corrotte in `.spark-manifest.json`.

### Procedura task parallelo

1. **Documenta l'anomalia** — scrivi una nota in `docs/reports/REPORT-Copilot-Step3-Audit.md` nella sezione "Anomalie rilevate" con: descrizione, file coinvolti, impatto sul task principale.
2. **Risolvi in isolamento** — lavora sulla correzione senza toccare i file del task principale sospeso.
3. **Verifica la correzione** — esegui i test rilevanti per confermare che l'anomalia è risolta.
4. **Riprendi il task principale** — torna esattamente al punto in cui avevi sospeso.

### Anomalie che non richiedono sospensione

Gestisci inline (senza sospendere) se si tratta di:
- Warning non bloccanti.
- Aggiornamento di un import path da `spark/core/X` al path reale (correzione da PROBLEMA-1 del report Issues).
- Aggiornamento di un nome funzione errato (correzione da PROBLEMA-2).
- Aggiornamento di uno snippet init (correzione da PROBLEMA-3).

---

## LIMITI E DIVIETI

- **Non mergiare mai la PR senza approvazione esplicita di Nemex81.**
- **Non modificare** `spark/manifest/gateway.py`, `spark/manifest/manifest.py`, `spark/registry/client.py`, `spark/workspace/locator.py`, `spark/inventory/framework.py` — sono invarianti architetturali.
- **Non modificare** la firma pubblica MCP (nome tool, parametri input/output JSON) di nessun tool esistente.
- **Non cancellare** i metodi stub deprecati in `lifecycle.py` — lasciarli con commento fino al cleanup esplicito.
- **Non usare `print()` o scrivere su `stdout`** — il canale JSON-RPC è esclusivo. Usa `sys.stderr` per logging con formato `[SPARK-ENGINE][DEBUG/INFO/ERROR] Messaggio`.
- **Non prendere decisioni architetturali autonome** — se trovi uno scenario non coperto da questo prompt, scrivi la domanda in `docs/reports/REPORT-Copilot-Step3-Final.md` nella sezione "Decisioni aperte" e aspetta approvazione.

---

## CRITERI DI ACCETTAZIONE FINALI

Il branch è pronto per la PR quando tutte queste condizioni sono vere:

- [ ] `spark/plugins/installer.py` contiene la logica di scrittura file (ex `_install_workspace_files_v3` e `_install_standalone_files_v3`).
- [ ] `spark/plugins/remover.py` contiene la logica di rimozione file (ex `_remove_workspace_files_v3`).
- [ ] `spark/boot/lifecycle.py` contiene solo stub deprecati per le funzioni migrate (non logica attiva di scrittura workspace).
- [ ] `spark/boot/engine.py` inizializza `PluginManagerFacade` in `_init_runtime_objects()` con lo snippet approvato.
- [ ] `spark/boot/tools_plugins.py` delega a `self._plugin_manager` (non a metodi di `lifecycle.py`).
- [ ] `spark/plugins/registry.py` usa `ManifestManager.upsert()` / `remove_entry()` — nessun file `.spark-plugins` separato.
- [ ] Tutti i test passano (`pytest` zero failures).
- [ ] `docs/reports/REPORT-Copilot-Step3-Final.md` scritto con conferme esplicite.
- [ ] PR aperta (non mergiata) con link ai report e sezione "Decisioni aperte".

---

*Prompt generato da Perplexity AI (Coordinatore SPARK Council) — approvato da Nemex81.*
*Integra correzioni da REPORT-Copilot-FullDecoupling-Issues.md (8 problemi, tutti indirizzati).*
