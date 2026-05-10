# REPORT Step 4 — Analisi e Strategia di Consolidamento

## Metadati

| Campo | Valore |
|-------|--------|
| Data | 2025-07-15 |
| Agente | spark-engine-maintainer |
| Branch | `feature/dual-mode-manifest-v3.1` |
| Suite al momento dell'analisi | 446 passed, 9 skipped, 0 failed |
| Prompt Step 4 | `docs/prompts/PROMPT-COPILOT-Step4-Consolidation-v1.0.md` |
| Riferimento Step 3 | `docs/reports/REPORT-Copilot-Step3-Implementation.md` |

---

## Executive Summary

L'analisi approfondita dello stato post-Step 3 rivela un sistema **funzionalmente
corretto**: la suite è verde, i componenti principali sono allineati all'architettura
target e non sono stati introdotti bug. Non esistono anomalie classificabili come ROSSO
(fonte di bug non intenzionale o regressione critica).

Sono stati identificati **sei gap formali** rispetto ai criteri di accettazione
del prompt Step 3, tutti classificati GIALLO (codice legacy o conformità incompleta).
Nessuno costituisce un blocco tecnico per l'apertura della PR.

Le due decisioni architetturali aperte (D1 e D2) richiedono approvazione esplicita
di Nemex81 prima di poter chiudere formalmente tutti i criteri.

**Raccomandazione**: aprire la PR in stato corrente, documentando i gap formali
come decisioni pendenti nella sezione "Decisioni aperte" della PR.

---

## Analisi Stato Attuale

### Stub lifecycle.py

File: `spark/boot/lifecycle.py` — classe `_V3LifecycleMixin`

| Metodo | Classificazione | Note |
|--------|----------------|------|
| `_install_workspace_files_v3` | **stub_deprecato** ✅ | Delega a `PluginInstaller.install_from_store()` |
| `_remove_workspace_files_v3` | **stub_deprecato** ✅ | Delega a `PluginRemover.remove_workspace_files()` |
| `_install_standalone_files_v3` | **attivo_residuo** ⚠️ | Contiene logica di routing (`_get_deployment_modes`), delega tramite catena stub |
| `_install_package_v3` | **attivo_residuo** (OK) | Logica di orchestrazione install, non scrive workspace direttamente |
| `_v3_repopulate_registry` | **attivo** (OK) | Popola registry MCP — non scrittura workspace |
| `_is_github_write_authorized_v3` | **attivo** (OK) | Guard autorizzazione |
| `_v3_runtime_state` | **attivo** (OK) | Factory di componenti runtime |

**Nota su `_install_standalone_files_v3`:** Il metodo è ancora attivo perché
gestisce il routing `deployment_modes.standalone_files` + `plugin_files` e li
converte in chiamate a `_install_workspace_files_v3` (stub). La logica di scrittura
fisica non è in lifecycle — è nello stub che delega correttamente. Tuttavia, il
criterio di accettazione 3 richiede che lifecycle contenga "solo stub deprecati per
le funzioni migrate". Questo criterio è **parzialmente soddisfatto**.

---

### Dual-backend PluginRegistry

File: `spark/plugins/registry.py`

**Domanda 1:** `register()` usa `ManifestManager` come backend primario?
→ **Sì**, se `manifest_manager` non è `None`. La condizione è esplicita in ogni
metodo: `if self._manifest_manager is not None: → _register_in_manifest()`.

**Domanda 2:** Esiste ancora un path che scrive `.spark-plugins`?
→ **Sì**. Il backend file-based (`_register_in_file()` → `_save_file()`) è ancora
presente e attivo quando `manifest_manager is None`.

**Domanda 3:** Attivazione del backend legacy?
→ Condizione esplicita e invertita: `manifest_manager is None` → file-based.
`manifest_manager is not None` → manifest-based. Non è un default silente.

