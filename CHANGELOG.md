<!-- markdownlint-disable MD022 MD024 MD032 MD038 -->

# Changelog

Tutte le modifiche importanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com) e il versioning segue [Semantic Versioning](https://semver.org).

---

## [Unreleased]

### Added — Post-Dual-Universe Cleanup (2026-05-11)

- `tests/conftest.py` — hook `pytest_pyfunc_call` per eseguire `async def test_*`
  via `asyncio.run()` senza dipendenza pytest-asyncio. Riabilita 19 test async
  precedentemente saltati in `test_bootstrap_workspace_extended.py` e
  `test_legacy_init_audit.py`. Zero nuove dipendenze.
- `tests/test_registry_client.py` — 18 nuovi test per `RegistryClient`:
  coprono `fetch`, `list_packages`, `_load_cache`, `_save_cache`,
  `fetch_package_manifest`, `fetch_raw_file` con mock completo (zero rete).
  Coverage `spark.registry.client`: **39% → 90%**.
- `.scf-registry-cache.json` e `.github/.scf-registry-cache.json` — allineati:
  `min_engine_version` 3.1.0 → 3.4.0 per `spark-base`, `scf-master-codecrafter`,
  `scf-pycode-crafter`. Risolve il `engine_min_mismatch` segnalato da `scf_verify_system`.
- `docs/reports/SPARK-REPORT-PostDualUniverse-v1.0.md` — report di chiusura post dual-universe.
  Suite finale: **575 passed (+37), 1 failed (pre-esistente), 0 skipped, 0 regressioni**.

### Added — Dual Universe Package Resolution (2026-05-11)

- `spark/boot/tools_bootstrap.py` — aggiunta logica di routing `delivery_mode`-based:
  se `delivery_mode=mcp_only` e manifest locale presente in `packages/{id}/` →
  Universo A (risoluzione da disco, zero chiamate HTTP); altrimenti → Universo B
  (registry remoto HTTPS via `RegistryClient`). Funzioni aggiunte:
  `_resolve_local_manifest(engine_root, package_id)` (standalone),
  `_try_local_install_context(package_id)` (closure),
  `_build_local_file_records(...)` (closure).
  Il routing in `_get_package_install_context()` chiama prima `_try_local_install_context()`
  e fa fallback a `_ih._get_package_install_context()` solo se ritorna `None`.
- `packages/spark-base/package-manifest.json` — aggiunto `"delivery_mode": "mcp_only"`
  per allineamento con gli altri 3 pacchetti engine-embedded già conformi.
- `tests/test_dual_universe_resolution.py` — 4 nuovi test: `test_local_context_returned_for_mcp_only_package`,
  `test_local_context_returns_none_when_no_local_manifest`,
  `test_local_context_returns_none_without_mcp_only`,
  `test_spark_base_real_manifest_qualifies_for_universe_a`.
  Suite: **538 passed (+4), 1 failed (pre-esistente), 19 skipped, 0 regressioni**.

### Changed — risoluzione final skipped test (env-gated → mock subprocess) (2026-05-10)

- `tests/test_server_stdio_smoke.py` — `test_mcp_initialize_via_stdio` precedentemente
  env-gated su `SPARK_SMOKE_TEST=1`. Ora esecuzione deterministica con mock di
  `subprocess.Popen` senza lanciare il server reale. Valida comunque il contratto
  JSON-RPC initialize. Rimosso marker `@pytest.mark.skipif`. Suite: 553p,1s → 554p,0s.
- Suite test: **100% passed (554 passed, 0 skipped)** — audit legacy test completato.

### Changed — legacy test audit e cleanup (2026-05-10)

- `tests/test_bootstrap_workspace.py` — eliminati 5 test obsoleti (dead code legacy mode
  e mocking strategy stale): `test_bootstrap_install_base_installs_spark_base_when_requested`,
  `test_bootstrap_extended_creates_policy_then_requires_authorization`,
  `test_bootstrap_install_base_with_integrative_mode_and_authorization`,
  prima definizione duplicata di `test_bootstrap_legacy_workspace_requires_authorization_before_policy_write`.
  Riabilitati 3 test con fix assertion (`prefs_path` da `runtime/spark-user-prefs.json`
  a `user-prefs.json`): `test_bootstrap_extended_requires_authorization_after_policy_creation`,
  `test_bootstrap_extended_writes_assets_and_policy_when_authorized`,
  `test_bootstrap_legacy_workspace_requires_authorization_before_policy_write`.
- `tests/test_smoke_bootstrap_v3.py` — eliminati 2 test Phase 6 obsoleti:
  `test_scenario_7_5_bootstrap_genera_agents_md`,
  `test_scenario_7_6_dropdown_agenti_equivalente_indice_agents`.
- Suite post-audit: `553 passed, 1 skipped` (era `550 passed, 9 skipped`).
  Unico skip rimasto: `test_mcp_initialize_via_stdio` (env-gate `SPARK_SMOKE_TEST=1`, by design).

## [3.4.0] - 2026-05-10

### Fixed — bootstrap sentinel legacy → Agent-Welcome.md (2026-05-10)

- `spark/boot/tools_bootstrap.py` — sentinel di idempotenza bootstrap cambiato da
  `spark-assistant.agent.md` a `Agent-Welcome.md` (agente neutro sempre presente in
  `spark-base` v2.1.0). Rimossi `spark-guide.agent.md` e `spark-assistant.agent.md`
  da `_SPARK_BASE_BOOTSTRAP_SENTINELS` (erano legacy post role-inversion v1.1.0).
  `_SPARK_BASE_BOOTSTRAP_SENTINELS` ora contiene `[".github/AGENTS.md",
  ".github/agents/Agent-Welcome.md"]`.
- `spark/boot/install_helpers.py` — `sentinel_path` in `_detect_workspace_migration_state`
  aggiornato da `agents/spark-assistant.agent.md` a `AGENTS.md` (rilevazione workspace
  legacy più neutro e stabile).
- `packages/spark-base/.github/AGENTS.md` — rimosso riferimento errato "da `spark-ops`"
  nella sezione `Agent-Research` (`Agent-Orchestrator` è in `spark-base` da v2.1.0).
- `packages/spark-base/README.md` — versione aggiornata a `2.1.0`; tabella agenti
  corretta (9 agenti: aggiunto `Agent-Orchestrator`, rimossi `spark-assistant` e
  `spark-guide` ora in `spark-ops`); nota skill aggiornata (`semantic-gate`,
  `error-recovery`, `task-scope-guard` sono in `spark-base` da v2.1.0).
- `tests/test_bootstrap_workspace.py` e `tests/test_bootstrap_workspace_extended.py` —
  aggiornati per riflettere il nuovo sentinel `Agent-Welcome.md`; test
  `test_bootstrap_does_not_retrack_spark_guide_when_owned_by_spark_base` rinominato
  e riscritto per `Agent-Welcome.md`; cross-owner test aggiornato su
  `framework-guard.instructions.md`.

### Fixed — spark-ops role inversion (2026-05-10)

- `packages/spark-base/package-manifest.json` — bump a `2.1.0`.
  `Agent-Orchestrator` (orchestrazione ciclo E2E) ritorna in `spark-base` come agente
  core user-operativo. Skill operative correlate (`error-recovery`, `semantic-gate`,
  `task-scope-guard`) e prompt `orchestrate` seguono il trasferimento in `spark-base`.
- `packages/spark-ops/package-manifest.json` — bump a `1.1.0`.
  `spark-assistant` e `spark-guide` (gateway onboarding e routing) si spostano in
  `spark-ops` come layer sistemico di accesso; le 3 skill E2E vengono rimosse dal
  catalogo `spark-ops` poiche ora in `spark-base`.
- `tests/test_spark_ops_decoupling_manifest.py` — `MIGRATED_AGENTS`,
  `MIGRATED_PROMPTS`, `MIGRATED_SKILLS` e `BASE_OWNED_AFTER_SPLIT` aggiornati
  per riflettere la nuova distribuzione.
- `packages/spark-ops/.github/AGENTS.md` e `packages/spark-base/.github/AGENTS.md`
  aggiornati con i riferimenti corretti agli agenti per package.
- `packages/spark-ops/README.md` — aggiornato con la nuova lista risorse MCP.
- `packages/spark-ops/.github/agents/spark-assistant.agent.md` e
  `packages/spark-ops/.github/agents/spark-guide.agent.md` — creati con
  `scf_owner: "spark-ops"` (file fisici nel package corretto).

### Added - spark-ops decoupling (2026-05-10)

- `packages/spark-ops/` - nuovo package MCP-only operativo per `Agent-Orchestrator`,
  `Agent-FrameworkDocs`, `Agent-Release`, skill E2E e prompt di framework maintenance.
- `tests/test_spark_ops_decoupling_manifest.py` - regressione sul contratto manifest
  `spark-base`/`spark-ops` e sulle dipendenze dei package embedded.

### Changed - spark-ops decoupling (2026-05-10)

- `packages/spark-base/package-manifest.json` - bump a `2.0.0` e perimetro
  ridotto a risorse user-facing/shared; gli asset operativi sono rimossi dal
  catalogo distribuito senza eliminazione fisica dei file legacy.
- `packages/scf-master-codecrafter/package-manifest.json` - bump a `2.7.0`,
  dipendenza minima `spark-base >= 2.0.0` e nuova dipendenza `spark-ops >= 1.0.0`.
- `packages/scf-pycode-crafter/package-manifest.json` - bump a `2.3.0` e
  dipendenza minima `scf-master-codecrafter >= 2.7.0`.
- `README.md`, `docs/architecture.md` e README package aggiornati con la
  separazione `spark-base` user-facing / `spark-ops` operational.

### Added — Legacy Init Audit v1.0 (2026-05-XX)

- `spark/boot/tools_bootstrap.py` — aggiunto `_classify_bootstrap_conflict(dest_path: Path) -> str`,
  helper module-level che legge il frontmatter YAML di un file preesistente nel workspace e
  restituisce `"spark_outdated"` (se `spark: true` presente) oppure `"non_spark"` (altrimenti).
- `spark/boot/tools_bootstrap.py` — `scf_bootstrap_workspace` ora espone 3 nuovi campi nel
  payload di risposta:
  - `files_conflict_non_spark`: file protetti che NON hanno frontmatter `spark: true` (Scenario X).
  - `files_conflict_spark_outdated`: file protetti che hanno frontmatter `spark: true` (Scenario Y).
  - `spark_outdated_details`: lista di dict `{file, existing_version}` per i file SPARK obsoleti,
    con la versione letta dal frontmatter del file esistente nel workspace.
  Nessun cambio comportamentale: i file continuano a essere protetti esattamente come prima.
  Cambia solo il payload MCP, che ora permette agli utenti di distinguere i conflitti
  e decidere consapevolmente se usare `force=True`.
- `tests/test_legacy_init_audit.py` — 5 nuovi test (TDD, Scenario X + Y):
  `test_bootstrap_classifies_non_spark_conflict_file`,
  `test_bootstrap_non_spark_conflict_payload_is_empty_on_clean_workspace`,
  `test_bootstrap_classifies_spark_outdated_conflict_file`,
  `test_bootstrap_spark_outdated_includes_version_details`,
  `test_bootstrap_non_md_file_classified_as_non_spark`.

### Fixed

- `tests/test_multi_owner_policy.py` —
  `test_extend_policy_can_create_section_file_when_shared_target_is_missing`:
  rimossa race condition mtime nella validazione della cache di `ManifestManager`.
  Il test riusava la stessa istanza per setup e assertion; su filesystem veloci
  (es. Windows NTFS in run brevi) le due scritture avvenivano nello stesso clock
  tick (T1 == T2), impedendo l'invalidazione della cache e restituendo dati stale
  (`["pkg-a"]` invece di `["pkg-a", "pkg-b"]`). Fix: l'assertion finale crea una
  fresh instance `ManifestManager(github_root)` — stessa semantica, lettura
  garantita da disco.

### Added — GAP-Y-2 Frontmatter-Only Update (2026-05-XX)

- `spark/boot/tools_bootstrap.py` — aggiunto `_apply_frontmatter_only_update(source_path, dest_path) -> str | None`,
  helper module-level che ricostruisce il contenuto di un file SPARK obsoleto
  combinando il frontmatter verbatim del file sorgente engine con il body
  verbatim del file utente esistente nel workspace. Restituisce `None` se il
  frontmatter sorgente è malformato (fallback a protezione).
- `spark/boot/tools_bootstrap.py` — `scf_bootstrap_workspace` ora gestisce i file
  SPARK obsoleti (`spark_outdated`) con `force=True` tramite frontmatter-only update:
  aggiorna solo il blocco YAML tra i marker `---` dal sorgente engine, lasciando
  il body utente intatto. I file non-SPARK continuano a ricevere sovrascrittura
  completa (comportamento invariato). Fallback a `files_protected` se il
  frontmatter-only update fallisce.
- `spark/boot/tools_bootstrap.py` — nuovo campo nel payload di risposta:
  - `files_updated_frontmatter_only`: file SPARK obsoleti aggiornati con la
    strategia frontmatter-only (aggiunto anche a `files_written` e `files_copied`
    per compatibilità backward).
- `tests/test_legacy_init_audit.py` — 7 nuovi test (GAP-Y-2):
  `test_force_true_updates_frontmatter_only_for_spark_outdated`,
  `test_force_true_preserves_user_body_when_spark_outdated`,
  `test_force_true_non_spark_file_still_gets_full_overwrite`,
  `test_force_true_spark_outdated_payload_on_clean_workspace`,
  `test_apply_frontmatter_only_unit_builds_merged_content`,
  `test_apply_frontmatter_only_unit_returns_none_on_malformed_source`,
  `test_apply_frontmatter_only_unit_handles_empty_user_body`.
  Suite totale: 546 passed / 9 skipped (baseline pre-sessione: 539).

### Planned

- Aggiornare `min_engine_version` in `scf-master-codecrafter`
  e `scf-pycode-crafter` a `"3.2.0"` nei rispettivi
  `package-manifest.json` (task post-merge, repo separati).

---

## [3.3.0] - 2026-05-09

### Added — Pending Resolution v1.0 (2026-05-09)

- `spark/boot/tools_plugins.py` — i tool legacy `scf_list_plugins` e
  `scf_install_plugin` ora espongono in tutti i payload JSON i campi
  `removal_target_version: "3.4.0"` (due minor release dopo l'engine
  3.2.0 corrente) e `migrate_to` con il nome esplicito del tool
  store-based equivalente (`scf_plugin_list` / `scf_plugin_install`).
  Aggiunte le costanti modulo `_LEGACY_REMOVAL_TARGET_VERSION` e
  `_LEGACY_MIGRATION_MAP`. Risolve SP-1 (R3 del report
  `SPARK-REPORT-DualUniverse-Consolidation-v1.0.md`).
- `packages/spark-base/.github/agents/spark-guide.agent.md` — aggiunta
  sezione "Architettura — pacchetti interni vs plugin workspace" con
  cross-reference a `spark-assistant` come fonte canonica del dettaglio
  operativo. Bump frontmatter `version: 1.0.0 → 1.1.0`. Risolve SP-2
  (R4 — narrativa dual-universe coerente nel layer di orientamento).
- `tests/test_no_orphan_imports.py` — test di regressione che importa
  ricorsivamente tutti i moduli `spark.*` (62 moduli oggi) per
  intercettare in CI/local la classe di anomalie tipo ANOMALIA-NEW
  (import path errato silenziato a runtime). Risolve SP-3 (R5).
- `CONTRIBUTING.md` — nuovo file con la procedura "Rinomina agenti
  SCF" (6 step: manifest, file fisico, test, CHANGELOG, doc cross-ref,
  validazione suite). Risolve SP-5.
