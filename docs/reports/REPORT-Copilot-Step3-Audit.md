# REPORT — Audit Stato Attuale Step 3: Separazione Netta Universo A/B

**Autore:** GitHub Copilot (spark-engine-maintainer)
**Data:** 2026-05-08
**Branch:** `feature/dual-mode-manifest-v3.1`
**Task:** Step 3 — TASK-1 (sola lettura, nessuna modifica)
**Gate:** PASS — audit completato, interventi identificati

---

## 1. Riepilogo Esecutivo

L'audit ha letto 10 file sorgente e 3 report preesistenti.
L'architettura è parzialmente allineata al design v2.0: il modulo `spark/plugins/`
è già implementato (Step 1), i tool MCP plugin sono registrati (Step 2), ma rimangono
**4 interventi strutturali** da eseguire prima che la separazione A/B sia completa.

**File letti:**
- `docs/reports/archiviati/REPORT-Copilot-FullDecoupling-Issues.md`
- `docs/reports/archiviati/REPORT-Copilot-FullDecoupling-v2.0-Validation.md`
- `spark/boot/lifecycle.py` (linee 1–465)
- `spark/boot/engine.py` (linee 260–310)
- `spark/boot/tools_packages_install.py` (linee 395–500)
- `spark/plugins/facade.py` (linee 1–100)
- `spark/plugins/installer.py` (linee 1–140)
- `spark/plugins/registry.py` (linee 1–110)

---

## 2. Risultati per voce di verifica

### Voce 1 — Funzioni di scrittura workspace ancora in `lifecycle.py`

| Funzione | Linea | Stato |
|---|---|---|
| `_install_workspace_files_v3` | 136 | **PRESENTE E ATTIVA** — logica completa, non stub |
| `_install_standalone_files_v3` | 306 | **PRESENTE E ATTIVA** — delega a `_install_workspace_files_v3` |
| `_remove_workspace_files_v3` | 405 | **PRESENTE E ATTIVA** — logica completa, non stub |

Tutte e tre le funzioni contengono logica operativa piena. Non esistono stub. Queste
funzioni scrivono (o rimuovono) file fisici nel workspace utente.

**Nota architettonica importante:** `_install_workspace_files_v3` legge il contenuto
dei file dall'**engine store locale** (`PackageResourceStore`, path `engine_root/packages/{pkg_id}/{file}`).
Questa è una logica fondamentalmente diversa da `PluginInstaller.install_files()`, che
scarica i file via **HTTP dal repository GitHub** del plugin. La "migrazione" richiede
l'aggiunta di un metodo complementare in `PluginInstaller` che gestisca il path
copy-from-store, non una semplice trasposizione 1:1.

---

### Voce 2 — `PluginManagerFacade` in `engine.py._init_runtime_objects()`

`_init_runtime_objects()` (linea 280) inizializza:
```python
self._manifest = ManifestManager(self._ctx.github_root)       # ✅ presente
self._registry_client = RegistryClient(self._ctx.github_root)  # ✅ presente
self._merge_engine = MergeEngine()                             # ✅ presente
self._snapshots = SnapshotManager(...)                         # ✅ presente
self._sessions = MergeSessionManager(...)                      # ✅ presente
```

`self._plugin_manager: PluginManagerFacade` → **ASSENTE**.
**Intervento TASK-3 necessario.**

Attributi verificati per lo snippet init approvato:
- `self._ctx.workspace_root` → ✅ esiste (`WorkspaceContext.workspace_root`)
- `_REGISTRY_URL` da `spark.core.constants` → ✅ esistente e già in uso nel file
- `PluginManagerFacade(workspace_root=..., registry_url=...)` → ✅ firma compatibile

---

### Voce 3 — Stato di `spark/plugins/installer.py`

`PluginInstaller.install_files()` (linea 70) è già implementato e funzionante.

**Meccanismo:** scarica i file da GitHub via `urllib.request.urlopen`, costruisce
la URL raw da `source_repo` + path dichiarato in `plugin_manifest.plugin_files`.

**Differenza critica rispetto a `_install_workspace_files_v3`:**

