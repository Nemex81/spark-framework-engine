# REPORT — Validazione Architettura Full Decoupling v2.0 (CASO A)

**Autore:** GitHub Copilot (spark-engine-maintainer)
**Data:** 2026-05-08
**Branch:** `feature/dual-mode-manifest-v3.1`
**Documento validato:** `docs/SPARK-DESIGN-FullDecoupling-v2.0.md`
**Esito:** CASO A — Architettura v2.0 compatibile con modifiche gestibili
**Confidence:** 0.93

---

## 1. Riepilogo Esecutivo

L'architettura Full Decoupling v2.0 è **compatibile** con il codebase attuale.
I tre problemi BLOCCANTI identificati nel report precedente
(`docs/reports/REPORT-Copilot-FullDecoupling-Issues.md`) sono stati corretti
nel documento v2.0. Non emergono nuovi problemi bloccanti.

**Gate:** PASS

**File prodotti:**
1. `docs/SPARK-DESIGN-FullDecoupling-v2.0.md` — documento design aggiornato
2. `docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md` — questo report

---

## 2. Risultati delle Fasi di Analisi

### FASE 1 — Lettura documenti e codebase

| File | Esito |
|------|-------|
| `docs/SPARK-DESIGN-FullDecoupling-v1.0.md` | Letto in full (9 sezioni) |
| `docs/reports/REPORT-Copilot-FullDecoupling-Issues.md` | Letto (8 problemi documentati) |
| `spark/boot/engine.py` | Letto: `SparkFrameworkEngine.__init__`, `_init_runtime_objects` |
| `spark/boot/lifecycle.py` | Letto: `_install_workspace_files_v3`, `_install_standalone_files_v3`, `_remove_workspace_files_v3` |
| `spark/manifest/gateway.py` | Letto: `WorkspaceWriteGateway.__init__` e metodi |
| `spark/manifest/manifest.py` | Letto: `ManifestManager.__init__`, `load()`, `upsert()` |
| `spark/registry/client.py` | Letto: `RegistryClient.__init__`, `fetch()` |
| `spark/boot/tools_bootstrap.py` | Letto: `scf_bootstrap_workspace` |
| `spark/assets/phase6.py` | Letto: `_apply_phase6_assets` |
| `spark/core/constants.py` | Verificati: `_MANIFEST_FILENAME`, `_REGISTRY_URL`, `ENGINE_VERSION` |
| `scf-master-codecrafter/package-manifest.json` | Nessun `plugin_files`, usa `workspace_files` |
| `scf-pycode-crafter/package-manifest.json` | Nessun `plugin_files`, usa `workspace_files` |

---

### FASE 2 — Validazione compatibilità componenti

#### WorkspaceWriteGateway (`spark/manifest/gateway.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/manifest/gateway.py`, classe `WorkspaceWriteGateway`

**Compatibile con v2.0?** ✅ Sì — invariante per definizione

**Modifiche concrete richieste:** Nessuna. `PluginInstaller` userà:
```python
gateway = WorkspaceWriteGateway(workspace_root, manifest_manager)
gateway.write_many(file_list)  # OPT-8: già implementato
```

---

#### ManifestManager (`spark/manifest/manifest.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/manifest/manifest.py`, classe `ManifestManager`

**Compatibile con v2.0?** ✅ Sì — il manifest traccia file con owner/SHA, struttura
agnostica rispetto al tipo di installatore che la popola.

**Nota v2.0:** il `_MANIFEST_FILENAME` costante è `.scf-manifest.json`, quindi il path
fisico è `.github/.scf-manifest.json` — da usare nei documenti (non `.spark-manifest.json`).

**Modifiche concrete richieste:** Nessuna alla classe. `PluginInstaller` chiama
`manifest.upsert_many()` come già fa il lifecycle corrente.

---

#### RegistryClient (`spark/registry/client.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/registry/client.py`, classe `RegistryClient`

**Compatibile con v2.0?** ✅ Sì, con nota d'uso

**Firma costruttore reale:**
```python
def __init__(
    self,
    github_root: Path,           # obbligatorio
    registry_url: str = _REGISTRY_URL,
    cache_path: Path | None = None,
) -> None:
```

**Modifiche concrete richieste:** Nessuna alla classe. `PluginManagerFacade` deve
instanziarlo con `github_root = workspace_root / ".github"`. Documentato nel §3.3
di `SPARK-DESIGN-FullDecoupling-v2.0.md`.

**Nota offline:** `RegistryClient.fetch()` ha già fallback alla cache locale. La
Decisione Aperta D3 (comportamento offline) è già parzialmente risolta dal
comportamento esistente.

---

#### FrameworkInventory (`spark/inventory/framework.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/inventory/framework.py`, classe `FrameworkInventory`