- `docs/reports/SPARK-REPORT-PendingResolution-v1.0.md` — report di
  risoluzione dei 5 sospesi pre-merge.
- `README.md` — aggiunta nota sui tool legacy `scf_list_plugins` /
  `scf_install_plugin` con `removal_target_version` e `migrate_to`.
  Aggiunta sezione "Architettura — Pacchetti interni vs Plugin Workspace"
  che spiega la distinzione Universo A (mcp_only) / Universo B (plugin
  workspace) e cross-reference a `spark-assistant` come fonte canonica.

### Fixed — Live Fixture Fix v1.0 (2026-05-09)

- `tests/test_integration_live.py` — fixture `tmp_workspace`: aggiunto
  blocco di inizializzazione di `runtime/orchestrator-state.json` con
  `github_write_authorized: true`. Senza questo file tutti e 4 i live test
  erano bloccati dal gate `_is_github_write_authorized_v3()` prima ancora di
  toccare la rete (Bug A).
- `spark/core/utils.py` — aggiunta helper `_normalize_dependency_ids()` che
  gestisce dipendenze in formato schema 3.1 (`{"id": ..., "min_version": ...}`)
  oltre al formato stringa legacy. Risolve il `missing_dependencies` errato
  per pacchetti con dipendenze object-typed (Bug B).
- `spark/boot/install_helpers.py` — `_get_package_install_context()` ora usa
  `_normalize_dependency_ids()` al posto di `_normalize_string_list()` per il
  campo `dependencies` del manifest (Bug B).
- `tests/test_integration_live.py` — `test_plan_install_detects_untracked_conflict_and_abort_preserves_workspace`:
  aggiornato `conflict_rel` da `".github/agents/Agent-Code.md"` (nome
  pre-rename) a `".github/agents/code-Agent-Code.md"` (nome attuale dopo
  razionalizzazione prefisso `code-`) (Bug D).
