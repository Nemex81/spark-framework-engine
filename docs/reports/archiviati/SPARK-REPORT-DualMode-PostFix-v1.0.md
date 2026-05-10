# SPARK Dual-Mode Post-Fix — Report v1.0

**Data:** 2026-05-08
**Branch:** `feature/dual-mode-manifest-v3.1`
**Agente:** `@spark-engine-maintainer`
**Baseline di partenza:** 446 passed, 9 skipped, 0 failed

---

## TASK-1 — manager.py audit

### File letti
- `spark/plugins/manager.py` (323 righe — intero file)
- `spark/plugins/__init__.py` (20 righe — intero file)
- `spark/plugins/facade.py` (prime 150 righe — sezione pubblica)
- `spark/registry/client.py` (prime 120 righe — per verificare cosa può lanciare `list_packages()` e `fetch_package_manifest()`)

### Problemi trovati per asse

**Asse 1 — stdout/stderr:** NESSUNO.
`_log: logging.Logger = logging.getLogger("spark-framework-engine")` presente.
Nessun `print()` trovato.

**Asse 2 — Gestione errori e connessione assente:** 3 PROBLEMI.

Analisi causale: `RegistryClient.list_packages()` internamente cattura solo
`RuntimeError` ma non `ValueError`. Se l'URL del registry non è pubblica
(`https://raw.githubusercontent.com/…`), `list_packages()` lascia propagare
`ValueError` al chiamante. La stessa eccezione può propagarsi da
`fetch_package_manifest()` se `repo_url` non è un URL GitHub.

1. **Riga ~47**: `list_available_plugins()` catturava solo `RuntimeError`.
   Un `ValueError` (URL registry non pubblica) avrebbe attraversato il canale MCP.
2. **Riga ~113**: `download_plugin()` chiamava `registry_client.list_packages()`
   senza alcun try/except — nessuna protezione.
3. **Riga ~131**: `download_plugin()` catturava solo `RuntimeError` su
   `fetch_package_manifest()` — mancava `ValueError` (URL repo non GitHub).
4. **Docstring `download_plugin()`**: sezione `Raises:` dichiarava
   `ValueError` e `RuntimeError` come eccezioni uscenti — in contraddizione
   con il contratto MCP "nessuna eccezione nuda". Rimossa.

**Asse 3 — Path resolution:** NESSUNO.
Tutti i path usano `pathlib.Path`. Nessuna concatenazione di stringhe.
`github_root = (target_dir / ".github").resolve()` — corretto.
Path traversal guard presente (`".." in Path(github_rel).parts`).

**Asse 4 — Coerenza con PluginManagerFacade:** NESSUNA DUPLICAZIONE.
`PluginManagerFacade` usa store interno, manifest, `PluginInstaller`,
`PluginRegistry`, `PluginRemover`, `PluginUpdater`.
`PluginManager` scarica direttamente senza nessuno di questi componenti.
Nessuna logica duplicata significativa.

**Asse 5 — Export in `__init__.py`:** NESSUNO.
`spark/plugins/__init__.py` esporta correttamente:
`PluginManagerFacade`, `PluginManager`, `download_plugin`, `list_available_plugins`.
`__all__` allineato.

### Correzioni applicate

| # | File | Riga (aprox.) | Modifica |
|---|------|--------------|----------|
| 1 | `spark/plugins/manager.py` | ~47 | `except RuntimeError` → `except (ValueError, RuntimeError)` in `list_available_plugins()` |
| 2 | `spark/plugins/manager.py` | ~113 | Avvolto `registry_client.list_packages()` in try/except `(ValueError, RuntimeError)` con ritorno strutturato `{"success": False, …}` |
| 3 | `spark/plugins/manager.py` | ~131 | `except RuntimeError` → `except (ValueError, RuntimeError)` per `fetch_package_manifest()` |
| 4 | `spark/plugins/manager.py` | docstring | Rimossa sezione `Raises:` da `download_plugin()` — funzione non lancia più eccezioni nude |

### Risultato py_compile

```
python -m py_compile spark/plugins/manager.py
→ OK (nessun errore sintattico)
```

---

## TASK-2 — README contatore