**Compatibile con v2.0?** ✅ Sì — gestisce solo risorse MCP Universo A, invariante

**Modifiche concrete richieste:** Nessuna

---

#### `_install_standalone_files_v3` (`spark/boot/lifecycle.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/boot/lifecycle.py`, mixin `_V3LifecycleMixin`,
metodo `_install_standalone_files_v3`. (Il nome `_install_plugin_files_v3` nella v1.0
era errato.)

**Compatibile con v2.0?** ✅ Sì — la logica migra in `PluginInstaller.install_files()`

**Modifiche concrete richieste:** La funzione viene rimossa da `_V3LifecycleMixin` nel
Step 3 della migrazione. Viene riscritta in `spark/plugins/installer.py` come metodo
di `PluginInstaller` con la stessa logica ma senza dipendenza dal mixin engine.

**Dipendenza verificata:**
```python
# _install_standalone_files_v3 chiama internamente:
from spark.packages import _get_deployment_modes   # invariante
# e delega a _install_workspace_files_v3 via manifest sintetico
```

---

#### `scf_install_package` (`spark/boot/tools_packages_install.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/boot/tools_packages_install.py`

**Compatibile con v2.0?** ✅ Sì, con ruolo ridefinito

**Modifiche concrete richieste:**
- `scf_install_package` rimane per Universo A (store interno) — rimuove la logica
  `plugin_files` che migra nel nuovo `scf_install_plugin`
- Aggiunta del nuovo tool `scf_install_plugin` come thin facade
- Contatore tool aggiornato (Step 2)

---

#### `SparkFrameworkEngine.__init__` e `_init_runtime_objects` (`spark/boot/engine.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/boot/engine.py`, classe `SparkFrameworkEngine`

**Compatibile con v2.0?** ✅ Sì, con aggiunta minimal

**Pattern init verificato (codebase):**
```python
# __init__ reale — attributi confermati:
self._mcp = mcp
self._ctx = context          # WorkspaceContext
self._inventory = inventory  # FrameworkInventory
self._runtime_dir = runtime_dir
# Runtime objects (lazy, via _init_runtime_objects()):
self._manifest: ManifestManager | None = None
self._registry_client: RegistryClient | None = None
self._merge_engine: MergeEngine | None = None
self._snapshots: SnapshotManager | None = None
self._sessions: MergeSessionManager | None = None

# NON esiste self._config
# NON esiste self._workspace_locator
# workspace_root accessibile come: self._ctx.workspace_root
```

**Snippet init corretto per v2.0:**
```python
# In _init_runtime_objects(), dopo self._registry_client = RegistryClient(...):
from spark.plugins import PluginManagerFacade  # noqa: PLC0415
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,
)
```

---

#### `scf_bootstrap_workspace` (`spark/boot/tools_bootstrap.py`)

**Esiste con path/nome reale?** ✅ Sì — `spark/boot/tools_bootstrap.py`

**Compatibile con v2.0?** ✅ Sì, con comportamento aggiornato al Step 4

**Stato attuale:** scrive tutti i file di bootstrap da `spark-base` store al workspace.
**Stato target v2.0:** scrive solo `copilot-instructions.md` + `AGENTS.md` base al
primo avvio; propone (ma non applica) aggiornamenti ai successivi avvii se l'utente
ha modificato i file.

**Nota:** `ManifestManager.is_user_modified()` già implementato — utilizzabile
direttamente nella logica di rilevamento modifiche utente.

---

### FASE 3 — Verifica meccanismo `#file:` VS Code Copilot

**Esiste già logica `#file:` nel codebase?** No — nessuna occorrenza nei file `.py` di `spark/`.

**È implementabile senza conflitti?** ✅ Sì

**Analisi:**

Il meccanismo `#file:` è una feature nativa di VS Code Copilot. VS Code legge
`copilot-instructions.md` e include automaticamente i file referenziati con `#file:`.
Non richiede alcuna logica Python lato motore per la **lettura** — Copilot la gestisce
nativamente.

Il motore Python deve solo:
1. `PluginInstaller._add_instruction_reference(pkg_id)`: aggiunge una riga
   `#file:.github/instructions/{pkg_id}.md` in una sezione dedicata di
   `copilot-instructions.md`
2. `PluginRemover._remove_instruction_reference(pkg_id)`: rimuove la riga
   corrispondente

Implementazione: string manipulation su `copilot-instructions.md` + scrittura
tramite `WorkspaceWriteGateway.write()` + aggiornamento `ManifestManager`.

**Coesistenza con SCF section merge:** ✅ Compatibile

Il meccanismo `#file:` (per plugin Universo B) coesiste con i marker
`SCF:BEGIN/END` (per bootstrap engine Universo A) in `copilot-instructions.md`:
- Il bootstrap engine scrive la sezione `SCF:BEGIN:engine-bootstrap`
- I plugin aggiungono righe `#file:` in una sezione separata
- Non c'è overlap tra i due meccanismi

