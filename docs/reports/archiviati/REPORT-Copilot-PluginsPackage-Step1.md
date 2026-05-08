# REPORT — SPARK Framework Full Decoupling Architecture — Step 1 di 4
# Plugin Manager Package (`spark/plugins/`)

**Data:** 2026-05-08  
**Agente:** spark-engine-maintainer  
**Branch:** feature/dual-mode-manifest-v3.1  
**Documento di design di riferimento:** `docs/REFACTORING-DESIGN.md`

---

## 1. Stato di completamento

✅ **Step 1 completato con successo — tutti i gate PASS.**

---

## 2. File creati

| File | Tipo | Righe | Note |
|------|------|-------|------|
| `spark/plugins/__init__.py` | Package entry point | ~10 | Esporta `PluginManagerFacade` |
| `spark/plugins/schema.py` | Dataclasses ed eccezioni | ~165 | `PluginError`, `PluginInstallError`, `PluginNotFoundError`, `PluginNotInstalledError`, `PluginManifest`, `PluginRecord` |
| `spark/plugins/registry.py` | Registry locale plugin | ~200 | Gestisce `.github/.spark-plugins`; API: `load`, `get`, `register`, `unregister`, `migrate_from_manifest` |
| `spark/plugins/installer.py` | Installazione file | ~230 | Download via `urllib.request.urlopen`; scrittura via `WorkspaceWriteGateway` |
| `spark/plugins/remover.py` | Rimozione file | ~200 | Preservation gate; pulizia referenze `#file:` |
| `spark/plugins/updater.py` | Aggiornamento plugin | ~110 | Remove + install + registry update |
| `spark/plugins/facade.py` | Punto di accesso unico | ~310 | 6 metodi pubblici: `install`, `remove`, `update`, `list_installed`, `list_available`, `status` |
| `tests/test_plugin_manager_unit.py` | Test unitari | ~320 | 26 test in 6 classi — 0 chiamate HTTP reali |

**Totale file creati: 8**

---

## 3. Risultati pytest

### 3.1 Test del nuovo modulo

```
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/test_plugin_manager_unit.py -v --tb=short
```

```
26 passed, 0 failed (0.25s)
```

| Classe test | Test | Stato |
|---|---|---|
| `TestPluginRegistryRegisterAndGet` | 7 | ✅ PASSED |
| `TestPluginRegistryMigrateFromManifest` | 3 | ✅ PASSED |
| `TestPluginInstallerBuildRawUrl` | 3 | ✅ PASSED |
| `TestPluginInstallerAddInstructionReference` | 4 | ✅ PASSED |
| `TestPluginRemoverRemoveInstructionReference` | 4 | ✅ PASSED |
| `TestPluginManagerFacadeInit` | 5 | ✅ PASSED |

### 3.2 Suite completa non-live (regressione)

```
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

```
439 passed, 9 skipped, 12 subtests passed (15.15s)
```

**Zero regressioni.** Baseline precedente: 313 passed, 9 skipped.  
Il delta di +126 test include il nuovo file (26 test) e test aggiunti da altri task intercorsi.

---

## 4. Deviazioni rispetto al design doc v2.0

### 4.1 Correzione costruttore `WorkspaceWriteGateway`

- **Design doc:** mostrava `WorkspaceWriteGateway(github_root, self._manifest)`
- **Implementazione reale:** il costruttore accetta `workspace_root` (non `github_root`)
- **Risoluzione:** `facade.py` usa correttamente `WorkspaceWriteGateway(workspace_root, self._manifest)`
- **Impatto:** nessuno sul comportamento esterno; il gateway calcola `github_root = workspace_root / ".github"` internamente

### 4.2 Campo `plugin_files` assente nei manifest esistenti

- **Problema:** `package-manifest.json` dei pacchetti attualmente pubblicati (spark-base, scf-master-codecrafter, ecc.) non include il campo `plugin_files`
- **Risoluzione:** `facade.install()` usa `pkg_manifest_data.get("plugin_files") or []` per gestire l'assenza in modo graceful; l'installazione riesce con lista vuota di file
- **Impatto:** nessun file fisico viene scritto su workspace finché i package-manifest dei plugin non vengono aggiornati con `plugin_files`

### 4.3 Nessun `asyncio` nel package

- Il design doc non specificava il requisito di sincronia — rispettato per coerenza con `spark/boot/lifecycle.py` (sincrono) e per evitare complicazioni con il server FastMCP

---

## 5. Decisioni implementative per ambiguità

| Ambiguità | Decisione |
|---|---|
| `migrate_from_manifest()` — come costruire `PluginRecord.files` dai dati manifest? | Raggruppamento per `package` field; i file vengono listati dal manifest come path relativi a `.github/` |
| `remover._cleanup_empty_section()` — quando si considera "vuota" la sezione plugin? | La sezione è vuota quando non rimane nessuna riga che inizia con `#file:` nella sezione delimitata dall'header |
| `facade._build_plugin_record()` — calcolo SHA-256 su file appena scritti | SHA calcolato su `abs_path.read_bytes()` dopo la scrittura da `gateway.write()`; file non trovabili vengono omessi da `file_hashes` senza errore |
| `updater.update()` — quando aggiornare il registry? | Aggiornamento atomic: `register(new_record)` solo dopo che install ha avuto successo |
| `installer._download_file()` — validazione URL | Accetta solo URL che iniziano con `https://raw.githubusercontent.com/`; qualsiasi altro schema viene rifiutato con `PluginInstallError` |

---

## 6. Vincoli rispettati

✅ Nessuna modifica a `spark/boot/lifecycle.py`, `spark/boot/engine.py`, `spark/boot/tools_packages_install.py`, `spark/boot/tools_bootstrap.py`  
✅ Nessuna modifica a file in `spark/manifest/`, `spark/registry/`, `spark/core/`  
✅ Nessun nuovo tool MCP aggiunto in questo step  
✅ Nessun `asyncio` nel package `spark/plugins/`  
✅ Nessun `print()` nei file `spark/plugins/` (logging esclusivamente su `sys.stderr`)  
✅ Nessun import da `spark.boot.lifecycle` nei file del nuovo package  
✅ Transport MCP non contaminato (stdout libero)  

---

## 7. Blocking issues per Nemex81

**Nessun blocking issue.**

Azione consigliata prima dello Step 2:
- Aggiornare `package-manifest.json` dei pacchetti plugin con la chiave `plugin_files` (lista di path relativi) per abilitare l'installazione fisica dei file tramite `PluginManagerFacade.install()`.

---

## 8. Prossimo step

**Step 2 di 4** — Integrazione MCP: aggiunta tool MCP `scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`, `scf_plugin_list`, `scf_plugin_status` in `spark-framework-engine.py` che delegano a `PluginManagerFacade`.

---

OPERAZIONE COMPLETATA: Step 1 — Plugin Manager Package  
GATE: PASS  
CONFIDENCE: 0.98  
FILE TOCCATI: 8 (tutti nuovi, nessun file esistente modificato)  
OUTPUT CHIAVE: 26/26 test PASSED, 439/439 test suite completa PASSED, 0 regressioni  
PROSSIMA AZIONE: Step 2 — Integrazione MCP tools in spark-framework-engine.py