### Valori rilevati

| Fonte | Valore |
|-------|--------|
| `spark/boot/engine.py` docstring `register_tools()` | `Tools (50)` |
| Conteggio reale `@_register_tool` su tutti i `tools_*.py` | **50** |
| `README.md` prima della modifica | 46 |
| `README.md` dopo la modifica | **50** |

### Dettaglio conteggio reale per file

| File | `@_register_tool` |
|------|:-----------------:|
| `tools_bootstrap.py` | 4 |
| `tools_override.py` | 3 |
| `tools_packages.py` | 0 |
| `tools_packages_diagnostics.py` | 4 |
| `tools_packages_install.py` | 1 |
| `tools_packages_query.py` | 4 |
| `tools_packages_remove.py` | 2 |
| `tools_packages_update.py` | 4 |
| `tools_plugins.py` | 6 |
| `tools_policy.py` | 9 |
| `tools_resources.py` | 13 |
| **TOTALE** | **50** |

### Stato lista tool nel README

I tool `scf_list_plugins` e `scf_install_plugin` erano già presenti nella
lista del README (aggiunti nel commit `0d52e644` del task precedente). ✅

### Correzione applicata

- `README.md` riga 66: `## Tools Disponibili (46)` → `## Tools Disponibili (50)`

### Risultato test coerenza

```
python -m pytest tests/test_engine_coherence.py -q
→ test_tool_counter_consistency: PASSED
```

---

## TASK-3 — Tool MCP verifica

### Lettura integrale tools_plugins.py

File letto integralmente (430 righe). Trovate le definizioni di:
- `scf_list_plugins` — registrato con `@_register_tool("scf_list_plugins")` ✅
- `scf_install_plugin` — registrato con `@_register_tool("scf_install_plugin")` ✅

Entrambi sono dentro `register_plugin_tools()`. ✅

### Verifica import chain

| Simbolo | Percorso dichiarato | Esiste? |
|---------|---------------------|---------|
| `download_plugin` | `spark.plugins.manager` → `spark.plugins` | ✅ |
| `list_available_plugins` | `spark.plugins.manager` → `spark.plugins` | ✅ |
| `PluginManagerFacade` | `spark.plugins` → `spark.plugins.facade` | ✅ |
| `RegistryClient` | `spark.registry.client` | ✅ |
| `_log` | `logging.getLogger("spark-framework-engine")` in `tools_plugins.py` | ✅ |

Import in `tools_plugins.py`:
```python
from spark.plugins import PluginManagerFacade
from spark.plugins.manager import download_plugin, list_available_plugins
from spark.registry.client import RegistryClient
```
Tutti i simboli risolvibili. ✅

### Verifica gestione errori nei tool

**`scf_list_plugins`**: wrap completo con `try/except Exception` → restituisce
`{"status": "error", "plugins": [], "count": 0, "message": str(exc)}`. ✅

**`scf_install_plugin`**: wrap completo con `try/except Exception` → restituisce
`{"status": "error", "package_id": …, "version": …, "files_written": [],
"files_skipped": [], "errors": [str(exc)], "message": str(exc)}`. ✅

Nessuna eccezione può raggiungere il canale MCP. ✅

### Test import sintetico

```
python -c "from spark.plugins import PluginManager, download_plugin, list_available_plugins; print('OK')"
→ OK
```

---

## File modificati

| File | Tipo modifica | Descrizione |
|------|:-------------:|-------------|
| `spark/plugins/manager.py` | Fix | Asse 2: 3 catch estesi + rimossa sezione `Raises:` dalla docstring |
| `README.md` | Aggiornamento | Contatore tool 46 → 50 |

---

## Suite test finale

```
python -m pytest -q --ignore=tests/test_integration_live.py
→ 446 passed, 9 skipped, 12 subtests passed in 5.19s
```

---

## Stato finale

**PRONTO PER MERGE**

Checklist pre-commit:
- [x] `py_compile` su `spark/plugins/manager.py`: OK
- [x] Suite non-live: 446 passed, 0 failed
- [x] Nessun `print()` su stdout in file toccati
- [x] Contatore tool `engine.py` (50) == `README.md` (50) == contatore reale (50)
