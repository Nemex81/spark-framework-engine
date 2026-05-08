# REPORT — SPARK Framework: Integrazione MCP + Aggiornamento Manifest Upstream (Step 2)

**Data:** 2026-05  
**Autore:** spark-engine-maintainer (GitHub Copilot)  
**Branch:** `feature/dual-mode-manifest-v3.1`  
**Baseline pre-step:** 439 passed, 9 skipped  
**Baseline post-step:** 446 passed, 9 skipped, 0 regressions

---

## Sommario Esecutivo

Step 2 dell'architettura Full Decoupling completato con successo.
Sono stati registrati 4 nuovi tool MCP di gestione lifecycle plugin
(`scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`,
`scf_plugin_list`), aggiornati i manifest upstream con il nuovo campo
`plugin_files`, e aggiunti 7 test di integrazione che coprono tutti i
percorsi principali della facade. Gate finale: **0 regressioni**.

---

## TASK A — Aggiornamento Manifest Upstream

### `scf-master-codecrafter/package-manifest.json`

| Campo | Prima | Dopo |
|-------|-------|------|
| `schema_version` | `"3.0"` | `"3.1"` |
| `version` | `"2.6.0"` | `"2.6.1"` |
| `plugin_files` | assente | aggiunto (13 file) |

**`plugin_files` aggiunti:**
```json
[
  ".github/agents/code-Agent-Analyze.md",
  ".github/agents/code-Agent-Code.md",
  ".github/agents/code-Agent-CodeRouter.md",
  ".github/agents/code-Agent-CodeUI.md",
  ".github/agents/code-Agent-Design.md",
  ".github/agents/code-Agent-Docs.md",
  ".github/agents/code-Agent-FrameworkDocs.md",
  ".github/agents/code-Agent-Git.md",
  ".github/agents/code-Agent-Helper.md",
  ".github/agents/code-Agent-Plan.md",
  ".github/agents/code-Agent-Research.md",
  ".github/AGENTS-master.md",
  ".github/instructions/mcp-context.instructions.md"
]
```

**Criteri di selezione applicati:**
- Inclusi: file `.github/agents/`, `.github/AGENTS-*.md`, `.github/instructions/`
- Esclusi: changelogs, `copilot-instructions.md` (gestito da `merge_sections`),
  `prompts/README.md`, skills (serviti via MCP dal motore, non dal workspace fisico)

### `scf-pycode-crafter/package-manifest.json`

| Campo | Prima | Dopo |
|-------|-------|------|
| `schema_version` | `"3.0"` | `"3.1"` |
| `version` | `"2.2.1"` | `"2.2.2"` |
| `plugin_files` | assente | aggiunto (9 file) |

**`plugin_files` aggiunti:**
```json
[
  ".github/agents/py-Agent-Analyze.md",
  ".github/agents/py-Agent-Code.md",
  ".github/agents/py-Agent-Design.md",
  ".github/agents/py-Agent-Plan.md",
  ".github/agents/py-Agent-Validate.md",
  ".github/AGENTS-python.md",
  ".github/instructions/python.instructions.md",
  ".github/instructions/tests.instructions.md",
  ".github/python.profile.md"
]
```

### Comandi git proposti (da eseguire manualmente)

```bash
# scf-master-codecrafter
cd path/to/scf-master-codecrafter
git checkout -b feature/dual-mode-manifest-v3.1
git add package-manifest.json
git commit -m "feat(schema): add plugin_files field — schema v3.1 (bump 2.6.0 → 2.6.1)"

# scf-pycode-crafter
cd path/to/scf-pycode-crafter
git checkout -b feature/dual-mode-manifest-v3.1
git add package-manifest.json
git commit -m "feat(schema): add plugin_files field — schema v3.1 (bump 2.2.1 → 2.2.2)"
```

---

## TASK B — Registrazione Tool MCP nel Server

### File creato: `spark/boot/tools_plugins.py`

Factory `register_plugin_tools(engine, mcp, tool_names)` che registra
4 tool MCP seguendo esattamente il pattern stabilito da `tools_policy.py`
e `tools_packages_remove.py`:

| Tool MCP | Metodo Facade | Input | Output principali |
|----------|--------------|-------|-------------------|
| `scf_plugin_install` | `facade.install(pkg_id)` | `pkg_id, workspace_root` | `status, pkg_id, version, files_installed, message` |
| `scf_plugin_remove` | `facade.remove(pkg_id)` | `pkg_id, workspace_root` | `status, pkg_id, files_removed, message` |
| `scf_plugin_update` | `facade.update(pkg_id)` | `pkg_id, workspace_root` | `status, pkg_id, old_version, new_version, message` |
| `scf_plugin_list` | `facade.list_installed()` + `facade.list_available()` | `workspace_root` | `status, installed, available, message` |

**Helper `_make_facade()`:** istanzia `PluginManagerFacade(workspace_root=Path(ws))` 
per ogni chiamata MCP, con fallback a `engine._ctx.workspace_root` se il parametro
`workspace_root` è vuoto.

**Comportamento di error handling:**
- Ogni tool avvolge l'intera chiamata facade in `try/except Exception`
- Ritorna `{"status": "error", ..., "message": str(exc)}` invece di propagare eccezioni
- Il tag `status` è `"ok"` / `"error"` (normalizzazione da `success: bool` della facade)
- Logging su `sys.stderr` tramite `logging.getLogger("spark-framework-engine")`

### Modifiche a `spark/boot/engine.py`

1. **Import aggiunto** (riga 176, dopo `register_package_tools`):
   ```python
   from spark.boot.tools_plugins import register_plugin_tools
   ```

