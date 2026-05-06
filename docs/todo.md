# TODO — SPARK Dual-Mode Package Contract

> Generato da Copilot Agent (spark-engine-maintainer) il 2026-05-06 UTC.
> Strategia: Dual-Mode Package Contract v1.0
> Stato: IN PIANIFICAZIONE → **COMPLETATO**
>
> Baseline test di riferimento: 313 passed / 9 skipped / 0 failed → aggiornata a 352 passed / 9 skipped post D.0–D.5
> Stato: COMPLETATO (Fase A, B, C, D interamente gated)

## Legenda stati

- [ ] Da fare
- [~] In corso
- [x] Completato
- [!] Bloccato (vedi note)

***

## Fase A — Schema manifest v4.0 + Collision warning + ResourceResolver

> Prerequisito per tutte le fasi successive. Zero breaking change.
> Rischio complessivo: BASSO.

### Task A.1 — Collision warning in list_skills()

File: `spark/inventory/framework.py` — funzione `FrameworkInventory.list_skills()`

- [x] Nel ramo Pass 2 (standard subdirectory format), aggiungere `else` al blocco
  `if key not in seen` con `_log.warning("[SPARK-ENGINE][WARNING] Skill name
  collision: '%s' flat format (.skill.md) wins over subdirectory version.", key)`
- [x] Verificare che il warning sia emesso su `sys.stderr` tramite `_log` (non print)
- [x] Eseguire `pytest tests/ -q --ignore=tests/test_integration_live.py` — baseline
  313 passed deve rimanere invariata

### Task A.2 — Helper _get_deployment_modes in packages/lifecycle.py

File: `spark/packages/lifecycle.py`

- [x] Aggiungere funzione standalone `_get_deployment_modes(manifest: Mapping[str, Any])
  -> dict[str, Any]` che legge `deployment_modes` dal manifest dict
- [x] Ritornare dict normalizzato: `{"mcp_store": bool, "standalone_copy": bool,
  "standalone_files": list[str]}` con fallback espliciti (mcp_store=True,
  standalone_copy=False, standalone_files=[]) quando la sezione è assente o malformata
- [x] Aggiungere export in `spark/packages/__init__.py`
- [x] Aggiungere test unitario in `tests/` per i casi: assente, parziale, malformato

### Task A.3 — Modulo spark/registry/resolver.py

File: `spark/registry/resolver.py` (NUOVO)

- [x] Creare classe `ResourceResolver` con costruttore:
  `__init__(self, registry: McpResourceRegistry, store: PackageResourceStore,
  workspace_github_root: Path)`
- [x] Implementare `resolve(resource_type: str, name: str) -> Path | None` con
  cascata: override (via registry.has_override + registry.resolve) →
  workspace_physical (via workspace_github_root / resource_type) → store
  (via registry.resolve_engine)
- [x] Implementare `enumerate_merged(resource_type: str) ->
  list[tuple[str, Path, str]]` che restituisce (name, resolved_path, source)
  per tutte le risorse da workspace fisico + store, deduplicando per nome con
  stessa priorità di `resolve()` (source: "override" | "workspace" | "store")
- [x] Aggiungere export in `spark/registry/__init__.py`
- [x] Nessuna dipendenza da `FrameworkInventory` (evitare import circolare)
- [x] Aggiungere test unitario coprendo cascata, dedup e fallback path

### Task A.4 — Integrazione ResourceResolver in FrameworkInventory

File: `spark/inventory/framework.py`

- [x] Aggiungere metodo privato `_build_resolver() -> ResourceResolver | None` che
  costruisce un `ResourceResolver` se `self.mcp_registry` e `self.resource_store`
  sono popolati (non None), altrimenti ritorna None
- [x] Aggiornare `list_agents()`, `list_skills()`, `list_instructions()`,
  `list_prompts()` per tentare `_build_resolver()`: se disponibile usare
  `resolver.enumerate_merged(resource_type)` per costruire la lista di
  `FrameworkFile`; fallback a `_list_by_pattern()` se resolver è None