| Aspetto | `_install_workspace_files_v3` | `PluginInstaller.install_files()` |
|---|---|---|
| Sorgente dati | Engine store locale (`packages/{pkg}/{file}`) | HTTP GitHub raw |
| Preservation gate | Usa `ManifestManager.load()` + `is_user_modified()` | Non implementato |
| Batch write | `manifest.upsert_many()` con OPT-4 | `WorkspaceWriteGateway.write()` per file |
| SHA idempotenza | Sì (OPT-5, salta scrittura se SHA identico) | No |
| File policies | Supporta `merge_strategy` per file | Non supportato |

**Conclusione:** `PluginInstaller.install_files()` gestisce i `plugin_files` scaricati
da GitHub. Il path lifecycle (`_install_workspace_files_v3`) gestisce i `workspace_files`
letti dallo store locale. Sono due meccanismi complementari, NON duplicati.

Per la migrazione TASK-2 serve aggiungere in `PluginInstaller` un metodo
`install_from_store()` equivalente a `_install_workspace_files_v3`, con:
- lettura da `PackageResourceStore`
- preservation gate via `ManifestManager.is_user_modified()`
- batch write via `manifest.upsert_many()`

---

### Voce 4 — `spark/plugins/registry.py` vs `ManifestManager`

`PluginRegistry` (linea 1–80) scrive il file **`.github/.spark-plugins`** separato.

```python
_PLUGINS_FILENAME: str = ".spark-plugins"
# ...
self._path = github_root / _PLUGINS_FILENAME
```

I metodi `register()` e `unregister()` leggono/scrivono JSON direttamente su questo file.

**Stato:** PROBLEMA-5 del report Issues **NON risolto**.
Il dual-tracking state risk è ancora presente:
- `ManifestManager` traccia ownership/SHA per file in `.scf-manifest.json`
- `PluginRegistry` traccia pacchetti in `.spark-plugins`
- Non c'è coordinamento tra i due

**Intervento TASK-4 necessario:** refactoring `PluginRegistry` per eliminare `.spark-plugins`
e delegare a `ManifestManager.upsert()` con campi extra:
```json
{
  "installation_mode": "plugin_manager",
  "source_repo": "Nemex81/scf-master-codecrafter",
  "installed_at": "2026-05-08T09:00:00Z"
}
```

---

### Voce 5 — `scf_install_package` in `tools_packages_install.py`

Alla linea ~441, `scf_install_package` chiama direttamente:
```python
standalone_result = engine._install_standalone_files_v3(
    package_id=package_id,
    pkg_version=pkg_version,
    pkg_manifest=pkg_manifest,
    manifest=manifest_for_standalone,
)
```

`PluginManagerFacade` **non è coinvolto** in questa chiamata.

**Stato:** il tool `scf_install_package` chiama ancora metodi del mixin `_V3LifecycleMixin`,
coerentemente con il design (backward compatibility). Dopo TASK-2 questi metodi diventano
stub che delegano a `PluginInstaller`, quindi la chiamata da `tools_packages_install.py`
continuerà a funzionare anche senza modifiche dirette al file.

---

## 3. Mappa interventi richiesti

| # | Task | File da modificare | Tipo intervento |
|---|------|-------------------|-----------------|
| T2.1 | TASK-2 | `spark/plugins/installer.py` | Aggiungere `install_from_store()` che replica logica di `_install_workspace_files_v3` |
| T2.2 | TASK-2 | `spark/boot/lifecycle.py` | Trasformare `_install_workspace_files_v3`, `_install_standalone_files_v3`, `_remove_workspace_files_v3` in stub deprecati che delegano ai nuovi metodi |
| T2.3 | TASK-2 | `spark/plugins/remover.py` | Verificare/aggiungere `remove_workspace_files()` equivalente a `_remove_workspace_files_v3` |
| T3 | TASK-3 | `spark/boot/engine.py` | Aggiungere `self._plugin_manager = PluginManagerFacade(...)` in `_init_runtime_objects()` |
| T4 | TASK-4 | `spark/plugins/registry.py` | Eliminare `.spark-plugins`, delegare a `ManifestManager` |
| T4b | TASK-4 | `spark/plugins/facade.py` | Aggiornare `install()`/`remove()` per passare `ManifestManager` a `PluginRegistry` |

---

## 4. Elementi già allineati (nessuna modifica necessaria)

