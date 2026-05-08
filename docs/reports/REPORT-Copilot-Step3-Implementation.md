# REPORT — Step 3: Separazione Netta Universo A/B

**Data**: 2025-07-15
**Agente**: spark-engine-maintainer
**Versione engine**: vedi `ENGINE_VERSION` in `spark-framework-engine.py`
**Branch**: `feature/dual-mode-manifest-v3.1`
**Suite validation**: 446 passed, 9 skipped, 0 failed

---

## Sommario esecutivo

Lo Step 3 "Separazione Netta Universo A/B" ha completato la migrazione della logica
di scrittura/rimozione workspace dai metodi `lifecycle.py` (mixin engine) verso i
componenti dedicati `spark/plugins/installer.py` e `spark/plugins/remover.py`.

Il `PluginRegistry` è stato aggiornato per supportare un backend manifest-based
(preferito) che elimina la dipendenza dal file separato `.spark-plugins`.

Il `SparkFrameworkEngine._init_runtime_objects()` ora istanzia `PluginManagerFacade`
al boot, rendendo il Plugin Manager disponibile come attributo dell'engine.

---

## Task completati

### TASK-1 ✅ — Audit stato attuale
- Report: `docs/reports/REPORT-Copilot-Step3-Audit.md`
- Identificate 3 funzioni lifecycle attive, 4 punti di non-allineamento
- Identificata divergenza critica: lifecycle usa store locale, installer usa HTTP

### TASK-2 ✅ — Migrazione logica scrittura da lifecycle a spark/plugins/

#### 2a. `PluginInstaller.install_from_store()` aggiunto in `spark/plugins/installer.py`
- Firma: `install_from_store(package_id, pkg_version, pkg_manifest, engine_root) -> dict`
- Replica completa della logica di `_install_workspace_files_v3`:
  - Legge file da `PackageResourceStore` (engine store locale)
  - Preservation gate: skip se altri owner hanno modificato il file
  - Idempotenza SHA (OPT-5): skip se contenuto invariato e file presente
  - Batch write via `gateway.write_many()` (OPT-8)
  - Path traversal guard su ogni entry
- Nuovi import: `collections.abc.Mapping`, `spark.core.utils._sha256_text`,
  `spark.registry.store.PackageResourceStore` (lazy in-method)
- Return: `{"success": bool, "files_written": [...], "preserved": [...], "errors": []}`

#### 2b. `PluginRemover.remove_workspace_files()` aggiunto in `spark/plugins/remover.py`
- Firma: `remove_workspace_files(package_id, pkg_manifest) -> dict`
- Replica completa della logica di `_remove_workspace_files_v3`:
  - Combina `workspace_files` + `plugin_files` dal manifest (deduplicati)
  - Preservation gate: skip se owned da altri, se non tracciato, se user-modified
  - Delete via `gateway.delete()`
- Nuovo helper module-level: `_dedupe_preserving_order(items) -> list`
- Nuovo import: `collections.abc.Mapping`, `typing.Any`
- Return: `{"removed": [...], "preserved": [...], "errors": []}`

#### 2c. Stubs in `spark/boot/lifecycle.py`
- `_install_workspace_files_v3()` → stub deprecato che delega a `PluginInstaller.install_from_store()`
- `_remove_workspace_files_v3()` → stub deprecato che delega a `PluginRemover.remove_workspace_files()`
- `_install_standalone_files_v3()` → invariato (delega già a `_install_workspace_files_v3` tramite catena)
- Commento `# DEPRECATED:` in ogni stub per il cleanup finale
- Import lazy (`from spark.plugins.installer import PluginInstaller`) per evitare import circolari

### TASK-3 ✅ — PluginManagerFacade in engine._init_runtime_objects()
- File: `spark/boot/engine.py`
- Aggiunto `self._plugin_manager: Any | None = None` in `__init__`
- Aggiunto in `_init_runtime_objects()` (dopo `sessions.cleanup_expired_sessions()`):
  ```python
  from spark.plugins.facade import PluginManagerFacade  # noqa: PLC0415
  self._plugin_manager = PluginManagerFacade(
      workspace_root=self._ctx.workspace_root,
      registry_url=_REGISTRY_URL,
  )
  ```
- Import lazy per rispettare la policy di inizializzazione runtime

### TASK-4 ✅ — PluginRegistry refactoring verso ManifestManager
- File: `spark/plugins/registry.py` — riscrittura completa
- Nuova costante: `_PLUGIN_MANAGER_INSTALLATION_MODE = "plugin_manager"`
- Nuova funzione: `_plugin_sentinel_file(pkg_id) -> str` → `"__plugins__/{pkg_id}"`
  (pattern analogo a `_v3_store_sentinel_file` in `spark/registry/v3_store.py`)
