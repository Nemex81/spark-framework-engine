# spark/boot/ — Sottosistema di Boot e Tool MCP

Questo package contiene il cuore operativo del motore SPARK:
l'engine principale, la sequenza di avvio, il manager di onboarding
e tutte le factory function che registrano i 51 tool MCP.

---

## File

### `sequence.py` — Builder dell'applicazione

Funzione `_build_app(engine_root: Path) -> FastMCP`.  
Assembla tutti i sottosistemi nell'ordine corretto e restituisce
l'istanza FastMCP pronta per il trasporto stdio.

**Sequenza di boot (11 passi):**

1. `FastMCP("sparkFrameworkEngine")`
2. `WorkspaceLocator(engine_root).resolve()` → `WorkspaceContext`
3. `resolve_runtime_dir(engine_root, workspace_root)` → `runtime_dir`
4. `_migrate_runtime_to_engine_dir(github_root, runtime_dir)` [idempotente]
5. `FrameworkInventory(context)`
6. `validate_engine_manifest(engine_root)` + `inventory.populate_mcp_registry(engine_manifest)`
7. `SparkFrameworkEngine(mcp, context, inventory, runtime_dir=runtime_dir)`
8. `app.register_resources()`
9. `app.register_tools()`
10. `app._v3_repopulate_registry()` — registra pacchetti installati dallo store al boot
11. `app.ensure_minimal_bootstrap()` — auto Cat.A bootstrap

---

### `engine.py` — SparkFrameworkEngine

Orchestratore centrale. Espone:

- `register_resources()` — registra 19 MCP resources statiche
- `register_tools()` — delega a tutte le factory `register_*_tools()`
- `_v3_repopulate_registry()` — popola il registry MCP dai pacchetti v3 installati
- `ensure_minimal_bootstrap()` — copia file Cat.A se assenti nel workspace
- `_install_package_v3()` / `_remove_package_v3()` — percorsi install/remove con rollback atomico
- `_install_workspace_files_v3()` — batch write + SHA sentinel skip

---

### `onboarding.py` — OnboardingManager

Gestisce il first-run automatico. Idempotente, non-fatal (tutti gli errori
vanno su `sys.stderr`).

- `is_first_run()`: legge `.github/spark-packages.json`, confronta con manifest
- `run_onboarding()`: 3 passi (bootstrap → store → install declared packages)
- Status: `"completed"` | `"partial"` | `"skipped"`

---

### `lifecycle.py` — Bootstrap lifecycle

Helper per il ciclo di vita del bootstrap engine-side.
Contiene `_install_workspace_files_v3()` con batch writes e `upsert_many()`
ottimizzati (OPT-4 performance batch).

---

### `install_helpers.py` — Helper installazione

Funzioni di supporto condivise tra `tools_packages_install.py` e
`tools_packages_update.py`: preflight, build diff summary, policy resolution.

---

### `validation.py` — Validazione manifest

Funzioni per validare `engine-manifest.json` e i package manifest.

---

## Tool factory (10 file)

Ogni file registra un gruppo tematico di tool MCP tramite una funzione
`register_*_tools(engine, mcp, tool_names)`. Il pattern è uniforme:

```python
def _register_tool(name: str) -> Any:
    tool_names.append(name)
    return mcp.tool()

@_register_tool("scf_nome_tool")
async def scf_nome_tool(...) -> dict[str, Any]:
    """Docstring esposta al client MCP."""
    ...
```

| File | Tool registrati |
|------|----------------|
| `tools_bootstrap.py` | `scf_verify_workspace`, `scf_verify_system`, `scf_bootstrap_workspace`, `scf_migrate_workspace` |
| `tools_packages.py` | Facade di retrocompatibilità — delega ai 5 submoduli |
| `tools_packages_query.py` | `scf_list_available_packages`, `scf_get_package_info`, `scf_list_installed_packages`, `scf_plan_install` |
| `tools_packages_install.py` | `scf_install_package` |
| `tools_packages_update.py` | `scf_check_updates`, `scf_update_package`, `scf_update_packages`, `scf_apply_updates` |
| `tools_packages_remove.py` | `scf_remove_package`, `scf_get_package_changelog` |
| `tools_packages_diagnostics.py` | `scf_resolve_conflict_ai`, `scf_approve_conflict`, `scf_reject_conflict`, `scf_finalize_update` |
| `tools_override.py` | `scf_list_overrides`, `scf_override_resource`, `scf_drop_override` |
| `tools_plugins.py` | `scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`, `scf_plugin_list`, `scf_get_plugin_info`, `scf_plugin_list_remote`, `scf_plugin_install_remote` |
| `tools_resources.py` | `scf_read_resource`, 4 `*_resource`, `scf_list_agents`, `scf_get_agent`, `scf_list_skills`, `scf_get_skill`, `scf_list_instructions`, `scf_get_instruction`, `scf_list_prompts`, `scf_get_prompt` |
| `tools_policy.py` | `scf_get_project_profile`, `scf_get_global_instructions`, `scf_get_model_policy`, `scf_get_framework_version`, `scf_get_workspace_info`, `scf_get_runtime_state`, `scf_update_runtime_state`, `scf_get_update_policy`, `scf_set_update_policy` |


---

## Regole invarianti

- Nessuna scrittura su `stdout` — tutto il log va su `sys.stderr`.
- Tutti i tool pubblici sono registrati con `@_register_tool("scf_*")`.
- `tools_packages.py` è una facade pura: zero logica propria.
- I tool deprecati restituiscono sempre `deprecated: true` e `migrate_to` nel payload.