**Domanda 4:** Quando viene rimosso il backend legacy?
→ Non è previsto un meccanismo automatico di rimozione. Il metodo
`migrate_from_manifest(mm)` consente la migrazione on-demand (esclude entries
con `installation_mode` = `"v3_store"` o `"plugin_manager"`). Il criterio 6
("nessun file `.spark-plugins` separato") è **parzialmente soddisfatto** —
il file legacy esiste ancora come percorso alternativo.

**Implicazione pratica:** in produzione, `PluginManagerFacade` passa sempre
`manifest_manager=self._manifest`, quindi `.spark-plugins` NON viene scritto
nel flusso normale. Il backend legacy resta per compatibilità con i test unitari
che istanziano `PluginRegistry(github_root)` senza `manifest_manager`.

---

### PluginManagerFacade in engine.py

File: `spark/boot/engine.py`

```python
# riga 279:
self._plugin_manager: Any | None = None  # PluginManagerFacade, inizializzato lazy

# righe 298-303 (in _init_runtime_objects()):
from spark.plugins.facade import PluginManagerFacade  # noqa: PLC0415
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
    registry_url=_REGISTRY_URL,
)
```

**Verifica snippet approvato:** ✅ corrisponde esattamente allo snippet del prompt Step 3.

**Istanziazioni dirette di PluginInstaller / PluginRemover fuori da facade.py:**
→ Nessuna trovata nell'engine. Solo `facade.py` istanzia `PluginInstaller` e `PluginRemover`.
Gli stub in `lifecycle.py` istanziano questi componenti inline (dentro lo stub),
ma questo è il pattern corretto per lo stub — non è un bypass del facade.

**Nota idempotenza `_init_runtime_objects`:** la funzione ha un early-return se
`self._manifest is not None`, quindi `_plugin_manager` è inizializzato solo alla
prima chiamata. Le chiamate successive fanno solo `cleanup_expired_sessions()`. ✅

---

### Separazione tool MCP

**`tools_plugins.py` — Universo B Plugin Manager:**

I tool `scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`, `scf_plugin_list`
usano `_make_facade(workspace_root, ctx.workspace_root)` che crea un `PluginManagerFacade`
fresco per ogni chiamata MCP. **Non usano `engine._plugin_manager`**.

Conseguenze:
- Non è un bug funzionale: il facade fresco e `engine._plugin_manager` hanno
  lo stesso comportamento per il workspace default.
- Il criterio 5 ("delega a `self._plugin_manager`") è **formalmente non soddisfatto**.
  In spirito è soddisfatto: i tool delegano al Plugin Manager, non a lifecycle.
