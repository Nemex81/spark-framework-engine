# spark/registry/ — Registry MCP e Risorse

Questo package gestisce la scoperta, il routing e l'accesso alle risorse SCF:
agenti, skill, instruction e prompt.

---

## Componenti

### `client.py` — RegistryClient

Client HTTP per il registry pubblico SCF.

- URL: `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json`
  (fonte: `spark/core/constants.py` → `_REGISTRY_URL`)
- Metodo principale: `fetch_registry() -> dict`
- Non gestisce autenticazione; accesso pubblico in sola lettura.

---

### `mcp.py` — McpResourceRegistry

Registry in-memory delle risorse MCP dell'engine.
Usato da `ResourceResolver` come fonte primaria durante la risoluzione URI.

**Operazioni principali:**
- `register(uri, path, sha256=None)` — aggiunge/aggiorna una entry
- `get(uri) -> dict | None` — legge una entry per URI
- `list_by_type(resource_type) -> list[dict]` — elenca per tipo
- Supporta override workspace: un'entry di tipo `"override"` ha priorità
  sulle entry engine durante la risoluzione `auto`.

---

### `resolver.py` — ResourceResolver

Risolve URI `{type}://{name}` con la policy override > engine:

1. Cerca nella lista override del `McpResourceRegistry`
2. Se non trovato, cerca nello store engine locale
3. Fallback: `FrameworkInventory` (workspace fisico)

Supporta il parametro `source: "auto" | "engine" | "override"` per forzare
la sorgente senza fallback.

---

### `store.py` — PackageResourceStore

Store engine-locale per pacchetti con `schema_version < "3.0"` (path legacy).
Mantiene le risorse installate in `packages/<pkg>/` con un indice per tipo.

---

### `v3_store.py` — V3PackageResourceStore

Store engine-locale per pacchetti con `schema_version >= "3.0"`.
Differisce da `store.py` per:
- Lettura metadati da `mcp_resources` nel `package-manifest.json`
- Supporto `delivery_mode: "mcp_only"` (zero file nel workspace utente)
- Registrazione automatica di agents, prompts, skills, instructions
  dal manifest senza richiedere file fisici in `.github/`

---

## Flusso di risoluzione URI

```
URI "agents://spark-assistant"
        │
        ▼
McpResourceRegistry.get("agents://spark-assistant")
        │
        ├─ entry di tipo "override"?  →  legge file in .github/ (workspace)
        │
        └─ entry di tipo "engine"?   →  legge file nello store engine
                │
                └─ non trovato?       →  FrameworkInventory (filesystem workspace)
```