- [x] Il tipo di ritorno `list[FrameworkFile]` rimane invariato — costruire
  `FrameworkFile` dalla tupla `(name, path, source)` del resolver
- [x] Verificare che `scf_list_agents` e `agents://{name}` restituiscano contenuti
  coerenti per lo stesso agente post-A.4
- [x] Aggiornare o aggiungere test per `list_agents` con resolver popolato

***

## Fase B — deployment_mode in scf_install_package

> Dipende da Fase A (Task A.2 per `_get_deployment_modes`).
> Rischio complessivo: BASSO.

### Task B.1 — _install_standalone_files_v3 in lifecycle.py

File: `spark/boot/lifecycle.py` — classe `_V3LifecycleMixin`

- [x] Aggiungere metodo `_install_standalone_files_v3(self, package_id, pkg_version,
  pkg_manifest, manifest) -> dict[str, Any]` con stessa firma di
  `_install_workspace_files_v3`
- [x] Internamente: chiamare `_get_deployment_modes(pkg_manifest)` per ottenere
  `standalone_files`; se lista vuota → ritornare `{"success": True, "files_written":
  [], "preserved": [], "errors": []}`
- [x] Per ogni file in `standalone_files`: lookup in store via `PackageResourceStore`,
  applica sha-check idempotente identica a `_install_workspace_files_v3`, scrivi
  via `WorkspaceWriteGateway`
- [x] Il metodo è idempotente: stessa logica preservation gate di
  `_install_workspace_files_v3`
- [x] Aggiungere test unitario parametrizzato: standalone_files presente / assente /
  con sha-match (idempotenza)

### Task B.2 — Parametro deployment_mode in scf_install_package

File: `spark/boot/engine.py` — closure `scf_install_package` dentro `register_tools()`

- [x] Aggiungere `deployment_mode: str = "auto"` come parametro tra `update_mode`
  e `migrate_copilot_instructions`
- [x] Aggiungere validazione: valori ammessi `"auto"`, `"store"`, `"copy"`;
  errore MCP-friendly per valori non supportati
- [x] Logica dispatch: `"store"` → comportamento v3 attuale (skip standalone);
  `"copy"` → chiama `self._install_standalone_files_v3` dopo
  `_install_workspace_files_v3`; `"auto"` → legge `_get_deployment_modes(pkg_manifest).
  standalone_copy` e decide
- [x] Includere `standalone_files_written` nel dict di ritorno del tool quando
  `deployment_mode != "store"`
- [x] Verificare che tutti i caller interni esistenti (`scf_bootstrap_workspace`,
  `scf_update_packages`, ecc.) non passino `deployment_mode` → ricevono default
  `"auto"` → comportamento invariato

***

## Fase C — Logging gap + scf_verify_workspace esteso

> Dipende da Fase A (Task A.3 per ResourceResolver disponibile).
> Indipendente da Fase B.
> Rischio complessivo: BASSO.

### Task C.1 — Source divergence report in scf_verify_workspace

File: `spark/boot/engine.py` — closure `scf_verify_workspace` dentro `register_tools()`

- [x] Dopo le verifiche esistenti, aggiungere blocco `source_divergence`:
  costruire un `ResourceResolver` dal registry e store disponibili
- [x] Enumerare risorse in store (via `registry.list_all()` filtrate per tipo)
  e risorse in workspace fisico (via `inventory.list_agents()` ecc.)
- [x] Classificare: `only_in_store` (store non presenti nel workspace fisico),
  `only_in_workspace` (workspace non registrate nello store), `divergent_content`
  (hash diverso store vs workspace per stessa risorsa)
- [x] Emettere `_log.warning("[SPARK-ENGINE][WARNING] Source divergence: ...")` per
  ogni coppia divergente su stderr
- [x] Aggiungere campo `"source_divergence"` al dict di ritorno (non breaking: campo
  nuovo opzionale)

***

## Fase D — Deframmentazione engine.py

