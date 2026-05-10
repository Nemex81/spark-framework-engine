# tests/ — Suite di Test del Motore SPARK

Questa directory contiene la suite completa di test pytest per
`spark-framework-engine`. I test coprono ogni modulo del motore
con test unitari, di integrazione e smoke test.

---

## Come eseguire i test

```bash
# Suite completa (esclude test live che richiedono connessione di rete)
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_integration_live.py --tb=short

# Solo i test di bootstrap
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/test_bootstrap_workspace.py tests/test_bootstrap_workspace_extended.py -q --tb=short

# Con coverage
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_integration_live.py --cov=spark
```

**Baseline corrente:** 554 passed / 0 skipped / 0 failed ✅  
**Nota:** Suite audit legacy test completato (2026-05-10). Ultimo skipped test (env-gated
`SPARK_SMOKE_TEST=1`) eliminato tramite mock subprocess. Tutte le suite **100% green**.
**`test_integration_live.py`** — escluso dal CI: richiede accesso a internet
e al registry pubblico SCF. Eseguire solo in ambienti con connessione garantita.

---

## Organizzazione

| File | Area |
|------|------|
| `conftest.py` | Fixture condivise (workspace tmp, manifest mock, context) |
| `test_bootstrap_workspace.py` | `scf_bootstrap_workspace` — scenari principali |
| `test_bootstrap_workspace_extended.py` | `scf_bootstrap_workspace` — edge case, idempotenza, conflict mode |
| `test_boot_sequence.py` | Sequenza di avvio `_build_app()` completa |
| `test_deployment_modes.py` | `deployment_mode: auto/store/copy` per installazione v3 |
| `test_engine_coherence.py` | Coerenza interna del motore (tool count, decorator, naming) |
| `test_engine_inventory.py` | `EngineInventory` — caricamento `engine-manifest.json` |
| `test_framework_inventory_resolver.py` | `FrameworkInventory` — risoluzione risorse MCP |
| `test_framework_inventory_skills.py` | `FrameworkInventory` — scoperta skill |
| `test_framework_versions.py` | `scf_get_framework_version` — versioni motore e pacchetti |
| `test_frontmatter_parser.py` | Parser frontmatter YAML nei file SCF |
| `test_install_helpers.py` | Funzioni preflight e build diff summary |
| `test_install_workspace_files.py` | `_install_workspace_files_v3()` — batch write, SHA skip, rollback |
| `test_integration_live.py` | ⚠️ Test live — escluso dal CI |
| `test_lifecycle.py` | `ManifestManager` + `SnapshotManager` ciclo di vita |
| `test_manifest_integrity.py` | Integrità del manifest `.scf-manifest.json` |
| `test_manifest_manager.py` | `ManifestManager` — CRUD, cache mtime-based, upsert_many |
| `test_merge_engine.py` | `MergeEngine` — 3-way merge, rilevamento conflitti |
| `test_merge_integration.py` | Scenari di merge end-to-end con sessioni |
| `test_merge_session.py` | `MergeSessionManager` — apertura, approvazione, finalizzazione sessioni |
| `test_merge_validators.py` | Validatori post-merge (frontmatter, struttura) |
| `test_migrate_workspace.py` | `scf_migrate_workspace` — migrazione runtime dir |
| `test_multi_owner_policy.py` | Policy multi-owner su file condivisi |
| `test_no_orphan_imports.py` | Verifica che nessun import sia orfano (non usato) |
| `test_onboarding_manager.py` | `OnboardingManager` — first-run, is_first_run, 3 passi |
| `test_override_tools.py` | `scf_list_overrides`, `scf_override_resource`, `scf_drop_override` |
| `test_package_installation_policies.py` | Policy di installazione (conflict_mode, update_mode) |
| `test_package_lifecycle_v3.py` | Ciclo install/update/remove completo su percorso v3 |
| `test_phase6_bootstrap_assets.py` | `spark/assets/phase6.py` — bootstrap batch write |
| `test_plugin_manager_integration.py` | `PluginManagerFacade` — scenari end-to-end |
| `test_plugin_manager_unit.py` | `PluginManagerFacade` — unit test (26 test) |
| `test_resource_aliases.py` | Alias e name normalization nella risoluzione risorse |
| `test_resource_registry.py` | `McpResourceRegistry` — register, get, list_by_type |
| `test_resource_resolver.py` | `ResourceResolver` — URI resolution, priority override > engine |
| `test_resource_store.py` | `PackageResourceStore` (schema < 3.0) |
| `test_section_merge.py` | Merge per sezioni SCF (marcatori `SCF:BEGIN/END`) |
| `test_server_stdio_smoke.py` | Smoke test del server stdio (import + boot senza crash) |
| `test_smoke_bootstrap_v3.py` | Smoke test install/remove v3 end-to-end |
| `test_snapshot_manager.py` | `SnapshotManager` — creazione, restore, cleanup snapshot |
| `test_spark_init.py` | `spark-init.py` — inizializzazione workspace |
| `test_standalone_files_v3.py` | File standalone in installazione v3 (`deployment_mode: copy`) |
| `test_update_diff.py` | Calcolo diff tra versioni di file |
| `test_update_planner.py` | Pianificazione aggiornamenti multi-pacchetto |
| `test_update_policy.py` | `scf_get_update_policy`, `scf_set_update_policy` |
| `test_verify_workspace_divergence.py` | `scf_verify_workspace` — source divergence report |
| `test_workspace_gateway.py` | `WorkspaceWriteGateway` — write atomico, SHA guard, preservation |
| `test_workspace_locator.py` | `WorkspaceLocator` — risoluzione workspace da `engine_root` |
| `test_ap1_scf_get_agent_source_warning.py` | Acceptance test: `scf_get_agent` `source_warning` |

---

## Convenzioni

- Tutte le fixture di workspace usano `tmp_path` di pytest (no filesystem reale).
- I mock di rete sono limitati a `RegistryClient` e a chiamate HTTP esterne.
- Nessun test scrive su `.github/` del repository del motore stesso.
- `test_integration_live.py` è l'unica eccezione: usa il registry remoto reale.