- Il vantaggio del facade fresco è il supporto multi-workspace (il parametro
  `workspace_root` del tool può puntare a un workspace diverso da quello dell'engine).

**`tools_packages_install.py` — Universo A (store MCP):**

`scf_install_package` chiama `_install_package_v3()` → `_install_workspace_files_v3`
(stub) → `PluginInstaller.install_from_store()`. Questo percorso **scrive ancora
`workspace_files` nel workspace utente**. Il principio architetturale "il Server MCP
non scrive nel workspace" non è rispettato per Universo A.

Questa è la **Decisione D1** documentata nel report Step 3, ancora pendente.

**Sovrapposizione responsabilità:**

| Tool | Universo | Scrive workspace? |
|------|---------|------------------|
| `scf_install_package` | A (store) | ✅ Sì, tramite stub → `install_from_store()` |
| `scf_plugin_install` | B (plugin) | ✅ Sì, tramite facade → `install_files()` |

Entrambi i tool scrivono nel workspace — il boundary Universo A / Universo B è
implementato a livello di fonte (store locale vs GitHub HTTP), non a livello di
"chi scrive nel workspace".

---

### Censimento debito tecnico

#### VERDE — Pienamente allineato

| Componente | Stato |
|-----------|-------|
| `PluginInstaller.install_from_store()` | ✅ Preservation gate, SHA idempotency, batch write |
| `PluginRemover.remove_workspace_files()` | ✅ Dedup, preservation gate, delete via gateway |
| `_install_workspace_files_v3` (stub) | ✅ Delega corretta a `install_from_store()` |
| `_remove_workspace_files_v3` (stub) | ✅ Delega corretta a `remove_workspace_files()` |
| `PluginManagerFacade` in `_init_runtime_objects` | ✅ Snippet corretto |
| `schema.py` | ✅ Dataclass e eccezioni clean |
| `updater.py` — logica update | ✅ Remove → install → register |
| Suite test 446/9/0 | ✅ Nessuna regressione post-Step 3 |

#### GIALLO — Funzionale ma cleanup richiesto

| ID | Componente | Descrizione | File | Riga approssimativa |
|----|-----------|-------------|------|---------------------|
| G1 | `_install_standalone_files_v3` | Metodo attivo in lifecycle, non stub. Delega tramite catena ma contiene logica di routing | `spark/boot/lifecycle.py` | ~200-260 |
| G2 | Backend file-based `.spark-plugins` | Ancora presente in `PluginRegistry`; il criterio 6 richiede manifest-only | `spark/plugins/registry.py` | metodi `_register_in_file`, `_save_file`, `_load_from_file` |
| G3 | `_make_facade()` in tools_plugins | Crea facade fresco invece di riusare `engine._plugin_manager` | `spark/boot/tools_plugins.py` | riga 35-38 |
| G4 | `print(file=sys.stderr)` | Nei moduli `spark/plugins/` il logging usa `print(file=sys.stderr)` anziché `logging.getLogger("spark-framework-engine")` | `installer.py`, `remover.py`, `updater.py` | varie |
| G5 | Coverage manifest-backend | Nessun test copre direttamente il backend manifest di `PluginRegistry` (tutti i test usano `PluginRegistry(github_root)` senza `manifest_manager`) | `tests/test_plugin_manager_unit.py` | — |
| G6 | Test via engine stub | `test_standalone_files_v3.py` e `test_install_workspace_files.py` testano via `SparkFrameworkEngine` stub, non direttamente `PluginInstaller`/`PluginRemover` | `tests/test_standalone_files_v3.py`, `tests/test_install_workspace_files.py` | — |
| G7 | Nome report Step 3 | Il criterio 8 richiede `REPORT-Copilot-Step3-Final.md`, ma esiste solo `REPORT-Copilot-Step3-Implementation.md` | `docs/reports/` | — |

#### ROSSO — Nessuna anomalia bloccante identificata

Non sono stati trovati bug intenzionali, dipendenze circolari, stati corrotti
del manifest o regressioni introdotte in Step 3. Le questioni G1–G7 sono
problemi di conformità formale ai criteri, non problemi tecnici.

---

### Decisioni aperte da Step 3

Da `docs/reports/REPORT-Copilot-Step3-Implementation.md` sezione "Problemi aperti":

**D1 — `scf_install_package` e workspace_files:**
> `scf_install_package` continua a scrivere `workspace_files` nel workspace tramite `_install_workspace_files_v3` (ora stub → `PluginInstaller.install_from_store()`).

→ **PENDENTE** per Nemex81. Questa decisione determina se la conferma formale
"il Server MCP non scrive più file nel workspace utente" può essere data o meno.
Finché D1 rimane aperta, il criterio 8 del prompt Step 3 (report con conferme esplicite)
non può essere soddisfatto completamente.

**D2 — `spark-base` come plugin:**
> `spark-base` dichiara `workspace_files` ma non `plugin_files`. La sua migrazione rientra nello scope di Step 3?

→ **PENDENTE** per Nemex81. Nessun package-manifest.json reale (`scf-master-codecrafter`,
`scf-pycode-crafter`) dichiara `plugin_files` — tutti usano `workspace_files`.
La migrazione richiederebbe aggiornamento dei manifest nei repository esterni.

---

## Strategia di Consolidamento

### Interventi BLOCCANTI

**Nessuno.**

L'analisi non ha rilevato anomalie tecniche che costituiscano un blocco al merge.
La suite è verde, il codice è funzionalmente corretto, non ci sono bug noti.

---

### Cleanup GIALLI inclusi nel branch

**G7 — Creare `REPORT-Copilot-Step3-Final.md`** (< 5 righe, impatto zero su test):

Il file richiesto dal criterio 8 non esiste. La soluzione minima è creare un file
di redirect che indica il contenuto equivalente in `REPORT-Copilot-Step3-Implementation.md`
e documenta esplicitamente lo stato delle due conferme richieste dal prompt Step 3:

- *"il Server MCP non scrive più file nel workspace utente"* → **PARZIALMENTE VERA**
  per Universo B (plugin manager); NON vera per Universo A (`scf_install_package`).
  Decisione D1 pendente.
- *"i plugin installati via scf_install_plugin producono file fisici in .github/
  indipendentemente dal server MCP"* → **VERA** (facade fresco, nessuna dipendenza
  dal server MCP).

