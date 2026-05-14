# API Reference — SPARK Framework Engine MCP Tools

> **Versione documentata:** 3.6.0  
> **Tool totali:** 53 (51 attivi + 2 deprecated)  
> **Fonte:** `spark/boot/tools_*.py` — tutti i tool sono registrati con `@_register_tool("scf_*")`

Per l'architettura generale e il flusso di boot, vedi [architecture.md](architecture.md).

---

## Indice per Categoria

| Categoria | Tool |
|-----------|------|
| [Workspace](#1-workspace) | `scf_verify_workspace`, `scf_verify_system`, `scf_bootstrap_workspace`, `scf_migrate_workspace` |
| [Pacchetti — Query](#2-pacchetti--query) | `scf_list_available_packages`, `scf_get_package_info`, `scf_list_installed_packages`, `scf_plan_install` |
| [Pacchetti — Install](#3-pacchetti--install) | `scf_install_package` |
| [Pacchetti — Remove](#4-pacchetti--remove) | `scf_remove_package`, `scf_get_package_changelog` |
| [Pacchetti — Update](#5-pacchetti--update) | `scf_check_updates`, `scf_update_package`, `scf_update_packages`, `scf_apply_updates` |
| [Merge / Conflitti](#6-merge--conflitti) | `scf_resolve_conflict_ai`, `scf_approve_conflict`, `scf_reject_conflict`, `scf_finalize_update` |
| [Override](#7-override) | `scf_list_overrides`, `scf_override_resource`, `scf_drop_override` |
| [Plugin](#8-plugin) | `scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`, `scf_plugin_list`, `scf_plugin_list_remote`, `scf_plugin_install_remote`, `scf_get_plugin_info` ✅  ·  `scf_list_plugins`, `scf_install_plugin` ⚠️ |
| [Risorse](#9-risorse) | `scf_read_resource`, `scf_get_*_resource` (4), `scf_list_*` / `scf_get_*` (10) |
| [Policy / Stato](#10-policy--stato) | `scf_get_project_profile`, `scf_get_global_instructions`, `scf_get_model_policy`, `scf_get_framework_version`, `scf_get_workspace_info`, `scf_get_runtime_state`, `scf_update_runtime_state`, `scf_get_update_policy`, `scf_set_update_policy` |
| [CLI — Entry Points](#11-cli--entry-points) | `spark_launcher.py`, `python -m spark.cli`, `scripts/scf`, `scripts/scf_universal.py` |

Legenda: ✅ Attivo  · ⚠️ Deprecated

---

## 1. Workspace

### `scf_verify_workspace`

**File:** `spark/boot/tools_bootstrap.py:131`

Verifica l'integrità del manifest runtime rispetto ai file fisicamente presenti
in `.github/`. Produce anche un report di source divergence (risorse solo in
store vs solo nel workspace fisico).

**Parametri:** nessuno

**Risposta:**
```json
{
  "summary": { "issue_count": 0, "is_clean": true },
  "source_divergence": {
    "only_in_store": [],
    "only_in_workspace": [],
    "divergent_content": []
  }
}
```

---

### `scf_verify_system`

**File:** `spark/boot/tools_bootstrap.py:180`

Verifica la coerenza cross-component tra motore, pacchetti installati e registry
remoto. Confronta versioni e `min_engine_version` dichiarate nei manifest dei
pacchetti con le corrispondenti entry nel registry.

**Parametri:** nessuno

**Risposta:**
```json
{
  "engine_version": "3.3.0",
  "packages_checked": 2,
  "issues": [],
  "warnings": [],
  "manifest_empty": false,
  "is_coherent": true
}
```

Campi `issues[].type` possibili: `"registry_stale"`, `"engine_min_mismatch"`.

---

### `scf_bootstrap_workspace`

**File:** `spark/boot/tools_bootstrap.py:250`

Copia i file Cat. A (dichiarati in `workspace_files` del manifest `spark-base`
più tre sentinelle di discovery) nel workspace utente.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `install_base` | `bool` | `False` | Se `True`, installa anche `spark-base` dopo il bootstrap |
| `conflict_mode` | `str` | `"abort"` | Modalità conflitto: `abort`, `replace`, `manual`, `auto`, `assisted` |
| `update_mode` | `str` | `""` | Strategia update: `ask`, `integrative`, `conservative`, `ask_later` |
| `migrate_copilot_instructions` | `bool` | `False` | Se `True`, migra `copilot-instructions.md` al formato SCF-marker |
| `force` | `bool` | `False` | Se `True`, sovrascrive anche i file modificati dall'utente |
| `dry_run` | `bool` | `False` | Se `True`, simula senza scrivere alcun file |

**Risposta (campi garantiti in tutti i rami):**
```json
{
  "success": true,
  "status": "ok",
  "files_written": [],
  "files_copied": [],
  "files_skipped": [],
  "files_protected": [],
  "sentinel_present": true,
  "message": "...",
  "preserved": [],
  "workspace": "/path/to/workspace"
}
```

**Idempotenza:** garantita dalla sentinella `spark-assistant.agent.md`.

---

### `scf_migrate_workspace`

**File:** `spark/boot/tools_bootstrap.py:898`

Migra il workspace da una versione pre-ownership a quella corrente.
Sposta metadati runtime da `.github/runtime/` alla directory locale del motore.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `dry_run` | `bool` | `True` | Se `True` (default), simula senza scrivere |
| `force` | `bool` | `False` | Se `True`, forza la migrazione anche su workspace già migrati |

---

## 2. Pacchetti — Query

### `scf_list_available_packages`

**File:** `spark/boot/tools_packages_query.py:76`

Elenca tutti i pacchetti disponibili nel registry pubblico SCF.

**Parametri:** nessuno

**Risposta:**
```json
{
  "success": true,
  "count": 3,
  "packages": [
    { "id": "spark-base", "description": "...", "latest_version": "1.7.3" }
  ]
}
```

---

### `scf_get_package_info`

**File:** `spark/boot/tools_packages_query.py:89`

Restituisce informazioni dettagliate per un pacchetto, incluse statistiche
sui file del manifest e compatibilità con il workspace attivo.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `package_id` | `str` | ID del pacchetto nel registry |

**Risposta:**
```json
{
  "success": true,
  "package": { "id": "...", "latest_version": "...", "status": "..." },
  "manifest": {
    "schema_version": "3.1",
    "version": "...",
    "min_engine_version": "3.1.0",
    "dependencies": [],
    "conflicts": [],
    "file_ownership_policy": "error",
    "file_count": 0,
    "categories": { "agents": 0, "skills": 0, "instructions": 0 }
  },
  "compatibility": {
    "engine_version": "3.3.0",
    "engine_compatible": true,
    "missing_dependencies": [],
    "present_conflicts": []
  }
}
```

---

### `scf_list_installed_packages`

**File:** `spark/boot/tools_packages_query.py:195`

Elenca i pacchetti attualmente installati nel workspace attivo.

**Parametri:** nessuno

**Risposta:**
```json
{ "count": 1, "packages": [{ "id": "spark-base", "version": "1.7.3" }] }
```

---

### `scf_plan_install`

**File:** `spark/boot/tools_packages_query.py:220`

Restituisce un'anteprima read-only del risultato di installazione senza
scrivere alcun file: file scrivibili, file da preservare, conflitti potenziali.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `package_id` | `str` | ID del pacchetto da analizzare |

---

## 3. Pacchetti — Install

### `scf_install_package`

**File:** `spark/boot/tools_packages_install.py:219`

Installa un pacchetto SCF dal registry pubblico.

- Pacchetti con `min_engine_version >= 3.0.0` → percorso v3 (store engine).
- Pacchetti legacy (< 3.0.0) → scrittura diretta in `.github/` (percorso v2).

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `package_id` | `str` | — | ID nel registry |
| `conflict_mode` | `str` | `"abort"` | `abort`, `replace`, `manual`, `auto`, `assisted` |
| `update_mode` | `str` | `""` | `ask`, `integrative`, `replace`, `conservative`, `selective` |
| `deployment_mode` | `str` | `"auto"` | `auto`, `store`, `copy` — controlla scrittura file v3 in `.github/` |
| `migrate_copilot_instructions` | `bool` | `False` | Migra `copilot-instructions.md` prima dell'installazione |

**Risposta (campi garantiti):**
```json
{ "success": true, "package": "spark-base", "version": "1.7.3" }
```

**Risposta v3 (aggiuntivi su successo):**
```json
{
  "deployment_summary": {
    "engine_store": true,
    "standalone_copy": false,
    "standalone_files_count": 0
  },
  "mcp_services_activated": ["agents://spark-assistant", "skills://..."],
  "workspace_files_written": [],
  "plugin_files_installed": []
}
```

**Risposta v2 legacy (aggiuntivi su successo):**
```json
{
  "installed": [".github/agents/spark-assistant.agent.md"],
  "preserved": [],
  "extended_files": [],
  "merge_clean": [],
  "merge_conflict": [],
  "session_id": null
}
```

**Risposta su `action_required`:**
```json
{
  "success": true,
  "action_required": "authorize_github_write",
  "message": "..."
}
```

Valori `action_required` possibili: `authorize_github_write`,
`migrate_copilot_instructions`, `choose_update_mode`.

**Rollback automatico:** in caso di errore in scrittura, il tool ripristina
i file appena toccati e non aggiorna il manifest in modo parziale.

---

## 4. Pacchetti — Remove

### `scf_remove_package`

**File:** `spark/boot/tools_packages_remove.py:32`

Rimuove un pacchetto SCF installato dal workspace.
Elimina solo i file non modificati dall'utente; i file modificati vengono
preservati e riportati in `preserved_user_modified`.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `package_id` | `str` | ID del pacchetto installato |

**Risposta:**
```json
{
  "success": true,
  "package": "spark-base",
  "preserved_user_modified": [],
  "deleted_snapshots": []
}
```

---

### `scf_get_package_changelog`

**File:** `spark/boot/tools_packages_remove.py:82`

Restituisce il contenuto del changelog per un pacchetto installato.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `package_id` | `str` | ID del pacchetto installato |

**Risposta:**
```json
{
  "package": "spark-base",
  "path": ".github/changelogs/spark-base.md",
  "content": "# Changelog...",
  "version": "1.7.3"
}
```

---

## 5. Pacchetti — Update

### `scf_check_updates`

**File:** `spark/boot/tools_packages_update.py:261`

Restituisce solo i pacchetti installati per cui è disponibile un aggiornamento.

**Parametri:** nessuno

**Risposta:**
```json
{ "success": true, "count": 1, "updates": [{ "package": "spark-base", "from": "1.7.2", "to": "1.7.3" }] }
```

---

### `scf_update_package`

**File:** `spark/boot/tools_packages_update.py:274`

Aggiorna un singolo pacchetto installato preservando i file modificati dall'utente.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `package_id` | `str` | — | ID del pacchetto da aggiornare |
| `conflict_mode` | `str` | `"abort"` | `abort`, `replace`, `manual`, `auto`, `assisted` |
| `update_mode` | `str` | `""` | `ask`, `integrative`, `replace`, `conservative`, `selective` |
| `migrate_copilot_instructions` | `bool` | `False` | Migra `copilot-instructions.md` prima dell'update |

**Risposta:** stessa struttura di `scf_install_package`, con campo aggiuntivo:
```json
{ "version_from": "1.7.2", "version_to": "1.7.3" }
```

---

### `scf_update_packages`

**File:** `spark/boot/tools_packages_update.py:514`

Controlla gli aggiornamenti per tutti i pacchetti installati e restituisce un
piano ordinato di aggiornamento (anteprima, non applica).

**Parametri:** nessuno

---

### `scf_apply_updates`

**File:** `spark/boot/tools_packages_update.py:519`

Applica gli aggiornamenti disponibili reinstallando le versioni più recenti
dal registry. Se `package_id` è fornito, aggiorna solo quel pacchetto.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `package_id` | `str \| None` | `None` | ID pacchetto specifico; `None` = tutti |
| `conflict_mode` | `str` | `"abort"` | `abort`, `replace`, `manual`, `auto`, `assisted` |
| `migrate_copilot_instructions` | `bool` | `False` | Migra `copilot-instructions.md` prima dell'apply |

---

## 6. Merge / Conflitti

Questi tool gestiscono le sessioni interattive di merge aperte durante
`scf_install_package` o `scf_update_package` con `conflict_mode: assisted`.

### `scf_resolve_conflict_ai`

**File:** `spark/boot/tools_packages_diagnostics.py:64`

Propone una risoluzione automatica conservativa per un conflitto di merge.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `session_id` | `str` | ID della sessione merge attiva |
| `conflict_id` | `str` | ID del conflitto nella sessione |

**Risposta:**
```json
{
  "success": true,
  "session_id": "...",
  "conflict_id": "...",
  "proposed_text": "...",
  "validator_results": { "passed": true },
  "resolution_status": "proposed"
}
```

---

### `scf_approve_conflict`

**File:** `spark/boot/tools_packages_diagnostics.py:106`

Approva e scrive nel workspace una proposta già validata per un conflitto.
Esegue i validatori post-merge prima della scrittura.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `session_id` | `str` | ID della sessione merge attiva |
| `conflict_id` | `str` | ID del conflitto da approvare |

**Risposta:**
```json
{
  "success": true,
  "approved": true,
  "remaining_conflicts": 0
}
```

---

### `scf_reject_conflict`

**File:** `spark/boot/tools_packages_diagnostics.py:196`

Rifiuta una proposta e mantiene il file in fallback manuale con marcatori
`<<<<<<<`/`>>>>>>>` nel file fisico.

**Parametri:** `session_id: str`, `conflict_id: str`

---

### `scf_finalize_update`

**File:** `spark/boot/tools_packages_diagnostics.py:257`

Finalizza una sessione di merge manuale dopo che l'utente ha risolto tutti
i marcatori di conflitto nel workspace.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `session_id` | `str` | ID della sessione merge da finalizzare |

**Risposta:**
```json
{
  "success": true,
  "session_id": "...",
  "written_files": [".github/copilot-instructions.md"],
  "pending": []
}
```

Se `pending` non è vuoto, la sessione non viene finalizzata (marcatori ancora presenti).

---

## 7. Override

Gli override permettono di sostituire localmente una risorsa engine (agente,
skill, instruction, prompt) senza modificare lo store centralizzato.

### `scf_list_overrides`

**File:** `spark/boot/tools_override.py:50`

Elenca gli override workspace registrati nel `McpResourceRegistry`.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `resource_type` | `str \| None` | `None` | Filtro: `agents`, `prompts`, `skills`, `instructions` |

**Risposta:**
```json
{
  "count": 1,
  "items": [{ "uri": "agents://spark-assistant", "type": "agents", "path": "...", "sha256": "..." }]
}
```

---

### `scf_override_resource`

**File:** `spark/boot/tools_override.py:93`

Crea o aggiorna un override workspace per la risorsa indicata.
Richiede `github_write_authorized: true` nello stato runtime.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `uri` | `str` | URI nel formato `{type}://{name}` |
| `content` | `str` | Nuovo contenuto del file di override |

**Risposta:**
```json
{ "success": true, "uri": "agents://spark-assistant", "path": "...", "sha256": "..." }
```

---

### `scf_drop_override`

**File:** `spark/boot/tools_override.py:139`

Rimuove un override workspace e lo deregistra dal registry.
Richiede `github_write_authorized: true`.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `uri` | `str` | URI nel formato `{type}://{name}` |

**Risposta:**
```json
{ "success": true, "uri": "agents://spark-assistant", "file_removed": true }
```

---

## 8. Plugin

I plugin sono pacchetti con `delivery_mode: "file"` che installano file fisici
nel workspace utente tramite `.github/.spark-plugins`.

### `scf_plugin_install` ✅

**File:** `spark/boot/tools_plugins.py:183`

Installa un plugin dal registry SCF nel workspace. Traccia l'installazione
in `.github/.spark-plugins`.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `pkg_id` | `str` | — | ID del pacchetto nel registry |
| `workspace_root` | `str` | `""` | Path assoluto al workspace; default: workspace engine attivo |

**Risposta:**
```json
{ "status": "ok", "pkg_id": "scf-pycode-crafter", "version": "2.1.0", "files_installed": [...] }
```

---

### `scf_plugin_remove` ✅

**File:** `spark/boot/tools_plugins.py:234`

Rimuove un plugin installato. Elimina i file non modificati, deregistra da
`.github/.spark-plugins` e rimuove il riferimento `#file:` da `copilot-instructions.md`.

**Parametri:** `pkg_id: str`, `workspace_root: str = ""`

**Risposta:**
```json
{ "status": "ok", "pkg_id": "scf-pycode-crafter", "files_removed": [...] }
```

---

### `scf_plugin_update` ✅

**File:** `spark/boot/tools_plugins.py:282`

Aggiorna un plugin installato alla versione più recente (remove → re-install).
Preserva i file modificati dall'utente.

**Parametri:** `pkg_id: str`, `workspace_root: str = ""`

**Risposta:**
```json
{ "status": "ok", "pkg_id": "...", "old_version": "2.0.0", "new_version": "2.1.0" }
```

---

### `scf_plugin_list` ✅

**File:** `spark/boot/tools_plugins.py:336`

Elenca i plugin installati e i pacchetti disponibili nel registry remoto.

**Parametri:** `workspace_root: str = ""`

**Risposta:**
```json
{
  "status": "ok",
  "installed": [],
  "available": [],
  "message": "0 plugin installati, 3 disponibili nel registry."
}
```

---

### `scf_plugin_list_remote` ✅

**File:** `spark/boot/tools_plugins.py:436`

Elenca i pacchetti disponibili nel registry SCF remoto (Universe U2) con cache TTL
di 1 ora. Ogni voce include il campo `universe` e `delivery_mode`.
I pacchetti `mcp_only` sono U1 (serviti localmente dall'engine); gli altri sono U2
(installabili nel workspace).

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `force_refresh` | `bool` | `False` | Se `True`, bypassa la cache e scarica dati freschi dal registry |

**Risposta:**

```json
{
  "status": "ok",
  "packages": [...],
  "u1_count": 2,
  "u2_count": 5,
  "from_cache": true,
  "cache_age_seconds": 120,
  "message": "7 pacchetti nel registry (2 U1 mcp_only, 5 U2 installabili)."
}
```

---

### `scf_plugin_install_remote` ✅

**File:** `spark/boot/tools_plugins.py:532`

Scarica un plugin Universe U2 direttamente dal sorgente GitHub in `.github/`.
Solo pacchetti con `delivery_mode != "mcp_only"` sono supportati.
Non registra il plugin in `.spark-plugins`: per il ciclo di vita completo
usare `scf_plugin_install`.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `pkg_id` | `str` | — | ID del pacchetto nel registry (es. `"scf-master-codecrafter"`) |
| `workspace_root` | `str` | `""` | Path assoluto al workspace; default: workspace engine attivo |
| `overwrite` | `bool` | `False` | Se `True`, sovrascrive file già presenti in `.github/` |
| `force_refresh` | `bool` | `False` | Se `True`, bypassa la cache registry prima di risolvere il pacchetto |

**Risposta:**

```json
{
  "status": "ok",
  "pkg_id": "scf-master-codecrafter",
  "universe": "U2",
  "version": "2.3.0",
  "files_written": [...],
  "files_skipped": [],
  "errors": [],
  "message": "3 file scritti in .github/."
}
```

---

### `scf_get_plugin_info` ✅

**File:** `spark/boot/tools_plugins.py:447`

Restituisce i dettagli di un singolo plugin per ID (nome, versione, dipendenze,
`source_url`, `min_engine_version`).

**Parametri:** `plugin_id: str`

---

### `scf_list_plugins` ⚠️ Deprecated

**File:** `spark/boot/tools_plugins.py:769`  
**Sostituito da:** `scf_plugin_list`  
**Rimosso in:** `3.4.0`

Elenca i plugin disponibili per download diretto (esclude `mcp_only`).
Il payload include `deprecated: true`, `removal_target_version`, `migrate_to`.

**Parametri:** nessuno

---

### `scf_install_plugin` ⚠️ Deprecated

**File:** `spark/boot/tools_plugins.py:846`  
**Sostituito da:** `scf_plugin_install`  
**Rimosso in:** `3.4.0`

Scarica un plugin direttamente in `.github/` senza tracciamento in `.spark-plugins`.
Il payload include `deprecated: true`.

**Parametri:** `package_id: str`, `version: str = "latest"`, `workspace_root: str = ""`, `overwrite: bool = False`

---

## 9. Risorse

### `scf_read_resource`

**File:** `spark/boot/tools_resources.py:110`

Legge il contenuto di una risorsa MCP (engine o override).

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `uri` | `str` | — | URI nel formato `{type}://{name}` |
| `source` | `str` | `"auto"` | `auto` (override > engine), `engine`, `override` |

**Risposta:**
```json
{ "success": true, "uri": "agents://spark-assistant", "source": "engine", "path": "...", "content": "..." }
```

---

### Resource Tool — gruppo `*_resource`

Questi tool restituiscono contenuto e metadati per una singola risorsa
via URI `{type}://{name}`. Differiscono da `scf_get_*` (che usa l'inventory
FrameworkInventory) perché passano dal `McpResourceRegistry` e coprono
solo override e store.

| Tool | File | Parametro | Descrizione |
|------|------|-----------|-------------|
| `scf_get_skill_resource(name)` | `tools_resources.py:170` | `name: str` | Skill via `skills://` URI |
| `scf_get_instruction_resource(name)` | `tools_resources.py:190` | `name: str` | Instruction via `instructions://` URI |
| `scf_get_agent_resource(name)` | `tools_resources.py:210` | `name: str` | Agente via `agents://` URI |
| `scf_get_prompt_resource(name)` | `tools_resources.py:230` | `name: str` | Prompt via `prompts://` URI |

**Risposta tipo:**
```json
{ "name": "spark-assistant", "path": "...", "content": "...", "mcp_uri": "agents://spark-assistant", "mime_type": "text/markdown" }
```

---

### Resource Tool — gruppo `list_*` / `get_*`

Questi tool usano `FrameworkInventory` e coprono risorse dal workspace fisico
e dallo store engine. `scf_get_agent` aggiunge il campo `source_warning` se
l'agente è trovato nel workspace fisico ma non nel registry engine.

| Tool | File | Parametri | Descrizione |
|------|------|-----------|-------------|
| `scf_list_agents()` | `tools_resources.py:250` | — | Tutti gli agenti SCF scoperti |
| `scf_get_agent(name)` | `tools_resources.py:256` | `name: str` | Agente per nome (case-insensitive) |
| `scf_list_skills()` | `tools_resources.py:281` | — | Tutte le skill SCF scoperte |
| `scf_get_skill(name)` | `tools_resources.py:287` | `name: str` | Skill per nome (suffisso `.skill` opzionale) |
| `scf_list_instructions()` | `tools_resources.py:302` | — | Tutte le instruction SCF scoperte |
| `scf_get_instruction(name)` | `tools_resources.py:308` | `name: str` | Instruction per nome (suffisso `.instructions` opzionale) |
| `scf_list_prompts()` | `tools_resources.py:323` | — | Tutti i prompt SCF scoperti (read-only) |
| `scf_get_prompt(name)` | `tools_resources.py:329` | `name: str` | Prompt per nome (suffisso `.prompt` opzionale) |

**Risposta `scf_list_*`:**
```json
{ "count": 13, "agents": [{ "name": "spark-assistant", "path": "...", "summary": "..." }] }
```

**Risposta `scf_get_*`:**
```json
{ "name": "spark-assistant", "path": "...", "content": "..." }
```

---

## 10. Policy / Stato

### `scf_get_project_profile`

**File:** `spark/boot/tools_policy.py:50`

Restituisce il contenuto di `project-profile.md`, metadati e stato di
inizializzazione. Se `initialized: false`, aggiunge `warning` con istruzione.

**Parametri:** nessuno

---

### `scf_get_global_instructions`

**File:** `spark/boot/tools_policy.py:65`

Restituisce il contenuto e i metadati di `copilot-instructions.md`.

**Parametri:** nessuno

---

### `scf_get_model_policy`

**File:** `spark/boot/tools_policy.py:75`

Restituisce il contenuto e i metadati di `model-policy.instructions.md`.

**Parametri:** nessuno

---

### `scf_get_framework_version`

**File:** `spark/boot/tools_policy.py:88`

Restituisce la versione del motore e le versioni dei pacchetti installati.

**Parametri:** nessuno

**Risposta:**
```json
{ "engine_version": "3.3.0", "packages": { "spark-base": "1.7.3" } }
```

---

### `scf_get_workspace_info`

**File:** `spark/boot/tools_policy.py:96`

Restituisce i path del workspace, lo stato di inizializzazione e il conteggio
degli asset SCF scoperti.

**Parametri:** nessuno

---

### `scf_get_runtime_state`

**File:** `spark/boot/tools_policy.py:101`

Legge lo stato runtime dell'orchestratore dal workspace corrente
(`orchestrator-state.json` nella directory runtime).

**Parametri:** nessuno

**Risposta:**
```json
{ "github_write_authorized": false, "session_id": null }
```

---

### `scf_update_runtime_state`

**File:** `spark/boot/tools_policy.py:106`

Aggiorna selettivamente lo stato runtime dell'orchestratore nel workspace.

**Parametri:**

| Parametro | Tipo | Descrizione |
|-----------|------|-------------|
| `patch` | `dict[str, Any]` | Campi da aggiornare (merge parziale) |

**Esempio:** `scf_update_runtime_state({"github_write_authorized": true})`

---

### `scf_get_update_policy`

**File:** `spark/boot/tools_policy.py:111`

Restituisce la policy di update del workspace usata per le operazioni sui file SCF.

**Parametri:** nessuno

**Risposta:**
```json
{
  "success": true,
  "policy": { "auto_update": false, "default_mode": "ask", "mode_per_package": {} },
  "path": ".github/user-prefs.json",
  "source": "file"
}
```

Valori `source` possibili: `"file"`, `"default_missing"`, `"default_corrupt"`.

---

### `scf_set_update_policy`

**File:** `spark/boot/tools_policy.py:122`

Crea o aggiorna la policy di update del workspace in `user-prefs.json`.

**Parametri:**

| Parametro | Tipo | Default | Descrizione |
|-----------|------|---------|-------------|
| `auto_update` | `bool` | — | Abilita/disabilita aggiornamento automatico |
| `default_mode` | `str \| None` | `None` | `ask`, `integrative`, `replace`, `conservative` |
| `mode_per_package` | `dict[str, str] \| None` | `None` | Override per pacchetto |
| `mode_per_file_role` | `dict[str, str] \| None` | `None` | Override per ruolo file SCF |

---

## 11. CLI — Entry Points

Il layer CLI fornisce accesso diretto al motore SPARK da terminale,
indipendentemente dal canale MCP. Utile per inizializzazione workspace,
gestione pacchetti e installazione plugin in ambienti senza VS Code attivo.
Accessibile da tastiera, senza dipendenze decorative, compatibile con screen reader.

### Entry Point Disponibili

| Comando | File | Descrizione |
|---------|------|-------------|
| `python spark_launcher.py` | `spark_launcher.py` | Avvio diretto: flusso primo avvio e menu principale |
| `python -m spark.cli` | `spark/cli/__init__.py` | Alternativa modulo Python; stesso comportamento di `spark_launcher.py` |
| `python scripts/scf [init]` | `scripts/scf` | Launcher con shebang (`#!/usr/bin/env python3`); Linux/macOS diretto, Windows con `py scripts/scf` |
| `python scripts/scf_universal.py` | `scripts/scf_universal.py` | Universal v5.2: auto-trova il motore risalendo la directory tree; gestisce setup venv automatico |

---

### Flusso Primo Avvio

**File:** `spark/cli/startup.py`

Il sentinel globale `~/.spark/.scf-init-done` determina se mostrare la guida
introduttiva al primo lancio:

- **Sentinel assente** → `run_startup_flow()` mostra il messaggio di benvenuto.
  L'utente sceglie:
  - `1` — salva il sentinel e accede al menu principale
  - `0` — salta (sentinel non scritto; la guida viene riproposta al prossimo lancio)
- **Sentinel presente** → accesso diretto al menu principale

Il workspace scelto viene persistito in `~/.spark/config.json`
(scrittura atomica tramite file `.tmp` + rename).

---

### Menu Principale

**File:** `spark/cli/main.py`

`KeyboardInterrupt` e `EOFError` vengono intercettati con uscita pulita
(`\nUscita.` + `sys.exit(0)`).

| Opzione | Azione | Delegato a |
|---------|--------|------------|
| `1` | Inizializza nuovo workspace | `InitManager` |
| `2` | Gestisci pacchetti installati | `PackageManager` |
| `3` | Sfoglia e installa plugin dal registro | `RegistryManager` |
| `4` | Verifica e applica aggiornamenti | `_cmd_updates()` |
| `5` | Diagnostica e stato sistema | `_cmd_diagnostics()` |
| `0` | Esci | — |

---

### `InitManager` — Sequenza 4+1 Step

**File:** `spark/cli/init_manager.py`

Wizard di inizializzazione workspace. Richiede il path target (default: `cwd`;
`0` = annulla; max 3 tentativi su percorso non scrivibile). Ogni operazione è
idempotente: le strutture già presenti non vengono sovrascritte.

| Step | Descrizione |
|------|-------------|
| `[1/4]` | Creazione struttura `.github/` nel workspace target |
| `[2/4]` | Trasferimento `workspace_files` di spark-ops con rollback atomico su errore |
| `[3/4]` | Scrittura/aggiornamento `.vscode/mcp.json` con configurazione server MCP |
| `[4/4]` | Emissione segnale reload |
| `[5/5]` (opzionale) | Proposta apertura VS Code tramite `subprocess` |

---

### `PackageManager` — Sotto-menu Pacchetti

**File:** `spark/cli/package_manager.py`

Chiama `os.system("cls"/"clear")` prima di ogni visualizzazione menu.
Dopo ogni operazione (opzioni 1–4): `input("Premi Invio per continuare...")`.

| Opzione | Azione |
|---------|--------|
| `1` | Elenca pacchetti installati |
| `2` | Installa pacchetto da store locale |
| `3` | Rimuovi pacchetto |
| `4` | Reinstalla / forza aggiornamento |
| `0` | Torna al menu principale |

---

### `RegistryManager` — Sotto-menu Plugin Remoti

**File:** `spark/cli/registry_manager.py`

Registry URL: `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json`
(timeout HTTP: 10 s). Graceful degradation se il registro non è raggiungibile.
Dopo ogni operazione (opzioni 1–4): `input("Premi Invio per continuare...")`.

| Opzione | Azione |
|---------|--------|
| `1` | Sfoglia plugin disponibili (registry remoto) |
| `2` | Installa plugin dal registro |
| `3` | Verifica aggiornamenti plugin installati |
| `4` | Applica aggiornamenti disponibili |
| `0` | Torna al menu principale |

---

### `scf_universal.py` — Auto-detect Launcher v5.2

**File:** `scripts/scf_universal.py`

Launcher zero-touch per esecuzione da qualsiasi directory. Flusso di boot:

1. Trova `spark-framework-engine.py` risalendo la directory tree
2. Auto-setup `.venv` + dipendenze engine se non disponibili (stdlib: `venv` + `pip`)
3. Se venv creato: riavvia con il Python del venv
4. Aggiunge `engine_root` a `sys.path`
5. Rileva `workspace_root` (esplicito, locale, fallback `cwd`)
6. Chiama `run_wizard(cwd=workspace_root)`

Idempotente: sentinel `.scf-init-done` previene wizard duplicate;
`.scf-deps-ready` previene reinstallazione deps.

---

## Note Generali

### Formato URI risorse

```
{type}://{name}
```

Dove `type` è uno di: `agents`, `prompts`, `skills`, `instructions`.

**Fonte:** `spark/core/constants.py` → `_RESOURCE_TYPES = ("agents", "prompts", "skills", "instructions")`

### Autorizzazione scritture `.github/`

Prima di qualsiasi scrittura sotto `.github/`, i tool verificano:

```json
{ "github_write_authorized": true }
```

in `scf_get_runtime_state()`. Se `false`, il tool ritorna:

```json
{ "success": false, "error": "github_write_authorized=False: scrittura su .github/ non autorizzata.", "authorization_required": true }
```

Attiva con: `scf_update_runtime_state({"github_write_authorized": true})`

### Tool deprecati

| Tool (deprecated) | Sostituito da | Removal target |
|-------------------|---------------|----------------|
| `scf_list_plugins()` | `scf_plugin_list()` | `3.4.0` |
| `scf_install_plugin()` | `scf_plugin_install()` | `3.4.0` |

I tool deprecati restituiscono `deprecated: true` e `migrate_to` nel payload.