> Dipende da Fase A e B (boundary tool stabilizzate).
> Refactoring puro: nessun tool cambia nome, firma o comportamento.
> Rischio complessivo: MEDIO (D.3 e D.5 ALTO per complessità logica).

### Task D.0 — Prerequisito: conversione closure vars → instance attrs

File: `spark/boot/engine.py`

- [x] Aggiungere metodo privato `_init_runtime_objects() -> None` in
  `SparkFrameworkEngine`
- [x] Spostare in `_init_runtime_objects()` la creazione di: `ManifestManager` →
  `self._manifest`, `RegistryClient` → `self._registry_client`, `MergeEngine` →
  `self._merge_engine`, `SnapshotManager` → `self._snapshots`,
  `MergeSessionManager` → `self._sessions`
- [x] Preservare `self._sessions.cleanup_expired_sessions()` in `_init_runtime_objects()`
- [x] In `register_tools()`: sostituire la creazione locale con
  `self._init_runtime_objects()` e aggiungere alias locali `manifest = self._manifest`
  ecc. per mantenere i tool closure invariati nel breve termine
- [x] Aggiungere type hints per i nuovi attributi in `__init__`
- [x] Eseguire suite completa — baseline 313 passed deve rimanere invariata

### Task D.1 — Estrazione tools_resources.py (13 tool)

File: `spark/boot/tools_resources.py` (NUOVO)

- [x] Creare funzione factory `register_resource_tools(inventory, engine_root, mcp, tool_names)`
- [x] Spostare i 13 tool: scf_read_resource, scf_get_skill_resource,
  scf_get_instruction_resource, scf_get_agent_resource, scf_get_prompt_resource,
  scf_list_agents, scf_get_agent, scf_list_skills, scf_get_skill,
  scf_list_instructions, scf_get_instruction, scf_list_prompts, scf_get_prompt
- [x] Spostare helpers locali usati solo da questi tool: `_parse_resource_uri`,
  `_ensure_registry`, `_ff_to_dict`
- [x] In `engine.py register_tools()`: sostituire le 13 definizioni con
  `register_resource_tools(inventory, self._ctx.engine_root, self._mcp, tool_names)`
- [x] Aggiornare `test_engine_coherence.py` per includere tools_resources.py nel conteggio
- [x] Verificare suite test completa post-estrazione — 352 passed, 9 skipped, 0 failed

### Task D.2 — Estrazione tools_override.py (3 tool)

File: `spark/boot/tools_override.py` (NUOVO)

- [x] Creare funzione factory `register_override_tools(inventory, ctx, mcp, tool_names) -> None`
- [x] Spostare: scf_list_overrides, scf_override_resource, scf_drop_override
- [x] Aggiornare `test_engine_coherence.py` per includere tools_override.py nel conteggio
- [x] Verificare suite test completa post-estrazione — 352 passed, 9 skipped, 0 failed

### Task D.3 — Estrazione tools_bootstrap.py (4 tool)

File: `spark/boot/tools_bootstrap.py` (NUOVO)

- [x] Creare funzione factory `register_bootstrap_tools(engine, mcp, tool_names) -> None`
- [x] Spostare: scf_verify_workspace, scf_verify_system, scf_bootstrap_workspace,
  scf_migrate_workspace
- [x] Preservare il pattern `engine._bootstrap_workspace_tool = scf_bootstrap_workspace`
  che è richiesto da `ensure_minimal_bootstrap()`
- [x] Rischio ALTO: scf_bootstrap_workspace ha logica complessa e callback injection
- [x] Verificare suite test completa post-estrazione con focus su test_bootstrap_workspace*

### Task D.4 — Estrazione tools_policy.py (9 tool)

File: `spark/boot/tools_policy.py` (NUOVO)

- [x] Creare funzione factory `register_policy_tools(engine, mcp, tool_names) -> None`
- [x] Spostare: scf_get_project_profile, scf_get_global_instructions, scf_get_model_policy,
  scf_get_framework_version, scf_get_workspace_info, scf_get_runtime_state,
  scf_update_runtime_state, scf_get_update_policy, scf_set_update_policy