**G4 — `print(file=sys.stderr)` → `logging`** (< 5 righe per file):

Nei file `installer.py`, `remover.py`, `updater.py`. Non contamina stdout (MCP-safe),
ma non è allineato allo standard del codebase (`logging.getLogger("spark-framework-engine")`).
La modifica è meccanica e reversibile. Inclusa nel branch se approvata da Nemex81.

---

### Issue da aprire (debito tecnico rinviato)

| ID | Titolo issue | File coinvolto | Priorità |
|----|-------------|---------------|----------|
| I-1 | Stub-ificare `_install_standalone_files_v3` in lifecycle.py | `spark/boot/lifecycle.py` | POST-MERGE |
| I-2 | Rimuovere backend file-based `.spark-plugins` da PluginRegistry | `spark/plugins/registry.py` | POST-MERGE |
| I-3 | tools_plugins.py: usare `engine._plugin_manager` per workspace default | `spark/boot/tools_plugins.py` | POST-MERGE |
| I-4 | Aggiungere test per manifest-backend di PluginRegistry | `tests/test_plugin_manager_unit.py` | POST-MERGE |
| I-5 | Migrare test standalone_files e install_workspace_files a test diretti | `tests/test_standalone_files_v3.py`, `tests/test_install_workspace_files.py` | POST-MERGE |

---

### Verifica PR-readiness (checklist criteri Step 3)

| # | Criterio (da `PROMPT-COPILOT-Step3-Separation-AB-v1.0.md`) | Stato |
|---|--------------------------------------------------------------|-------|
| 1 | `installer.py` contiene logica scrittura (ex `_install_workspace_files_v3` e `_install_standalone_files_v3`) | **SODDISFATTO** — `install_from_store()` e `install_files()` presenti |
| 2 | `remover.py` contiene logica rimozione (ex `_remove_workspace_files_v3`) | **SODDISFATTO** — `remove_workspace_files()` presente |
| 3 | `lifecycle.py` contiene solo stub deprecati (non logica attiva di scrittura) | **PARZIALMENTE SODDISFATTO** — `_install_workspace_files_v3` e `_remove_workspace_files_v3` sono stub; `_install_standalone_files_v3` è ancora attivo (G1) |
| 4 | `engine.py` inizializza `PluginManagerFacade` in `_init_runtime_objects()` | **SODDISFATTO** — snippet approvato presente alle righe 298-303 |
| 5 | `tools_plugins.py` delega a `self._plugin_manager` (non a lifecycle) | **PARZIALMENTE SODDISFATTO** — delega al Plugin Manager (non a lifecycle) ✅; usa facade fresco invece di `engine._plugin_manager` ⚠️ (G3) |
| 6 | `registry.py` usa `ManifestManager.upsert()` / `remove_entry()` — nessun `.spark-plugins` | **PARZIALMENTE SODDISFATTO** — dual-backend: manifest (preferito) + file (legacy); backend file ancora presente (G2) |
| 7 | Tutti i test passano | **SODDISFATTO** — 446 passed, 9 skipped, 0 failed |
| 8 | `REPORT-Copilot-Step3-Final.md` con conferme esplicite | **NON SODDISFATTO** — file con nome diverso; conferma "MCP non scrive workspace" non dabile completamente senza risoluzione D1 (G7) |
| 9 | PR aperta (non mergiata) | **NON ESEGUITO** |