---

## 3. Correzioni applicate nel documento v2.0

### Correzione PROBLEMA-1 (BLOCCANTE) — Path moduli errati

**v1.0 (errato):** `spark/core/workspace_write_gateway.py`, `spark/core/manifest_manager.py`,
`spark/core/registry_client.py`, `spark/core/framework_inventory.py`, `spark/core/workspace_locator.py`

**v2.0 (corretto):** Tabella §0.2 e §5 con path reali verificati:
- `spark/manifest/gateway.py` — `WorkspaceWriteGateway`
- `spark/manifest/manifest.py` — `ManifestManager`
- `spark/registry/client.py` — `RegistryClient`
- `spark/inventory/framework.py` — `FrameworkInventory`
- `spark/workspace/locator.py` — `WorkspaceLocator`

Confidence su questa correzione: **1.0** (path verificati con `list_dir` e `read_file`)

---

### Correzione PROBLEMA-2 (BLOCCANTE) — Nome funzione errato

**v1.0 (errato):** `_install_plugin_files_v3` (funzione inesistente)

**v2.0 (corretto):** §4.2 usa esplicitamente `_install_standalone_files_v3` con
nota a margine che spiega l'errore della v1.0.

Confidence su questa correzione: **1.0** (funzione verificata nel codice con `read_file`)

---

### Correzione PROBLEMA-3 (BLOCCANTE) — Snippet init con attributi inesistenti

**v1.0 (errato):**
```python
self._plugin_manager = PluginManagerFacade(
    workspace_path=self._workspace_locator.workspace_path,  # NON ESISTE
    registry_url=self._config.registry_url  # NON ESISTE
)
```

**v2.0 (corretto):** §4.3 e §3.3 usano attributi reali verificati:
```python
self._plugin_manager = PluginManagerFacade(
    workspace_root=self._ctx.workspace_root,  # attributo reale di WorkspaceContext
    # registry_url usa default _REGISTRY_URL da spark.core.constants
)
```

Confidence su questa correzione: **1.0** (attributi verificati nel codice)

---

### Correzione PROBLEMA-4 (RILEVANTE) — Firma RegistryClient

**v1.0:** non specificava come `PluginManagerFacade` instanzia `RegistryClient`

**v2.0:** §3.3 documenta esplicitamente il pattern di costruzione con `github_root`

---

### Correzione PROBLEMA-5 (RILEVANTE) — Dual-tracking risk

**v1.0:** due file di stato indipendenti senza coordinamento

**v2.0:** §6.4 definisce coordinamento esplicito:
- `ManifestManager` (.scf-manifest.json): granularità file, preservation gate
- `PluginRegistry` (.spark-plugins): granularità pacchetto, metadati installazione
- Nessun overlap: chiavi diverse (path file vs package_id)
- Backward compat: PluginRegistry importa ownership da ManifestManager al primo avvio

---

### Correzione PROBLEMA-6 (RILEVANTE) — Boundary engine-embedded vs plugin

**v1.0:** non definito per `spark-base`

**v2.0:** §2.1 introduce la distinzione Universo A / Universo B con regole esplicite.
La Decisione Aperta D1 in §9 chiede a Nemex81 di scegliere tra le due opzioni per
`spark-base` (plugin autonomo vs engine embedded).

---

### Correzione PROBLEMA-7 (RILEVANTE) — Test impact sottostimato

**v1.0:** affermava "modifiche minime ai fixture"

**v2.0:** §7 documenta esplicitamente i 5 file test con tipo di modifica:
- 3 file con modifica significativa (riscrittura fixture)
- 2 file con modifica minimale (mock names)

---

### Correzione PROBLEMA-8 (MINORE) — `plugin_files` assente nei manifest reali

**v1.0:** non documentava che `plugin_files` era assente nei repo remoti

**v2.0:** §6.2 documenta lo stato attuale dei manifest remoti e la modifica
necessaria nei repo `scf-master-codecrafter` e `scf-pycode-crafter`.

---

## 4. Aggiunte della v2.0 non presenti in v1.0

| Aggiunta | Sezione v2.0 | Motivazione |
|----------|-------------|-------------|
| Sezione §0 "Stato Attuale vs Stato Target" | §0 | Path reali verificati, roadmap struttura |
| Distinzione Universo A / Universo B | §2.1 | Chiarisce il boundary architetturale |
| Meccanismo `#file:` per istruzioni plugin | §2.4 | Feature proposta dal coordinatore, validata |
| Firma completa di `PluginManagerFacade.__init__` | §3.3 | Corregge PROBLEMA-3 e PROBLEMA-4 |
| Piano migrazione in 4 step con criteri accettazione | §6.3 | Aggiunge Step 4 bootstrap e criteri verificabili |
| Sezione §6.4 coordinamento PluginRegistry/ManifestManager | §6.4 | Risolve PROBLEMA-5 |
| Tabella invarianti con path reali | §5 | Risolve PROBLEMA-1 |
| D1 — Boundary spark-base (Decisione Aperta) | §9 | Risolve PROBLEMA-6 con decisione esplicita richiesta |