| Componente | Stato |
|---|---|
| `spark/plugins/facade.py` | ✅ Implementato — API pubblica completa |
| `spark/plugins/installer.py` | ✅ Parzialmente allineato — `install_files()` per HTTP già funzionante |
| `spark/boot/tools_plugins.py` | ✅ 4 tool MCP registrati (Step 2) |
| `spark/manifest/gateway.py` | ✅ Invariante — nessuna modifica prevista |
| `spark/manifest/manifest.py` | ✅ Invariante — `upsert_many()`, `is_user_modified()` già presenti |
| `spark/registry/client.py` | ✅ Invariante — `RegistryClient(github_root=...)` compatibile |
| `scf-master-codecrafter/package-manifest.json` | ✅ `plugin_files` aggiunto (Step 2) |
| `scf-pycode-crafter/package-manifest.json` | ✅ `plugin_files` aggiunto (Step 2) |
| Baseline test | ✅ 446 passed, 9 skipped (post-Step 2) |

---

## 5. Anomalie rilevate

### ANOMALIA-1 — Divergenza meccanismi di scrittura installer vs lifecycle

**Descrizione:** `PluginInstaller.install_files()` scarica da GitHub HTTP.
`_install_workspace_files_v3` copia dallo store locale. Il prompt Step 3 TASK-2
tratta la migrazione come trasposizione 1:1, ma i due meccanismi operano su sorgenti
diverse. La migrazione corretta richiede l'aggiunta di un secondo metodo in
`PluginInstaller` (copy-from-store), non la sostituzione di quello esistente.

**Impatto:** TASK-2 deve essere eseguito con più attenzione di quanto descritto
nel prompt; il metodo da aggiungere è complementare, non sostitutivo.
**Classificazione:** non bloccante — gestibile inline durante TASK-2.

### ANOMALIA-2 — `PluginInstaller.install_files()` usa `print()` su stderr

**Descrizione:** alle linee 93–96 e 115–117, `installer.py` usa `print(..., file=sys.stderr)`
invece di `logging.getLogger("spark-framework-engine")`.

**Impatto:** violazione della regola operativa (logging esclusivamente via `logging`).
**Classificazione:** non bloccante per Step 3 — da correggere insieme alla migrazione TASK-2.

---

## 6. Decisioni aperte

**D1 — `scf_install_package` e il path `workspace_files` post-Step 3**

Il prompt Step 3 dice: "`scf_install_package` (path v2 legacy) rimane invariato per
compatibilità ma NON scrive più file Cat. A/B nel workspace". Tuttavia dopo che i metodi
`lifecycle.py` diventano stub che delegano a `PluginInstaller.install_from_store()`,
il comportamento esterno di `scf_install_package` rimane identico (scrive ancora i file).

**Domanda a Nemex81:** `scf_install_package` deve continuare a scrivere `workspace_files`
dopo Step 3 (solo il meccanismo interno cambia) oppure deve smettere completamente
di scrivere nel workspace (spezzando il comportamento legacy)?

**D2 — `spark-base` come plugin: timing della migrazione**

Il prompt Step 3 dice "spark-base è un plugin gestito da `scf_install_plugin`". Tuttavia
`spark-base` usa `workspace_files` (non `plugin_files`) nel suo manifest attuale. La
migrazione del flusso di bootstrap per `spark-base` è nello scope di Step 3 o va rimandata?

---

## 7. Piano di esecuzione Step 3 (aggiornato post-audit)

Sequenza confermata, con modifiche alla granularità di TASK-2:

1. **TASK-2a:** Aggiungere `PluginInstaller.install_from_store()` — copia da store locale
2. **TASK-2b:** Aggiungere `PluginRemover.remove_workspace_files()` — verifica stato attuale di `spark/plugins/remover.py`
3. **TASK-2c:** Trasformare i tre metodi `lifecycle.py` in stub con delega
4. **TASK-3:** `_init_runtime_objects()` in `engine.py`
5. **TASK-4:** Refactoring `PluginRegistry` → `ManifestManager`
6. **TASK-5:** Suite test verde
7. **TASK-6:** Report finale + PR

**OPERAZIONE COMPLETATA:** TASK-1 Audit stato attuale
**GATE:** PASS
**CONFIDENCE:** 0.92
**FILE TOCCATI:** 1 creato (`docs/reports/REPORT-Copilot-Step3-Audit.md`), 0 modificati
**OUTPUT CHIAVE:** 4 interventi strutturali identificati (lifecycle stubs, engine init, registry refactor, installer extension)
**PROSSIMA AZIONE:** TASK-2 — Migrazione logica scrittura