---

### Piano conclusivo Step A → D

**Step A — Interventi BLOCCANTI:** Nessuno.

**Step B — Cleanup GIALLI inclusi nel branch** (richiede approvazione Nemex81):

- B1: Creare `docs/reports/REPORT-Copilot-Step3-Final.md` con stato delle conferme
  e riferimento a `REPORT-Copilot-Step3-Implementation.md`. *(G7)*
- B2: Sostituire `print(file=sys.stderr)` con `logging.getLogger(...)` in
  `installer.py`, `remover.py`, `updater.py`. *(G4)* — opzionale, impatto MCP nullo.

**Step C — Apertura issue** (dopo la PR, per tracciamento debito tecnico):
Aprire le 5 issue elencate nella tabella "Issue da aprire" sopra.

**Step D — Apertura PR su `main`:**
Aprire la PR con:
- Titolo: `feat: Full Decoupling Architecture v2.0 — Consolidamento finale post-Step 3`
- Corpo: checklist criteri, link ai report, sezione "Decisioni aperte" per D1, D2, D3.
- Stato: NON mergiare senza approvazione di Nemex81.

---

## Conclusione

### Dichiarazione di merge-readiness

Il branch `feature/dual-mode-manifest-v3.1` è in stato di **merge-ready condizionale**.

Condizioni soddisfatte:
- ✅ Nessuna anomalia tecnica bloccante.
- ✅ Suite 446 passed, 9 skipped, 0 failed.
- ✅ Architettura target implementata nella sostanza: Plugin Manager autonomo,
  stubs lifecycle, PluginManagerFacade nel boot sequence.

Condizioni non completamente soddisfatte (gap formali):
- ⚠️ 3 criteri di accettazione Step 3 sono "PARZIALMENTE SODDISFATTI" (criteri 3, 5, 6).
- ⚠️ 1 criterio non soddisfatto (criterio 8 — report Final.md).
- ⚠️ 1 criterio non eseguito (criterio 9 — PR non ancora aperta).

I gap formali sono documentati e non costituiscono rischi tecnici per il merge.
Il cleanup post-merge è tracciato nelle issue proposte.

---

### Decisioni che richiedono approvazione di Nemex81

| ID | Domanda | Impatto se risposta "Sì" |
|----|---------|--------------------------|
| D1 | `scf_install_package` deve smettere di scrivere `workspace_files` nel workspace? | Rimuovere stub chain in lifecycle + aggiornare logica scf_install_package |
| D2 | `spark-base` (e altri pacchetti) devono migrare da `workspace_files` a `plugin_files`? | Aggiornare `package-manifest.json` in repo esterni + pipeline install |
| D3 | `tools_plugins.py` deve usare `engine._plugin_manager` per il workspace default? | ~10 righe in `tools_plugins.py`, perdita capacità multi-workspace per il caso default |
| B1 | Creare `REPORT-Copilot-Step3-Final.md` in questo branch? | Sì → 1 file nuovo, impatto zero su test |
| B2 | Convertire `print(file=sys.stderr)` → `logging` in `spark/plugins/`? | Sì → ~15 righe, impatto zero su test |

---

*Report generato da spark-engine-maintainer — Step 4 Consolidamento Finale.*
*Branch: `feature/dual-mode-manifest-v3.1` — Nessun file di codice modificato in questo step.*