- `tests/test_integration_live.py` — `test_install_clean_master_package_creates_manifest_and_replan_is_clean`:
  le entry manifest `__store__/{pkg}` sono sentinelle interne v3 store e non
  corrispondono a file fisici nel workspace; filtrate dall'assertion sui file
  tracciati (Bug C).
- `tests/test_integration_live.py` — `test_install_clean_master_package_creates_manifest_and_replan_is_clean`:
  la replan assertion ora verifica che tutti i file installati
  (workspace_files + plugin_files) siano classificati come
  `update_tracked_clean` / `extend_section`, ignorando le voci store-only
  (changelogs, skills, prompts) presenti in `files` ma non nel workspace
  fisico (Bug C / replan assertion).
- `spark/boot/tools_packages_install.py` — aggiunto pre-check conflitti per
  `plugin_files` nel branch v3 prima dell'avvio del download nello store. Se
  `conflict_mode="abort"` e uno o più `plugin_files` corrispondono a file
  non tracciati già presenti nel workspace, `scf_install_package` restituisce
  `success=False` senza toccare store né manifest (Bug E).

### Added — Merge Readiness Step 5 (2026-05-09)

- `tests/test_onboarding_manager.py` — test E2E minimal-mock
  `test_run_onboarding_e2e_minimal_mock_virgin_workspace` (R2): verifica
  `run_onboarding()` end-to-end su workspace vergine con `auto_install: true`,
  controlla `status == "completed"`, `packages_installed == ["spark-base"]` e
  idempotenza post-install (`is_first_run() is False` dopo l'esecuzione).
  Porta il totale dei test `OnboardingManager` a 18.

### Changed — Merge Readiness Step 5 (2026-05-09)

- `packages/spark-base/.github/agents/spark-assistant.agent.md` — bump
  versione da `1.2.0` a `1.3.0` (minor: la sezione "Architettura — pacchetti
  interni vs plugin workspace" introduce regole comportamentali per l'agente,
  non solo narrativa descrittiva. SemVer minor corretto).
- `spark/boot/tools_plugins.py` — aggiunto commento
  `# TODO: centralizzare in spark/boot/_legacy_markers.py se altri tool
  diventano legacy in moduli diversi` sopra la costante
  `_LEGACY_DEPRECATION_NOTICE` (D2: lasciata in loco, oggi 2 tool legacy
  in un solo modulo — estrazione non giustificata).
- `docs/reports/rapporto perplexity - audit-system-state-v1.0.md` — aggiunta
  nota inline su V2: classificazione rivista da CRITICO a MEDIO nel report
  `SPARK-REPORT-DualUniverse-Consolidation-v1.0.md` post analisi statica
  entry point FastMCP.

### Added — Dual-Universe Consolidation (audit 2026-05-09)

- `tests/test_onboarding_manager.py` — 17 test unitari per
  `spark.boot.onboarding.OnboardingManager` (gap V6 del rapporto
  `docs/reports/rapporto perplexity - audit-system-state-v1.0.md`):
  copre `is_first_run` (manifest popolato/vuoto, fallback legacy,
  `auto_install: false`, packages list vuota, file corrotto),
  `_install_declared_packages` (no file, `auto_install: false`,
  pacchetto gia installato, install OK / KO / RuntimeError, campo
  `packages` non lista) e `run_onboarding` (status `completed`,
  `partial`, `skipped`).
- `packages/spark-base/.github/agents/spark-assistant.agent.md` — nuova
  sezione "Architettura — pacchetti interni vs plugin workspace" che
  esplicita all'utente finale la distinzione tra Universo A
  (pacchetti `mcp_only` serviti dall'engine) e Universo B (plugin
  esterni installati esplicitamente). Colma il gap narrativo V5.
- `spark/boot/tools_plugins.py` — costante `_LEGACY_DEPRECATION_NOTICE`.
  I tool legacy `scf_list_plugins` e `scf_install_plugin` ora
  espongono `deprecated: true` e `deprecation_notice` in tutti i
  payload JSON di risposta (success ed error). Permette a Copilot di
  preferire automaticamente i tool store-based `scf_plugin_list` /
  `scf_plugin_install`.
- `docs/reports/SPARK-REPORT-DualUniverse-Consolidation-v1.0.md` —
  report di consolidamento dual-universe.

### Fixed — Dual-Universe Consolidation (audit 2026-05-09)

- `spark/boot/onboarding.py` — corretto import errato in
  `OnboardingManager._ensure_store_populated`: `PackageResourceStore`
  vive in `spark.registry.store`, non in `spark.packages.store`.
  L'import errato sollevava `ImportError` silenziosamente ad ogni
  esecuzione, trasformando ogni `run_onboarding()` in
  `status: "partial"` con errore `"No module named
  'spark.packages.store'"`. Anomalia non rilevata dal rapporto
  Perplexity originale, scoperta in fase di test del Modulo 3.

### Added — Dual-Mode Architecture v1.0 (TASK-1..TASK-4)

- `packages/spark-base/package-manifest.json` — `delivery_mode: "mcp_only"`,
  `schema_version: "3.0" → "3.1"`, `workspace_files: []`, `plugin_files: []`.
  I pacchetti built-in sono ora serviti esclusivamente via MCP dallo store
  interno del motore; nessun file viene copiato nel workspace utente.
- `packages/scf-master-codecrafter/package-manifest.json` — `delivery_mode: "mcp_only"`,
  `workspace_files: []`. `plugin_files` resta `[]`.
- `packages/scf-pycode-crafter/package-manifest.json` — `delivery_mode: "mcp_only"`,
  `workspace_files: []`, `plugin_files: []`.
- `spark/plugins/manager.py` — nuovo modulo con `PluginManager`,
  `download_plugin()` e `list_available_plugins()`. Implementa il download
  diretto di plugin nella directory `.github/` senza passare per lo store
  interno del motore. I pacchetti `mcp_only` sono filtrati automaticamente
  dal listing. (TASK-3)
- `spark/plugins/__init__.py` — aggiornato: esporta anche `PluginManager`,
  `download_plugin`, `list_available_plugins` oltre a `PluginManagerFacade`.
- `spark/boot/tools_plugins.py` — aggiunti 2 nuovi tool MCP (TASK-4):
  - `scf_list_plugins()` — elenca i plugin disponibili per download diretto
    (esclude `mcp_only`). Usa `list_available_plugins()` di `manager.py`.
  - `scf_install_plugin(package_id, version, workspace_root, overwrite)` —
    scarica un plugin nel workspace utente tramite `download_plugin()`.
    Nessun tracking nello store; il contatore tool passa da 4 a 6 in questo modulo.
- `README.md` — sezione "Tools Disponibili" aggiornata da 44 a 46 con i
  nuovi tool `scf_list_plugins` e `scf_install_plugin`.

### Changed — Dual-Mode Architecture v1.0

- `spark/plugins/installer.py` — aggiunto guard `delivery_mode == "mcp_only"` in
  `install_from_store()`: i pacchetti con `delivery_mode: "mcp_only"` non scrivono
  mai `workspace_files` nel workspace utente. Aggiunto anche `import logging` e
  `_log` per il nuovo guard. (TASK-2)
- `spark/boot/tools_plugins.py` — docstring aggiornato: "Registers 6 MCP tools"
  (era 4). Aggiunti import `download_plugin`, `list_available_plugins`,
  `RegistryClient` a livello di modulo.

- `spark/boot/tools_packages.py` — nuovo modulo factory per i 15 tool package
  lifecycle e conflict resolution: `scf_list_available_packages`,
  `scf_get_package_info`, `scf_list_installed_packages`, `scf_install_package`,
  `scf_check_updates`, `scf_update_package`, `scf_update_packages`,
  `scf_apply_updates`, `scf_plan_install`, `scf_remove_package`,
  `scf_get_package_changelog`, `scf_resolve_conflict_ai`, `scf_approve_conflict`,
  `scf_reject_conflict`, `scf_finalize_update`. Factory `register_package_tools(engine, mcp, tool_names)`.
- `tests/test_ap1_scf_get_agent_source_warning.py` — 3 test per la divergenza silenziosa
  tra `scf_get_agent` (workspace+store) e `scf_get_agent_resource` (registry-only):
  `test_source_warning_present_for_workspace_only_agent`,
  `test_no_source_warning_for_store_agent`, `test_not_found_returns_error`.

### Changed

- `spark/boot/engine.py` — `register_tools()` ridotto ad assembler puro (5 chiamate
  factory): registra sequenzialmente `register_resource_tools`, `register_override_tools`,
  `register_policy_tools`, `register_package_tools`, `register_bootstrap_tools`.
  Zero tool definiti inline. (Fase D.5 — Deframmentazione engine.py completata.)
- `spark/boot/engine.py` — log contatore tool ora dinamico:
  `_log.info("[SPARK-ENGINE][INFO] Tools registered: %d total", len(tool_names))` —
  rimosso il valore hardcoded precedente (AP.3).
- `spark/boot/sequence.py` — rimosso log hardcoded
  `"Tools registered: 44 total"` dalla fine di `_build_app()` (AP.3).
- `tests/test_engine_coherence.py` — `test_tool_counter_consistency` aggiornato:
  verifica il pattern dinamico `"%d total"` in `engine.py` invece del log
  hardcoded; conta decoratori `@_register_tool(` nei moduli factory (AP.3).

### Fixed

- `spark/boot/tools_resources.py` — `scf_get_agent` ora aggiunge il campo
  `source_warning` quando un agente è trovato nel workspace fisico ma non nel
  registry MCP, segnalando la divergenza senza breaking change (AP.1).
- `tests/test_framework_inventory_resolver.py` — aggiunto test di regressione
  `test_list_agents_cat_b_store_only_after_a4`: documenta che gli agenti Cat.B
  (Agent-Analyze, Agent-Git, Agent-Plan, Agent-Docs) presenti solo nello store
  compaiono in `list_agents()` dopo l'integrazione A.4 con ResourceResolver (AP.2).
- `tests/test_package_installation_policies.py` —
  `test_scf_install_package_allows_reinstall_for_same_package`: sostituita
  l'asserzione sulla versione con una nuova istanza `ManifestManager(github_root)`
  per eliminare la race condition mtime-based cache tra l'istanza pre-install
  e la scrittura del motore (S.1 stabilizzazione).
- `README.md`: corretto link rotto a `SCF-PROJECT-DESIGN.md` — punta ora al percorso
  corretto `docs/archivio/SCF-PROJECT-DESIGN.md` con nota "(archiviato)".
- `README.md`: corretto conteggio prompt bootstrap da "9" a "13" (`scf-*.prompt.md`
  copiati da `packages/spark-base/package-manifest.json`).

---

## [3.2.0] - 2026-05-06

### Added

- `scf_bootstrap_workspace` — nuovi parametri `force: bool = False` e
  `dry_run: bool = False` (v3.1 extension). Con `force=True` sovrascrive anche
  i file modificati dall'utente. Con `dry_run=True` simula il bootstrap senza
  scrivere file.
- `scf_bootstrap_workspace` — nuovi campi nella response: `files_copied`
  (percorsi scritti o che sarebbero stati scritti in dry_run), `files_skipped`
  (già presenti e invariati), `files_protected` (modificati dall'utente, richiedono
  force=True), `sentinel_present` (bool), `message` (stringa descrittiva).
  Tutti i return path esistenti mantengono backward compatibility (`files_written`,
  `preserved`, `note`).
- `tests/test_bootstrap_workspace_extended.py` — +7 test: `force`/`dry_run`,
  `files_skipped`/`files_protected`, presenza nuovi campi v3.1 in tutti i path di
  successo. Suite: 306 → 313 passed.

- `WorkspaceWriteGateway` in `spark/manifest/gateway.py` — gateway centralizzato
  per scritture su `<workspace>/.github/**`. Espone `write()`, `write_bytes()`,
  `delete()` che aggiornano atomicamente il manifest dopo ogni write.
- `tests/test_workspace_gateway.py` — suite test gateway (TestGatewayWrite,
  TestGatewayWriteBytes, TestGatewayDelete, TestGatewayIdempotency,
  TestPhase6GatewayIntegration).
- `spark/boot/engine.py` — helper modulo-level `_gateway_write_text` e
  `_gateway_write_bytes` (Fase 4-BIS). Incapsulano l'istanziazione del
  gateway e la scrittura tracciata; usati dai forward write di
  `scf_install_package`, `scf_approve_conflict`, `scf_reject_conflict` e
  `scf_bootstrap_workspace`.
- `tests/test_bootstrap_workspace_extended.py` — +3 test per
  `scf_bootstrap_workspace` (commit `64b436f`): coprono INVARIANTE-4
  cross-owner preserve-senza-write, flusso esteso riattivato e sentinella
  `spark-assistant` come ultimo asset bootstrap. Suite: 296 → 299 passed.
- `tests/test_boot_sequence.py` — test mirato sul boot sequence che verifica
  il trigger di auto-bootstrap al primo avvio del server quando il workspace
  utente è risolto correttamente.

### Changed

- `_apply_phase6_assets` in `spark/assets/phase6.py` — parametri opzionali
  `gateway` e `engine_version`. Se il gateway è fornito, `AGENTS.md`,
  `AGENTS-{pkg}.md` e `project-profile.md` sono scritti via gateway
  (owner `"spark-engine"`) invece di scrittura diretta. `.clinerules` resta
  scrittura diretta (file a root workspace, non sotto `.github/`).
- `SparkFrameworkEngine` in `spark/boot/engine.py` — `WorkspaceWriteGateway`
  importato da `spark.manifest` e iniettato ai 3 callsite di
  `_apply_phase6_assets` (`_install_package_v3`, `_remove_package_v3`,
  `scf_bootstrap_workspace`).
- `spark-framework-engine.py` — rimossi import stdlib inutilizzati e blocchi
  di commenti storici (`# XYZ moved to…`). Entry point ridotto da 376 a 194
  righe. Soli import effettivamente usati: `logging`, `sys`, `pathlib.Path`.
- `docs/REFACTORING-DESIGN.md` — Sezione 4 aggiornata: `workspace/policy.py`
  → `update_policy.py`, aggiunto `manifest/gateway.py`, rimosso `[validation.py]`
  come "da creare". Sezione 7: aggiunta Fase 5 con deviazione INVARIANTE-4 documentata.
  Aggiunta Sezione Fase 4-BIS che documenta la chiusura della deviazione
  INVARIANTE-4 per i forward write tracciati nel manifest.
- `docs/todo.md` — ciclo refactoring COMPLETATO; Fase 4-BIS aggiunta alla
  tabella fasi successive; sessione attiva aggiornata da "Fase 5 ATTIVA" a
  "Ciclo di refactoring modulare SPARK — COMPLETATO".
- `docs/coding plans/FASE5-PIANO-TECNICO.md` — tabella Chiusura: SHA reali
  sostituiscono i placeholder "da committare"; Verdetto Finale aggiornato a
  "GATE: CHIUSO — C1–C5 tutti implementati"; deviazione gateway bypass
  marcata RISOLTO in Fase 4-BIS.
- `docs/reports/FASE5-CHIUSURA-REPORT.md` — C5 aggiornato da "⏭ RINVIATA"
  a "✅ APPLICATA in Fase 4-BIS (commit a2a32ac)"; sezione deviazioni
  riscritta con dettagli implementazione; contratti soddisfatti 4/5 → 5/5;
  prossimo passo aggiornato: ciclo completamente certificato.
- `spark/boot/engine.py` — Fase 4-BIS: 11 callsites di scrittura su
  `workspace/.github/**` instradate attraverso `WorkspaceWriteGateway`
  via i nuovi helper `_gateway_write_text`/`_gateway_write_bytes`.
  Coperti `scf_install_package` (8 punti: merge_sections, extend_section,
  diff3 clean, diff3 conflict, replace, auto-approve, auto-marker),
  `scf_approve_conflict`, `scf_reject_conflict` e `scf_bootstrap_workspace`
  (2 path: bootstrap legacy + bootstrap nuovo). La cross-owner protection
  in bootstrap viene preservata: file già di proprietà di altro pacchetto
  vengono scritti direttamente senza upsert manifest.
- `spark/workspace/locator.py` — `WorkspaceLocator.resolve()` ora applica una
  precedenza esplicita per `--workspace`, `ENGINE_WORKSPACE` e
  `WORKSPACE_FOLDER`, così il bootstrap del primo avvio può puntare al
  workspace utente anche quando il server è lanciato da una directory diversa.
- `spark/workspace/locator.py` — `_discover_from_cwd()` ignora esplicitamente
  `engine_root` come candidato workspace e `resolve()` emette un warning di
  degrado quando il processo viene avviato dalla directory engine senza un
  workspace utente esplicito.
- `spark/boot/sequence.py` — `_build_app()` ora invoca un hook di
  auto-bootstrap minimo dopo `register_tools()`, materializzando il Layer 0
  nel workspace utente quando mancano i file essenziali (`spark-assistant`,
  `spark-guide`, `AGENTS.md`, `copilot-instructions.md`, `project-profile.md`).
- `mcp-config-example.json` — aggiunta `WORKSPACE_FOLDER=${workspaceFolder}`
  al template stdio, per allineare il server MCP alla cartella aperta in VS Code.

### Performance (OPT-1 — OPT-8)

- **OPT-1** `ManifestManager.load()` (`spark/manifest/manifest.py`) — cache
  in-memory validata con `st_mtime`. Elimina reletture ridondanti del JSON
  durante batch di install/update sullo stesso file manifest.
- **OPT-2** `_install_workspace_files_v3` (`spark/boot/lifecycle.py`) —
  accumulo `pending_writes` pre-loop; scrittura fisica e `upsert_many()` in
  un'unica flush dopo il loop. Elimina N round-trip al manifest per file.
- **OPT-3** `_install_package_v3_into_store` (`spark/packages/lifecycle.py`) —
  download parallelo dei file pacchetto via `ThreadPoolExecutor(max_workers=8)`
  al posto del loop seriale `fetch_raw_file`.
- **OPT-4** `WorkspaceWriteGateway.write_many()` (`spark/manifest/gateway.py`) —
  nuovo metodo batch: N scritture fisiche + singola `upsert_many()` al manifest.
- **OPT-5** SHA-sentinel skip in `_install_workspace_files_v3` — file con SHA
  invariato rispetto allo snapshot pre-loop non vengono riscritti né
  re-upsertati nel manifest.
- **OPT-6** `_v3_repopulate_registry` (`spark/boot/lifecycle.py`) — parametro
  opzionale `freshly_installed: dict | None`; se fornito evita rilettura da
  disco del manifest del pacchetto appena installato.
- **OPT-7** `ManifestManager._build_entry()` — parametro opzionale
  `sha256_hint: str | None`; se fornito usa l'hint invece di ricalcolare SHA
  sul file destinazione.
- **OPT-8** `_apply_phase6_assets` (`spark/assets/phase6.py`) — accumulo
  `pending_gateway_writes` per `AGENTS.md`, `AGENTS-{pkg}.md` e
  `project-profile.md`; flush unica via `gateway.write_many()`.

### Fixed

- `tests/test_engine_coherence.py` — regex `r"## \[(\d[^\]]+)\]"` sostituisce
  `r"## \[([^\]]+)\]"` per saltare la sezione `[Unreleased]` nel CHANGELOG
  e rilevare correttamente la versione più recente rilasciata (CORREZIONE [1]).
- `spark/boot/engine.py` — `scf_bootstrap_workspace` (commit `64b436f`):
  tre correzioni al bootstrap tool 28: (1) INVARIANTE-4 — scritture dirette
  cross-owner convertite in preserve-senza-write via gateway, eliminando la
  violazione di ownership per file owned da altri pacchetti; (2) flusso
  esteso riattivato rimuovendo un `return` anticipato che rendeva dead code
  l'intero blocco post-sentinella; (3) sentinella
  `agents/spark-assistant.agent.md` spostata come ultimo elemento di
  `bootstrap_targets`, garantendo ordine di scrittura deterministico.
- `spark/boot/engine.py` — il bootstrap minimo usa ora come sorgente primaria
  il bundle locale `packages/spark-base/.github`, copia anche le istruzioni di
  base, tutti i prompt `.prompt.md`, `AGENTS.md`, `copilot-instructions.md` e
  `project-profile.md`, e ripara un bootstrap parziale anche quando la
  sentinella è già tracciata ma mancano asset root fondamentali.

---

## [3.1.0] - 2026-04-28

### Added

- **v3-aware package lifecycle (Fase 9).** I tool `scf_install_package`,
  `scf_update_package` e `scf_remove_package` ora rilevano i pacchetti
  v3 (con `min_engine_version >= 3.0.0`) e li installano nel store
  centralizzato `engine_dir/packages/{pkg_id}/.github/` invece che in
  `workspace/.github/`. La install registra una entry sentinella
  `installation_mode: "v3_store"` nel manifest workspace e popola
  `McpResourceRegistry` live; remove deregistra le URI e cancella lo
  store ma preserva sempre gli override workspace; update riusa la
  install idempotente e segnala via `override_blocked` quali risorse
  hanno un override workspace attivo.
- Nuovi helper interni `_is_v3_package()`, `_install_package_v3_into_store()`,
  `_remove_package_v3_from_store()`, `_list_orphan_overrides_for_package()`,
  `_v3_overrides_blocking_update()`, `McpResourceRegistry.unregister()` e
  `McpResourceRegistry.unregister_package()`.
- Nuova suite test `tests/test_package_lifecycle_v3.py` (10 test) che
  copre install/update/remove v3 + retrocompat v2.

### Changed

- `ManifestManager.verify_integrity()` e `ManifestManager.remove_package()`
  ora ignorano le entry sentinella v3 (`installation_mode == "v3_store"`),
  evitando lookup falliti su path workspace.
- I pacchetti legacy con `min_engine_version < 3.0.0` continuano a usare
  il flusso v2 (copia file in workspace) con un warning su stderr.

---

## [3.0.0] - 2026-04-28

### Added

- **Architettura v3.0 — Centralized Package Store + MCP Resource Registry.**
  I pacchetti SCF non vengono più copiati nel workspace utente: vivono in
  `engine_dir/packages/{pkg_id}/.github/` e sono esposti via MCP resources con
  override workspace prioritari (`workspace/.github/overrides/{type}/`).
- `WorkspaceLocator` per la risoluzione esplicita del workspace target via
  flag CLI `--workspace`, con cache engine in `engine_dir/.scf-cache/` e
  override resolver per agenti, prompt, skill e instruction.
- `RegistryClient` ora accetta `cache_path` esplicito (default retrocompatibile
  in `github_root/.scf-registry-cache.json`) per supportare cache engine-side.
- `MigrationPlanner` e tool `scf_migrate_workspace(dry_run=...)` per la
  migrazione one-shot dei workspace v2.x verso v3.0 (rimuove file copiati
  da `.github/agents/`, `prompts/`, `skills/`, registra override esistenti).
- `PackageResourceStore` e `McpResourceRegistry` per la risoluzione
  `(package_id, type, name) → engine_path` con priorità override.
- Bootstrap v3 (Fase 6): `_apply_phase6_assets` genera dinamicamente
  `.github/AGENTS.md` (safe-merge tra marker `SCF:BEGIN:agents-index`),
  `AGENTS-{plugin}.md` per pacchetto, template `project-profile.md`,
  `.clinerules` (solo se assente).
- ManifestManager schema **3.0**: `.scf-manifest.json` ora include un campo
  `overrides[]` ordinato e derivato dalle entry con `override_type`. Lettura
  retrocompatibile con schema 1.0/2.0/2.1.
- Agente engine `spark-welcome` per onboarding interattivo del workspace.
- 26 nuovi test automatici: `tests/test_phase6_bootstrap_assets.py` (16) e
  `tests/test_manifest_manager.py` (10).

### Changed

- `ENGINE_VERSION` bump a `3.0.0` (breaking: nuova architettura risorse).
- `_MANIFEST_SCHEMA_VERSION` aggiornato da `"1.0"` a `"3.0"`.
- I pacchetti `spark-base`, `scf-master-codecrafter` e `scf-pycode-crafter`
  richiedono ora `min_engine_version: 3.0.0`.

### Deprecated

- Copia fisica di `agents/`, `prompts/`, `skills/`, `instructions/` nel
  workspace utente. I client devono leggere via MCP resources.
- Schema `.scf-manifest.json` 1.0/2.x: ancora letti, ma riscritti in
  schema 3.0 alla prima `save()`.

### Migration

- Workspace v2.x: vedi `docs/MIGRATION-GUIDE-v3.md` per la procedura
  `scf_migrate_workspace`.
- Smoke test manuali Copilot: `docs/SMOKE-TEST-COPILOT-v3.md` (DEFERRED,
  da eseguire dallo sviluppatore prima del rilascio pubblico).

### Notes

- Suite test: **272 passed** (28 aprile 2026, escluso integration-live).
- Nessun comando git eseguito dall'engine: il tag `v3.0.0` va creato
  manualmente (vedi sezione Release nel piano).

---

## [2.4.0] - 2026-04-22

### Added

- Nuova classe `EngineInventory` che legge skill e instruction dal `.github/` del motore (percorso derivato da `Path(__file__).parent / ".github"`), indipendente dal workspace utente.
- Nuove resource MCP per consumare gli asset universali hostati dal motore: `engine-skills://list`, `engine-skills://{name}`, `engine-instructions://list`, `engine-instructions://{name}`.
- 18 skill universali copiate in `.github/skills/` del motore (`accessibility-output`, `changelog-entry`, `conventional-commit`, `document-template`, `error-recovery`, `file-deletion-guard`, `framework-guard`, `framework-index`, `framework-query`, `framework-scope-guard`, `git-execution`, `personality`, `rollback-procedure`, `semantic-gate`, `semver-bump`, `style-setup`, `task-scope-guard`, `validate-accessibility`, `verbosity`) + 2 dal layer master (`clean-architecture`, `docs-manager`).
- 7 instruction universali copiate in `.github/instructions/` del motore (`framework-guard`, `git-policy`, `model-policy`, `personality`, `spark-assistant-guide`, `verbosity`, `workflow-standard`).
- Schema manifest workspace: `2.1` aggiunto a `_SUPPORTED_MANIFEST_SCHEMA_VERSIONS` per accettare entry con il campo opzionale `stub: true` (infrastruttura pronta; wiring in install/update rinviato a release successiva).
- `ManifestManager._build_entry` e `ManifestManager.upsert_many` accettano parametro opzionale `stub` / `stub_files` additivo e retrocompatibile.

### Notes

- Nessuna modifica al comportamento delle resource esistenti `skills://` e `instructions://` (continuano a leggere dal workspace utente). I due namespace `engine-*://` sono additivi e non introducono shadowing.
- `_MANIFEST_SCHEMA_VERSION` resta a `"1.0"` per retrocompatibilita` con i test e con i client esistenti; il valore `2.1` e` accettato in lettura ma non ancora emesso come default di scrittura.
- Questa release prepara il terreno per `spark-base@1.3.0` e `scf-master-codecrafter@2.2.0` che spediranno stub al posto dei file fisici delegati.

---

## [2.3.2] - 2026-04-21

### Changed

- `.github/copilot-instructions.md` del motore convertito da file single-owner a file condiviso canonico con marker `<!-- SCF:BEGIN:{package}@{version} -->` / `<!-- SCF:END:{package} -->`, con sezioni per `spark-framework-engine@2.3.1`, `spark-base@1.2.0`, `scf-master-codecrafter@2.1.0` e `scf-pycode-crafter@2.0.1`, ordinate per `scf_merge_priority` (0 → 10 → 20 → 30).
- File `.github/` del motore classificati esplicitamente per ownership: file nativi engine taggati con `scf_owner: "spark-framework-engine"`; 10 file shadow di `spark-base` (`spark-guide.agent.md` e i 9 prompt `scf-*.prompt.md`) riallineati al contenuto del pacchetto sorgente con `scf_owner: "spark-base"`.
- README riallineato: la sezione `## Migrazione Da Workspace Pre-Ownership` e' stata spostata fuori dal blocco codice di `## Tools Disponibili (35)` per ripristinare una struttura markdown coerente con i contenuti runtime documentati.

### Notes

- Nessuna modifica al codice Python del motore. Release di governance `.github/` e normalizzazione ownership degli asset installati.

---

## [2.3.1] - 2026-04-19

### Fixed

- `scf_verify_workspace()` non segnala piu' come `duplicate_owners` i file condivisi intenzionalmente tra piu' pacchetti quando tutte le entry del manifest usano `scf_merge_strategy: merge_sections`.
- Il manifest runtime riallinea ora hash e merge strategy delle entry condivise dopo install, update, finalize e remove di file `merge_sections`, evitando falsi `modified` sui package owner residui.

---

## [2.3.0] - 2026-04-19

### Added

- `scf_get_update_policy()` e `scf_set_update_policy()` per leggere e persistare la policy update del workspace in `.github/runtime/spark-user-prefs.json`.
- `diff_summary`, `authorization_required`, `github_write_authorized` e `backup_path` nei payload pubblici dei flussi install/update quando entra in gioco il sistema di policy del workspace.
- Estensione di `scf_bootstrap_workspace(..., update_mode="")` con handshake iniziale di policy, preview diff per `spark-base` e gate esplicito per le scritture protette in `.github/`.

### Changed

- `scf_install_package(package_id, conflict_mode, update_mode)` e `scf_update_package(package_id, conflict_mode, update_mode)` risolvono ora il comportamento package-level tramite `mode_per_package`, `mode_per_file_role` e `default_mode`, mantenendo invariato il flusso legacy se il workspace non ha ancora una policy esplicita.
- I file `merge_sections` usano ora in scrittura `_scf_section_merge()` come path canonico, mentre i file `user_protected` continuano a essere delegati senza fetch o overwrite impliciti.
- README, copilot instructions, skill e prompt del motore descrivono ora il flusso ownership-aware in 6 step, le modalita `integrative` / `replace` / `conservative` / `selective` e il ruolo del bootstrap esteso.

### Notes

- Release minor: consolida le feature OWN-B, OWN-C, OWN-D, OWN-E e OWN-F in una versione documentata e pronta per il rollout, senza introdurre breaking change sui tool legacy.

---

## [2.2.1] - 2026-04-17

### Fixed
- Rimossa chiave legacy `engine_min_version` dall'output di `_plan_package_updates`.
  La chiave canonica `min_engine_version` è l'unico output corretto per i tool
  `scf_check_updates` e `scf_update_packages`.

---

## [2.2.0] - 2026-04-17

### Removed
- `scf_get_package_info`: rimosso il campo legacy `engine_min_version` dall'output.
  Il campo canonico è `min_engine_version`. Breaking change dell'output del tool.
  La funzione interna `_get_registry_min_engine_version` mantiene ancora il fallback
  in lettura del campo legacy per compatibilità con cache locali non ancora aggiornate.

---

## [2.1.3] — 2026-04-17

### Changed

- Il registry usa ora `min_engine_version` come campo canonico anche nel workflow di sincronizzazione automatica, mantenendo nel motore la compatibilita' in lettura del legacy `engine_min_version`.

### Fixed

- `MergeEngine` calcola ora `start_line` e `end_line` dei conflitti sulla base del contesto realmente condiviso da `base`, `ours` e `theirs`, evitando coordinate sfalsate quando il testo base diverge.

---

## [2.1.2] — 2026-04-17

### Changed

- `scf_apply_updates(package_id | None, conflict_mode)` inoltra ora davvero il `conflict_mode` al batch update invece di forzare sempre `replace`.
- `scf_bootstrap_workspace(install_base=True, conflict_mode)` inoltra il mode scelto all'installazione di `spark-base` durante il bootstrap MCP.
- `spark-init.py` chiede ora una scelta esplicita `replace` / `preserve` / `integrate` quando trova file gia presenti nel primo bootstrap standalone di `spark-base`.

### Fixed

- `conflict_mode="replace"` sovrascrive ora anche i file tracciati e modificati che prima cadevano sempre sul ramo di preservazione implicita.
- Allineata la documentazione runtime e i prompt operativi al nuovo comportamento di bootstrap e update batch.

---

## [2.1.1] — 2026-04-15

### Changed

- `scf_bootstrap_workspace(install_base=True)` puo' ora completare il bootstrap MCP e tentare subito l'installazione gestita di `spark-base`, saltando il passo se il pacchetto e gia installato.
- `spark-init.py` sostituisce il bootstrap hard-coded con un installer embedded di `spark-base`, aggiornando `.github/.scf-manifest.json` e riducendo lo stdout al solo riepilogo finale.
- README allineato al bootstrap embedded di `spark-init.py`, al manifest runtime e al nuovo riepilogo in 3 righe.

### Fixed

- Aggiornata la cache locale del registry bundlata con il motore al formato `2.0` e all'inventario pacchetti corrente.
- Allineato `scf-pycode-crafter` a `engine_min_version: 2.1.0` nel registry per riflettere la dipendenza effettiva dalla chain `spark-base -> scf-master-codecrafter -> scf-pycode-crafter`.

### Notes

- Il registry pubblico e il manifest remoto di `spark-base` risultano ancora disallineati sulla versione pubblicata; `spark-init.py` usa il manifest remoto reale e segnala la discrepanza su `stderr`.

---

## [2.1.0] — 2026-04-15

### Added

- Adozione dei file bootstrap da parte dei pacchetti installabili: `spark-base` puo' ora rilevare e assorbire in modo sicuro `spark-guide.agent.md` gia' tracciato da `scf-engine-bootstrap`.

### Changed

- `scf_install_package(package_id, conflict_mode)` rimuove l'ownership bootstrap superata quando `spark-base` installa file gia' bootstrap-pati e puliti.
- `scf_bootstrap_workspace()` evita di ri-registrare nel manifest bootstrap file gia' posseduti da un pacchetto SCF non-bootstrap.

### Notes

- Versione minor per supportare la promozione di `spark-guide` dentro `spark-base` senza conflitti di ownership nei workspace gia' inizializzati.

---

## [2.0.0] — 2026-04-14

### Added

- Sistema di merge a 3 vie per file markdown: snapshot BASE, versione utente e nuova versione pacchetto vengono combinati da `MergeEngine` con percorsi `manual`, `auto` e `assisted`.
- `conflict_mode: "manual"` — apre una sessione stateful e scrive i marker di conflitto nel file finche' l'utente non li risolve e chiude la sessione con `scf_finalize_update`.
- `conflict_mode: "auto"` — tenta una risoluzione best-effort deterministica tramite `scf_resolve_conflict_ai`; se il caso non e sicuro o i validator falliscono, degrada esplicitamente a `manual`.
- `conflict_mode: "assisted"` — apre una sessione stateful, conserva i marker sul file e permette di proporre, approvare o rifiutare una risoluzione per singolo conflitto.
- `scf_finalize_update(session_id)` — finalizza una sessione di merge chiudendola e applicando le decisioni confermate al manifest e ai file del workspace.
- `scf_resolve_conflict_ai(session_id, conflict_id)` — propone automaticamente una risoluzione conservativa per un singolo conflitto in una sessione attiva.
- `scf_approve_conflict(session_id, conflict_id)` — approva la risoluzione proposta per un conflitto, marcandolo come risolto nella sessione.
- `scf_reject_conflict(session_id, conflict_id)` — rifiuta la risoluzione proposta per un conflitto, mantenendo la versione utente corrente.
- Validator post-merge: verifica strutturale, completezza heading e coerenza del blocco `tools:` per i file `.agent.md`.
- Policy multi-owner `extend` e `delegate`: gestione di file condivisi tra più pacchetti con regole di ownership esplicite e risoluzione conflitti cross-package.

### Changed

- `scf_install_package(package_id, conflict_mode)` supporta ora i nuovi valori `"manual"`, `"auto"` e `"assisted"` in aggiunta ai precedenti `"abort"` e `"replace"`. Il default rimane `"abort"`.
- `scf_plan_install(package_id)` restituisce ora anche l'anteprima del piano di merge quando il `conflict_mode` richiesto e un merge mode.
- `scf_update_package(package_id, conflict_mode)` propaga il `conflict_mode` alla pipeline di merge durante l'aggiornamento del pacchetto.
- `ManifestManager` permette ora ownership multiple sullo stesso file quando il package differisce, abilitando il modello multi-owner con policy per-file.
- `ENGINE_VERSION` aggiornato a `2.0.0`.

### Notes

- Versione major per cambio architetturale: introduzione `MergeEngine`, sessioni stateful e policy multi-owner rappresentano un'estensione dell'interfaccia MCP non retrocompatibile con motori `< 2.0.0` per i nuovi `conflict_mode`.
- `scf_cleanup_sessions` resta helper interno e non e esposto come tool MCP pubblico.
- Il numero totale di tool registrati passa da 29 a 33.

---

## [1.9.0] — 2026-04-13

### Added

- `scf_plan_install(package_id)` — dry-run tool per classificare i target di installazione prima di qualsiasi scrittura e mostrare write plan, preserve plan e conflict plan.

### Changed

- `scf_install_package(package_id, conflict_mode="abort")` blocca di default i conflitti su file esistenti non tracciati e richiede un opt-in esplicito `replace` per sovrascriverli.
- `scf_apply_updates()` esegue ora un preflight su tutti i package target prima della prima scrittura del batch, fermandosi se rileva conflitti irrisolti.
- `scf_update_package(package_id)` propaga i conflitti di preflight restituiti dal flusso di update.
- `spark-guide.agent.md` torna coerente con i tool realmente dichiarati nel frontmatter.

### Fixed

- Corretto il rischio di overwrite silenzioso su file `.github/` pre-esistenti ma non tracciati dal manifest durante installazione e update.
- Corretta la documentazione del registry: il manifest consumer canonico usa `entries[]`, non `installed_packages[]`.
- Allineata la documentazione del bootstrap MCP al set asset realmente copiato da `scf_bootstrap_workspace()`.

---

## [1.8.2] — 2026-04-12

### Added

- `spark-assistant v1.0.0` — agente utente finale per onboarding, gestione pacchetti e diagnostica workspace. Sostituisce il placeholder precedente.
- `spark-guide v1.0.0` — agente di orientamento user-facing nel repo engine; interpreta richieste in linguaggio naturale e instrada le operazioni concrete verso `spark-assistant` o `spark-engine-maintainer`.

### Changed

- `spark-init.py` include ora anche `spark-engine-maintainer.agent.md` tra gli asset bootstrap copiati nel workspace utente.
- `ENGINE_VERSION` aggiornato a `1.8.2`.

---

## [1.8.1] — 2026-04-12

### Changed

- `WorkspaceLocator` usa ora una cascata piu robusta: `WORKSPACE_FOLDER` valido, marker locali del workspace (`.vscode/settings.json`, `.vscode/mcp.json`, `*.code-workspace`), discovery SCF sotto `.github/`, quindi fallback finale su `cwd`.

### Fixed

- Il motore non accetta piu in modo cieco il path della home utente come workspace quando `WORKSPACE_FOLDER` manca o viene risolto in modo errato senza marker locali SPARK.
- Ridotte le risoluzioni errate del workspace causate da merge parziali della configurazione MCP tra livello globale e livello workspace.

### Notes

- Il fix mantiene compatibile il bootstrap di workspace non inizializzati: un `WORKSPACE_FOLDER` esplicito e valido continua a essere accettato anche se `.github/` non esiste ancora.

---

## [1.8.0] — 2026-04-12

### Added

- `spark-assistant.agent.md`: nuovo agente bootstrap per l'utente finale orientato a catalogo, installazione, update e diagnostica base dei pacchetti SCF.
- `spark-assistant-guide.instructions.md`: instruction dedicata al comportamento operativo dell'assistente bootstrap.
- `scf-package-management` skill: guida riutilizzabile per il ciclo install/update/remove/verify dei pacchetti SCF.
- `spark-init.py`: `_update_vscode_settings()` crea o aggiorna `.vscode/settings.json` scrivendo solo la chiave `mcp.servers.sparkFrameworkEngine`; JSON corrotto loggato su stderr e ricreato.
- `spark-init.py`: `_bootstrap_github_files()` copia `agents/spark-assistant.agent.md`, `instructions/spark-assistant-guide.instructions.md` e tutti i `prompts/scf-*.prompt.md` dal repo engine al workspace utente con idempotenza SHA-256.
- `spark-init.py`: `main()` produce ora su stdout un riepilogo ordinato (workspace, settings, ogni file bootstrap, modalità e cartella); tutto il logging intermedio è su stderr nel formato `[SPARK-INIT][LEVEL]`.

### Changed

- `scf_bootstrap_workspace()` ora copia l'agente `spark-assistant.agent.md` e `spark-assistant-guide.instructions.md` dal repo engine al workspace utente.
- `ENGINE_VERSION` aggiornato a `1.8.0`.

### Notes

- Il bootstrap resta idempotente e, se trova un workspace gia bootstrap-pato in modo parziale, completa solo gli asset mancanti senza sovrascrivere file utente.

---

## [1.7.0] — 2026-04-12

### Added

- `scf_bootstrap_workspace()` tool: copia i prompt base SPARK e l'agente assistant dal repo engine alla cartella `.github/` del workspace utente senza usare il manifest dei pacchetti.

### Changed

- Conteggio tool aggiornato da 27 a 28.
- `ENGINE_VERSION` aggiornato a `1.7.0`.

### Notes

- Il bootstrap usa solo I/O locale, preserva i file gia presenti con contenuto diverso e suggerisce `/scf-list-available` come passo successivo.

---

## [1.6.0] — 2026-04-11

### Added

- `scf_check_updates()` tool: restituisce solo i pacchetti installati che hanno un aggiornamento disponibile.
- `scf_update_package(package_id)` tool: aggiorna un singolo pacchetto installato preservando i file modificati dall'utente.

### Changed

- Conteggio tool aggiornato da 25 a 27.
- `ENGINE_VERSION` aggiornato a `1.6.0`.

### Notes

- `scf_update_package(package_id)` riusa il planner dependency-aware e la logica di installazione esistenti, senza introdurre nuovi modelli dati.

---

## [1.5.1] — 2026-04-10

### Changed

- `scf_update_packages()` ora restituisce anche un piano di update ordinato per dipendenze e gli eventuali blocchi operativi.
- `scf_apply_updates()` ora usa il piano dependency-aware invece di applicare aggiornamenti in ordine lineare.
- `registry-sync-gateway.yml` accetta anche `stable` come status valido del registry.

### Fixed

- Allineata la documentazione pubblica del motore al conteggio reale delle resource e al flusso di update.

### Notes

- Nessun nuovo tool MCP pubblico: il rafforzamento riguarda il comportamento dei tool di update esistenti.

---

## [1.5.0] — 2026-04-10

### Added

- `scf_get_runtime_state` tool: legge `.github/runtime/orchestrator-state.json`.
- `scf_update_runtime_state` tool: aggiorna con merge parziale `orchestrator-state.json`.
- `scf://runtime-state` resource: espone lo stato runtime come JSON leggibile direttamente.
- `FrameworkInventory.get_orchestrator_state()`: lettura con default e gestione file corrotto.
- `FrameworkInventory.set_orchestrator_state()`: scrittura con merge, creazione cartella runtime e timestamp UTC.
- `FrameworkInventory.list_agents_indexes()`: scoperta di tutti i file `AGENTS*.md` per supporto multi-plugin.

### Changed

- `scf://agents-index`: ora aggrega tutti i file `AGENTS*.md` presenti nella root `.github/`.
- Conteggio resource aggiornato da 14 a 15.
- Conteggio tool aggiornato da 23 a 25.

### Notes

- `.github/runtime/` resta esclusa dal `ManifestManager` per design.
- `scf-master-codecrafter` richiede `min_engine_version: 1.5.0`.

---

## [1.4.2] — 2026-04-06

### Fixed

- **README.md**: corretto conteggio tool da 22 a 23; aggiunto `scf_verify_system` nella lista tool.
- **CHANGELOG.md**: normalizzate le date delle versioni precedenti al formato ISO 8601 (YYYY-MM-DD).

---

## [1.4.1] — 2026-04-02

### Fixed

- **Atomicità installazione in `scf_install_package`**: il blocco diff-cleanup (rimozione file
  obsoleti) è stato spostato **dopo** la fase fetch. Se uno o più file non possono essere
  scaricati, l'installazione si interrompe prima di toccare il disco — manifiest e file esistenti
  rimangono intatti. In precedenza, i file obsoleti venivano eliminati prima ancora di verificare
  se il fetch sarebbe andato a buon fine, causando corruzione silenziosa dello stato.
- **Chiavi mancanti nei return di errore di `scf_install_package`**: tutti i path di ritorno
  (successo, fetch failure, OSError rollback e tutti i guard iniziali) includono ora
  uniformemente `removed_obsolete_files` e `preserved_obsolete_files`. I return anticipati
  restituiscono liste vuote `[]`; il rollback OSError restituisce i valori effettivi poiché
  il diff-cleanup è già avvenuto a quel punto.
- **Import inutilizzato** rimosso da `tests/test_update_diff.py` (`import json`).
- **Nuovi test di regressione** in `tests/test_update_diff.py`:
  - `test_fetch_error_leaves_manifest_intact` — verifica che manifest e disco siano intatti
    se il fetch fallisce.
  - `test_fetch_error_return_has_all_keys` — verifica che il dict di ritorno contenga tutte
    le chiavi richieste anche in caso di fetch failure.

---

## [1.4.0] — 2026-04-02

### Added

- **Diff-based cleanup in `scf_install_package`**: durante un update/reinstall, il motore
  calcola i file presenti nell'installazione corrente ma assenti nel nuovo manifest del pacchetto
  e li rimuove automaticamente. I file modificati dall'utente (SHA mismatch) vengono preservati.
  Il risultato include i nuovi campi `removed_obsolete_files` e `preserved_obsolete_files`.
- **Classificazione tripartita in `verify_integrity`**: i file non tracciati nel manifest
  non sono più raggruppati indiscriminatamente come `orphan_candidates`, ma separati in:
  - `user_files` — file `.md` senza `spark: true` (componenti locali utente, non SCF)
  - `untagged_spark_files` — file `.md` con `spark: true` ma non nel manifest (anomalia)
  - `orphan_candidates` — invariante retrocompatibile, ora = `untagged_spark_files`
- Campo `user_file_count` e `untagged_spark_count` aggiunti al `summary` di `verify_integrity`.
- Campi `user_files` e `untagged_spark_files` propagati automaticamente nel risultato
  di `scf_verify_workspace` (passthrough dal report di `verify_integrity`).

---

## [1.3.2] — 2026-04-02

### Fixed

- Corretto docstring `register_tools()`: aggiornato da `"Register all 22 MCP tools"` a `"Register all 23 MCP tools"` per allinearlo al conteggio reale.
- Rimosso `.github/.scf-registry-cache.json` dal tracking Git (era già in `.gitignore`).
- Aggiunta validazione schema JSON nel workflow `registry-sync-gateway.yml`: lo step verifica campi obbligatori, semver e status validi prima di aprire la PR su `scf-registry`.

---

## [1.3.1] — 2026-03-31

### Added

- Workflow `registry-sync-gateway.yml`: gateway centralizzato per la sincronizzazione automatica di `scf-registry`. Riceve eventi `plugin-manifest-updated` via `repository_dispatch` dai plugin e apre PR su `scf-registry` aggiornando `latest_version` ed `engine_min_version`. È l'unico punto del sistema con accesso diretto al registry (tramite `REGISTRY_WRITE_TOKEN`).

---

## [1.3.0] — 2026-03-31

### Added

- Nuovo tool MCP `scf_verify_system`: verifica la coerenza cross-component tra motore, pacchetti installati e registry (versioni e `min_engine_version`).
- Nuovo file `tests/test_engine_coherence.py`: due test di invariante che verificano l'allineamento contatori tool MCP e l'allineamento `ENGINE_VERSION`/CHANGELOG.

### Fixed

- `scf_remove_package`: aggiunta guard esplicita che restituisce errore descrittivo se il pacchetto non è nel manifest, eliminando il falso positivo silenzioso precedente.
- Allineato il commento `Tools (21)` → `Tools (23)` (era desincronizzato rispetto ai tool effettivi).

---

## [1.2.1] — 2026-03-31

### Fixed

- Rimosso il fallback legacy a `.github/FRAMEWORK_CHANGELOG.md` dal motore.
- `FrameworkInventory.get_package_changelog()` e `scf_get_package_changelog` usano ora solo il path canonico `.github/changelogs/{package_id}.md`.
- Rimossi i test del comportamento legacy deprecato.

## [1.2.0] — 2026-03-30

### Added

- **Agente di manutenzione SCF**: creato `.github/agents/spark-engine-maintainer.agent.md` con perimetro operativo, responsabilita' e regole di comportamento per la manutenzione del motore.
- **Skill dedicate all'agente**: aggiunte 6 skill in formato standard `skill-name/SKILL.md`:
  - `.github/skills/scf-coherence-audit/SKILL.md`
  - `.github/skills/scf-changelog/SKILL.md`
  - `.github/skills/scf-tool-development/SKILL.md`
  - `.github/skills/scf-prompt-management/SKILL.md`
  - `.github/skills/scf-release-check/SKILL.md`
  - `.github/skills/scf-documentation/SKILL.md`
- **Istruzioni operative dominio motore**: creato `.github/instructions/spark-engine-maintenance.instructions.md` con convenzioni su naming tool/prompt, contatori, versioning e policy di conferma.
- **Entry point Copilot repository-scoped**: creato `.github/copilot-instructions.md` con regole di ingaggio e riferimenti agli artefatti del maintainer.

### Notes

- Introduzione non-breaking: la release aggiunge artefatti di governance e manutenzione senza alterare API MCP o comportamento runtime del motore.

## [1.1.0] — 2026-03-30

### Added

- **Dual-format skill discovery**: `FrameworkInventory.list_skills()` ora scopre le skill sia nel formato legacy piatto (`.github/skills/*.skill.md`) sia nel formato standard Agent Skills (`.github/skills/skill-name/SKILL.md`). Entrambi i formati sono completamente supportati e funzionali.
- **Test coverage for skill discovery**: suite di test completa per verificare la scoperta di skill in formato piatto, standard, collisioni di nome e comportamento su directory vuote.

### Changed

- **Skill deduplication logic**: in caso di collisione tra un file `foo.skill.md` e una directory `foo/SKILL.md`, il formato piatto legacy ha priorità e prevale.
- **Skill listing sort**: le skill risultati sono ordinate alfabeticamente per nome.

### Fixed

- **Typo in README**: contatore tool corretto da 13 a 18. I tool effettivamente registrati sono 18: lista aggiornata nel README per riflettere `scf_list_available_packages`, `scf_get_package_info`, `scf_list_installed_packages`, `scf_install_package`, `scf_update_packages`, `scf_apply_updates`, `scf_remove_package` aggiunti agli 11 tool core di inventory.

### Notes

- Nessuna breaking change: il comportamento su repository legacy contenenti solo skill in formato piatto rimane completamente invariato.
- La resource `skills://{name}` e il tool `scf_get_skill` funzionano correttamente su entrambi i formati senza modifiche.

---

## [1.0.0] — 2026-02-20

### Initial Release

- Server MCP universale per il SPARK Code Framework
- Discovery dinamico di agenti, skill, istruzioni e prompt da `.github/`
- 14 Resources MCP (agents, skills, instructions, prompts, scf-*) e 11 tool core
- Gestione manifest di installazione con SHA-256 tracking
- Source registry support (pubblico, read-only in v1)
- Tool di installazione, aggiornamento e rimozione di pacchetti SCF
- Parser YAML-style frontmatter con supporto liste inline e block
- Test coverage con unittest (standard library, zero external dependencies)