- [x] Verificare suite test completa post-estrazione

### Task D.5 — Estrazione tools_packages.py (15 tool) + riduzione engine.py

File: `spark/boot/tools_packages.py` (NUOVO) + `spark/boot/engine.py` (riduzione)

- [x] Creare funzione factory `register_package_tools(engine, mcp, tool_names) -> None`
- [x] Spostare tutti i 15 tool packages + conflict lifecycle: scf_list_available_packages,
  scf_get_package_info, scf_list_installed_packages, scf_install_package,
  scf_check_updates, scf_update_package, scf_update_packages, scf_apply_updates,
  scf_plan_install, scf_remove_package, scf_get_package_changelog,
  scf_resolve_conflict_ai, scf_approve_conflict, scf_reject_conflict,
  scf_finalize_update
- [x] Spostare tutti gli shim e helpers di install_helpers (con self.* per closure vars)
- [x] Ridurre `engine.py` ad assembler puro con le 5 chiamate factory:
  register_resource_tools, register_override_tools, register_bootstrap_tools,
  register_policy_tools, register_package_tools
- [x] Aggiornare contatore in `spark/boot/sequence.py`:
  `_log.info("Tools registered: 44 total")` — verificare che sia ancora 44
- [x] Rischio ALTO: tocca scf_install_package e conflict resolution — suite completa
  obbligatoria
- [x] GATE PASS: 352 passed, 9 skipped, 0 failed

***

## Anomalie parallele aperte

> Task secondari emersi durante l'analisi, gestiti in parallelo
> senza bloccare il flusso principale.

### AP.1 — scf_get_agent vs scf_get_agent_resource divergenza silenziosa (get singolo)

- [ ] Dopo Fase A (A.4 integrazione ResourceResolver), verificare che `scf_get_agent(name)`
  e `scf_get_agent_resource(name)` restituiscano lo stesso contenuto per agenti
  installati via v3 store
- [ ] Se divergono ancora, aggiungere warning nel risultato del tool:
  `"source_warning": "agent found in workspace but not in store — consider
  registering an override"` o viceversa
- [ ] Aggiornare test di integrazione per coprire il caso store-vs-workspace

### AP.2 — scf_list_agents omette agenti Cat.B post v3 install

- [ ] Aggiungere test esplicito: dopo install di spark-base in un workspace vuoto,
  verificare che `scf_list_agents` includa Agent-Analyze, Agent-Git ecc. (agenti
  Cat.B solo nello store)
- [ ] Il test deve fallire PRIMA di A.4 e passare DOPO A.4 (test di regressione
  intenzionale che documenta il fix)

### AP.3 — Contatore "Tools registered: 44 total" non automatico

- [ ] Valutare aggiunta di un assertion automatica in `register_tools()`:
  `assert len(tool_names) == 44, f"Expected 44 tools, got {len(tool_names)}"` emessa
  come warning (non eccezione) su stderr se il contatore diverge
- [ ] Alternativa: generare il log dal contatore reale `len(tool_names)` invece di
  hardcoded "44"

***

## Note tecniche

- Baseline regressione: 313 passed / 9 skipped — da verificare dopo ogni Task.
- Zero `print()` in tutto il codice prodotto. Logging esclusivamente via `_log.*` su `sys.stderr`.
- Ogni nuovo metodo pubblico o modulo: type hints completi obbligatori.
- ManifestManager è l'unico punto di scrittura del manifest workspace — invariante da non violare.
- `_install_standalone_files_v3` (B.1) deve replicare il preservation gate di
  `_install_workspace_files_v3` per evitare sovrascrittura di file utente modificati.
- La conversione closure vars → instance attrs (D.0) è prerequisito BLOCCANTE per D.1–D.5.
  Eseguire i task in ordine: D.0 → D.1 → D.2 → D.3 → D.4 → D.5.
- `scf_bootstrap_workspace` inietta se stessa in `self._bootstrap_workspace_tool` — questo
  pattern deve essere preservato in D.3 per non rompere `ensure_minimal_bootstrap()`.