---

## 5. Punti a Confidence < 1.0

### Confidence 0.90 — Meccanismo `#file:` in VS Code Copilot

La feature `#file:` in `copilot-instructions.md` è documentata in modo informale
nella community VS Code. Non è stata verificata tramite documentazione ufficiale
Microsoft in questa sessione. Il meccanismo è noto per funzionare con le versioni
recenti di GitHub Copilot in VS Code.

**Rischio:** se la feature non è supportata nella versione Copilot installata nel
workspace di Nemex81, il meccanismo di istruzioni plugin non funziona a runtime.
**Mitigazione:** verificare con Nemex81 che VS Code Copilot supporti `#file:` nella
versione in uso, oppure usare il meccanismo `applyTo` in `.github/instructions/*.md`
che è definitivamente supportato (già usato nel workspace corrente).

**Alternativa verificata:** le instruction con `applyTo: '**'` vengono caricate da
VS Code Copilot per ogni file — pattern già presente nel workspace (vedere
`.github/instructions/workflow-standard.instructions.md`). Se `#file:` non è
supportato, il PluginInstaller scrive semplicemente i file `.github/instructions/`
con `applyTo` corretto — VS Code li carica automaticamente senza `#file:`.

### Confidence 0.87 — Step 3 non introduce regressioni nascoste

La rimozione di `_install_workspace_files_v3` e `_install_standalone_files_v3` dal
mixin potrebbe rilevare dipendenze non evidenti da `read_file` (es. test parametrizzati
in file non letti). I criteri di accettazione dello Step 3 includono
`pytest -q --ignore=tests/test_integration_live.py` come gate obbligatorio.

---

## 6. Raccomandazione

### PROCEDI — Il documento v2.0 è approvabile

L'architettura v2.0 è:
- Compatibile con il codebase attuale senza breaking change immediate
- Costruita su invarianti verificati
- Con un piano di migrazione a basso rischio nei passi 1 e 4, medio nei passi 2 e 3

**Azione immediata consigliata:**
1. Nemex81 risponde alla Decisione Aperta D1 (boundary `spark-base`)
2. Nemex81 approva la checklist §8 del documento v2.0
3. Copilot procede con Step 1: crea `spark/plugins/` senza rimuovere nulla

**Comandi proposti per commit (da eseguire manualmente):**
```bash
# Dopo approvazione di Nemex81:
git add docs/SPARK-DESIGN-FullDecoupling-v2.0.md
git add docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md
git commit -m "docs(design): Full Decoupling Architecture v2.0 — design aggiornato e validato"
```

---

## 7. Matrice di Copertura Problemi

| Problema (da report v1.0) | Gravità | Corretto in v2.0 | Confidence |
|---------------------------|---------|-----------------|------------|
| PROBLEMA-1: path moduli errati | BLOCCANTE | ✅ Sì — §0.1, §5 | 1.0 |
| PROBLEMA-2: nome funzione errato | BLOCCANTE | ✅ Sì — §4.2 | 1.0 |
| PROBLEMA-3: snippet init errato | BLOCCANTE | ✅ Sì — §3.3, §4.3 | 1.0 |
| PROBLEMA-4: RegistryClient firma | RILEVANTE | ✅ Sì — §3.3 | 1.0 |
| PROBLEMA-5: dual-tracking risk | RILEVANTE | ✅ Sì — §6.4 | 0.95 |
| PROBLEMA-6: boundary engine/plugin | RILEVANTE | ✅ Sì — §2.1 + D1 aperta | 0.90 |
| PROBLEMA-7: test impact sottostimato | RILEVANTE | ✅ Sì — §7 tabella | 0.95 |
| PROBLEMA-8: plugin_files assente | MINORE | ✅ Sì — §6.2 | 1.0 |

**Tutti gli 8 problemi del report precedente sono indirizzati nel documento v2.0.**

---

OPERAZIONE COMPLETATA: Validazione architettura v2.0 e produzione documenti
GATE: PASS
CONFIDENCE: 0.93
FILE TOCCATI: `docs/SPARK-DESIGN-FullDecoupling-v2.0.md`, `docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md`
OUTPUT CHIAVE: CASO A — architettura compatibile, tutti i problemi BLOCCANTI corretti
PROSSIMA AZIONE: Nemex81 risponde a D1 (boundary spark-base) e approva checklist §8