2. **Chiamata in `register_tools()`** (dopo `register_bootstrap_tools`):
   ```python
   # D.6: i 4 tool plugin lifecycle sono registrati dalla factory in tools_plugins.py.
   register_plugin_tools(self, self._mcp, tool_names)
   ```

3. **Docstring aggiornata**: `Tools (44)` → `Tools (48)`

### Modifiche a `tests/test_engine_coherence.py`

Aggiunta di `_TOOLS_PLUGINS_PATH` al dizionario dei percorsi sorgente e alla
concatenazione nel test `test_tool_counter_consistency`. Il test verifica che:
- Il numero di `@_register_tool(` presenti nel sorgente aggregato coincida con `Tools (N)`
- **Risultato: PASS** — 48 tool reali, commento `Tools (48)`: corrispondenza confermata.

**Totale tool MCP post-Step2: 48**  
(15 resource tools + 13 override/resource + 9 policy + 15 packages + 4 bootstrap → 48;
il log è dinamico con `len(tool_names)`, nessun hardcoding)

---

## TASK C — Test di Integrazione

### File creato: `tests/test_plugin_manager_integration.py`

7 test di integrazione (≥4 richiesti dalla spec):

| Test | Verifica | Esito |
|------|---------|-------|
| `test_scf_plugin_list_empty_workspace` | struttura corretta con workspace vuoto | ✅ PASS |
| `test_scf_plugin_list_response_keys` | chiavi obbligatorie nella risposta composita | ✅ PASS |
| `test_scf_plugin_install_nonexistent_pkg` | `install()` con pkg non esistente → `success=False` senza crash | ✅ PASS |
| `test_scf_plugin_install_maps_to_status_error` | normalizzazione `success=False` → `status='error'` | ✅ PASS |
| `test_scf_plugin_remove_not_installed` | `remove()` su plugin non installato → `success=False` senza crash | ✅ PASS |
| `test_scf_plugin_remove_maps_to_status_error` | normalizzazione `success=False` → `status='error'` | ✅ PASS |
| `test_install_list_remove_cycle_mocked` | ciclo completo install → list → remove con HTTP mocked | ✅ PASS |

**Mock applicati:** `RegistryClient.list_packages()`, `RegistryClient.fetch_package_manifest()`,
`PluginInstaller.install_files()`, `PluginInstaller._add_instruction_reference()`,
`PluginRemover.remove_files()`, `PluginRemover._remove_instruction_reference()`

**Nessuna chiamata HTTP reale nei test.**

---

## Deviazioni dalla Spec

### DEV-1: `list_plugins(workspace_root)` → metodi separati sulla facade

La spec originale menziona `PluginManagerFacade.list_plugins(workspace_root)` come
metodo unico. L'implementazione effettiva della facade (Step 1) espone due metodi
separati: `list_installed()` e `list_available()`.

**Soluzione adottata:** `scf_plugin_list` chiama entrambi i metodi e aggrega il
risultato in `{"status": "ok", "installed": [...], "available": [...], "message": ...}`.
Se il registry remoto non è raggiungibile, `available` è lista vuota e il campo
`registry_error` riporta il messaggio di errore.

### DEV-2: `workspace_root` come `str` opzionale (non obbligatorio)

La spec mostra `workspace_root` come parametro obbligatorio. Nell'implementazione
è definito come `workspace_root: str = ""` con fallback a `engine._ctx.workspace_root`.
Questo evita che il client MCP debba sempre specificare il workspace quando il
server è già configurato con il workspace corretto.

### DEV-3: `python.profile.md` incluso in `plugin_files` scf-pycode-crafter

Il file `.github/python.profile.md` è stato incluso in `plugin_files` in quanto
file fisico utile nel workspace (profilo linguaggio Python per Copilot), non un
file di configurazione engine.

---

## Stato del Sistema Post-Step 2

| Componente | Stato |
|-----------|-------|
| `spark/boot/tools_plugins.py` | ✅ Creato — 4 tool MCP registrati |
| `spark/boot/engine.py` | ✅ Aggiornato — import + call + docstring |
| `tests/test_engine_coherence.py` | ✅ Aggiornato — tools_plugins incluso nel conteggio |
| `scf-master-codecrafter/package-manifest.json` | ✅ `v2.6.1`, `schema 3.1`, `plugin_files` aggiunto |
| `scf-pycode-crafter/package-manifest.json` | ✅ `v2.2.2`, `schema 3.1`, `plugin_files` aggiunto |
| `tests/test_plugin_manager_integration.py` | ✅ 7 test — tutti PASS |
| Suite completa non-live | ✅ **446 passed, 9 skipped, 0 failed** |
| Regressioni | ✅ **0** (baseline era 439 passed) |

---

## Prossima Azione (Step 3)

Step 3 dell'architettura Full Decoupling previsto nel design doc `SPARK-DESIGN-FullDecoupling-v2.0.md`:

- **Separazione Universo A/B**: engine MCP diventa sola lettura per Universo A; 
  Plugin Manager (Universo B) opera autonomamente sul filesystem
- **`#file:` reference in `copilot-instructions.md`**: `PluginInstaller._add_instruction_reference()` 
  già implementato in Step 1; validare end-to-end
- **Bootstrap update**: aggiornare `scf_bootstrap_workspace` per usare `plugin_files` 
  invece dei glob-based whitelist
- **PR upstream**: aprire PR su `scf-master-codecrafter` e `scf-pycode-crafter` 
  con le modifiche manifest di Step 2
- **Validazione engine coherence**: verificare che il contatore tool rimanga in 
  sync dopo eventuali nuovi tool in Step 3