- `PluginRegistry.__init__` ora accetta `manifest_manager: ManifestManager | None = None`
- Due backend:
  - **manifest-based** (preferito, attivato da `manifest_manager`): entry sentinella
    con `installation_mode: "plugin_manager"`, `source_repo`, `files`, `file_hashes`
  - **file-based** (legacy/fallback): `_load_from_file()`, `_register_in_file()`,
    `_unregister_from_file()`, `_save_file()` (logica precedente)
- `PluginManagerFacade.__init__` aggiornato: `PluginRegistry(github_root, manifest_manager=self._manifest)`

### TASK-5 ✅ — Validazione test suite
- Comando: `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py`
- Risultato: **446 passed, 9 skipped, 0 failed** (baseline: 446 passed pre-Step 3)
- Nessun test modificato (stubs retrocompatibili, nessuna regressione)

---

## File modificati

| File | Tipo modifica |
|------|--------------|
| `spark/plugins/installer.py` | Nuovi import + `install_from_store()` |
| `spark/plugins/remover.py` | Nuovi import + `_dedupe_preserving_order()` + `remove_workspace_files()` |
| `spark/plugins/registry.py` | Riscrittura: dual-backend manifest/file |
| `spark/plugins/facade.py` | 1 riga: passa `manifest_manager=self._manifest` a `PluginRegistry` |
| `spark/boot/lifecycle.py` | `_install_workspace_files_v3` e `_remove_workspace_files_v3` → stubs |
| `spark/boot/engine.py` | `_plugin_manager` attr + `PluginManagerFacade` in `_init_runtime_objects` |

---

## File NON modificati (invarianti)

Per policy Step 3:
- `spark/manifest/gateway.py` ✅
- `spark/manifest/manifest.py` ✅
- `spark/registry/client.py` ✅
- `spark/workspace/locator.py` ✅
- `spark/inventory/framework.py` ✅

---

## Problemi aperti (da decidere con Nemex81)

### D1 — `scf_install_package` e workspace_files
`scf_install_package` continua a scrivere `workspace_files` nel workspace tramite
`_install_workspace_files_v3` (ora stub → `PluginInstaller.install_from_store()`).
Domanda: in uno scenario futuro, il percorso `scf_install_package` deve smettere
completamente di scrivere `workspace_files` in favore del Plugin Manager?
→ **Decisione richiesta** prima di eventuali cleanup finali.

### D2 — `spark-base` come plugin
`spark-base` dichiara `workspace_files` ma non `plugin_files`.
La sua migrazione da Universo A a Universo B rientra nello scope di Step 3?
→ **Decisione richiesta** prima di qualsiasi modifica al suo manifest.

---

## Debito tecnico residuo (cleanup finale)

1. **Stubs lifecycle.py**: rimuovere `_install_workspace_files_v3`,
   `_install_standalone_files_v3`, `_remove_workspace_files_v3` dopo che i
   chiamanti diretti sono stati aggiornati nei test.
2. **ANOMALIA-2**: sostituire `print(..., file=sys.stderr)` in `installer.py`
   e `remover.py` con `logging.getLogger("spark-framework-engine")`.
3. **Migrazione `.spark-plugins`**: definire quando il backend file-based di
   `PluginRegistry` viene rimosso (dopo che i workspace live sono stati migrati).
4. **Test diretti**: `test_standalone_files_v3.py` e `test_install_workspace_files.py`
   possono essere aggiornati per testare `PluginInstaller.install_from_store()`
   e `PluginRemover.remove_workspace_files()` direttamente (senza passare per lifecycle).

---

## Comandi proposti per commit

```bash
# Comandi da eseguire manualmente:
git add spark/plugins/installer.py spark/plugins/remover.py spark/plugins/registry.py
git add spark/plugins/facade.py spark/boot/lifecycle.py spark/boot/engine.py
git add docs/reports/REPORT-Copilot-Step3-Implementation.md
git commit -m "feat(plugins): Step 3 — separazione netta Universo A/B

- PluginInstaller.install_from_store(): copia workspace_files da engine store
- PluginRemover.remove_workspace_files(): rimuove workspace_files+plugin_files
- lifecycle._install_workspace_files_v3 e _remove_workspace_files_v3 -> stubs
- PluginRegistry: dual-backend manifest-based (preferito) + file-based (legacy)
- PluginManagerFacade passa manifest_manager a PluginRegistry
- engine._init_runtime_objects() ora istanzia PluginManagerFacade

Suite: 446 passed, 9 skipped, 0 failed"
```
