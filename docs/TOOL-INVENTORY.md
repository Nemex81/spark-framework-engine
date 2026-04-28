# TOOL-INVENTORY.md — Inventario tool scf_* engine v2.4.0
# Aggiornato: 2026-04-28
# Fonte: spark-framework-engine.py
# Conteggio: 35 tool esistenti
# Nuovi tool v3.0 (Fase 3): +5 → totale 40 (vedi sezione finale)

## Nota di lettura

- Firma completa con parametri e tipo di ritorno.
- Riga = numero riga corrente in `spark-framework-engine.py`.
- Nessuna tabella: lista NVDA-friendly.

---

## Gruppo 1 — Lettura risorse framework (agenti, skill, instruction, prompt)

- `scf_list_agents() -> dict[str, Any]`
  Riga: 2589

- `scf_get_agent(name: str) -> dict[str, Any]`
  Riga: 2595

- `scf_list_skills() -> dict[str, Any]`
  Riga: 2609

- `scf_get_skill(name: str) -> dict[str, Any]`
  Riga: 2615

- `scf_list_instructions() -> dict[str, Any]`
  Riga: 2630

- `scf_get_instruction(name: str) -> dict[str, Any]`
  Riga: 2636

- `scf_list_prompts() -> dict[str, Any]`
  Riga: 2651

- `scf_get_prompt(name: str) -> dict[str, Any]`
  Riga: 2657

## Gruppo 2 — Lettura profilo workspace e metadati motore

- `scf_get_project_profile() -> dict[str, Any]`
  Riga: 2672

- `scf_get_global_instructions() -> dict[str, Any]`
  Riga: 2685

- `scf_get_model_policy() -> dict[str, Any]`
  Riga: 2695

- `scf_get_framework_version() -> dict[str, Any]`
  Riga: 2708

- `scf_get_workspace_info() -> dict[str, Any]`
  Riga: 2716

## Gruppo 3 — Registry e info pacchetti

- `scf_list_available_packages() -> dict[str, Any]`
  Riga: 2911

- `scf_get_package_info(package_id: str) -> dict[str, Any]`
  Riga: 2924

## Gruppo 4 — Installazione e gestione pacchetti

- `scf_list_installed_packages() -> dict[str, Any]`
  Riga: 3603

- `scf_install_package(package_id: str, conflict_mode: str = "abort", update_mode: str = "", migrate_copilot_instructions: bool = False) -> dict[str, Any]`
  Riga: 3628

- `scf_check_updates() -> dict[str, Any]`
  Riga: 4378

- `scf_update_package(package_id: str, conflict_mode: str = "abort", update_mode: str = "", migrate_copilot_instructions: bool = False) -> dict[str, Any]`
  Riga: 4391

- `scf_update_packages() -> dict[str, Any]`
  Riga: 4761

- `scf_apply_updates(package_id: str | None = None, conflict_mode: str = "abort", migrate_copilot_instructions: bool = False) -> dict[str, Any]`
  Riga: 4766

- `scf_plan_install(package_id: str) -> dict[str, Any]`
  Riga: 4869

- `scf_remove_package(package_id: str) -> dict[str, Any]`
  Riga: 4945

- `scf_get_package_changelog(package_id: str) -> dict[str, Any]`
  Riga: 4971

## Gruppo 5 — Verifica e diagnostica

- `scf_verify_workspace() -> dict[str, Any]`
  Riga: 4989

- `scf_verify_system() -> dict[str, Any]`
  Riga: 4999

## Gruppo 6 — Runtime state e bootstrap

- `scf_get_runtime_state() -> dict[str, Any]`
  Riga: 5065

- `scf_update_runtime_state(patch: dict[str, Any]) -> dict[str, Any]`
  Riga: 5070

- `scf_bootstrap_workspace(install_base: bool = False, conflict_mode: str = "abort", update_mode: str = "", migrate_copilot_instructions: bool = False) -> dict[str, Any]`
  Riga: 5075

## Gruppo 7 — Sessioni merge (conflict resolution)

- `scf_resolve_conflict_ai(session_id: str, conflict_id: str) -> dict[str, Any]`
  Riga: 5487

- `scf_approve_conflict(session_id: str, conflict_id: str) -> dict[str, Any]`
  Riga: 5529

- `scf_reject_conflict(session_id: str, conflict_id: str) -> dict[str, Any]`
  Riga: 5609

- `scf_finalize_update(session_id: str) -> dict[str, Any]`
  Riga: 5660

## Gruppo 8 — Update policy

- `scf_get_update_policy() -> dict[str, Any]`
  Riga: 5748

- `scf_set_update_policy(auto_update: bool, default_mode: str | None = None, mode_per_package: dict[str, str] | None = None, mode_per_file_role: dict[str, str] | None = None) -> dict[str, Any]`
  Riga: 5759

---

## Nuovi tool v3.0 — Fase 3 (NON ancora esistenti)

Nomi riservati, zero collisioni con i 35 sopra:

- `scf_migrate_workspace(dry_run: bool = True, force: bool = False) -> dict[str, Any]`
  Fase: 0 — punto inserimento: dopo riga 5075 (dopo scf_bootstrap_workspace)

- `scf_read_resource(uri: str, mode: str = "auto") -> dict[str, Any]`
  Fase: 3 — mode: "auto" | "engine" | "override"

- `scf_override_resource(uri: str, content: str) -> dict[str, Any]`
  Fase: 3

- `scf_drop_override(uri: str) -> dict[str, Any]`
  Fase: 3

- `scf_list_overrides() -> dict[str, Any]`
  Fase: 3

Nessun conflitto di nome. Verifica: grep "scf_migrate_workspace\|scf_read_resource\|scf_override_resource\|scf_drop_override\|scf_list_overrides" in spark-framework-engine.py → 0 occorrenze.
