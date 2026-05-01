# Fase 2 — PackageResourceStore + McpResourceRegistry
# Dipende da: Fase 1
# Effort stimato: L
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_resource_store.py (nuovo)
#   - spark-framework-engine/tests/test_resource_registry.py (nuovo)

## Prerequisiti

- [x] Fase 1 completata
- [x] `engine-manifest.json` presente e validato
- [x] Tutti i package-manifest a schema 3.0

## Task

- [x] 2.1 Implementare `PackageResourceStore`
      File: `spark-framework-engine.py`
      Punto di inserimento: dopo `RegistryClient` (riga 2277),
      prima di `class SparkFrameworkEngine` (riga 2389).
      Metodi: `__init__(engine_dir: Path)`,
              `resolve(package_id, resource_type, name) -> Path`,
              `list_resources(package_id, resource_type) -> list[str]`,
              `verify_integrity(package_id) -> dict`,
              `has_workspace_override(workspace, type, name) -> bool`.
      Path base: `engine_dir/packages/{package_id}/.github/{type}/`.

- [x] 2.2 Implementare `McpResourceRegistry`
      File: `spark-framework-engine.py`
      Punto di inserimento: subito dopo `PackageResourceStore`.
      Struttura interna: dict URI → {engine: Path, override: Path | None,
      package: str, resource_type: str}.
      Metodi: `register(uri, engine_path, package, type)`,
              `register_override(uri, override_path)`,
              `resolve(uri) -> Path` (override > engine),
              `resolve_engine(uri) -> Path`,
              `list_by_type(resource_type) -> list[str]`,
              `has_override(uri) -> bool`.

- [x] 2.3 Estendere `FrameworkInventory.__init__` per popolare
      `McpResourceRegistry` al boot
      File: `spark-framework-engine.py`
      Riga partenza: 1144.
      Logica: itera engine-manifest + package manifests, per ogni
      risorsa chiama `registry.register(uri, path, package, type)`.

- [x] 2.4 Aggiungere scan di `.github/overrides/` in
      `FrameworkInventory`
      File: `spark-framework-engine.py`
      Logica: dopo registrazione engine + pacchetti, scan
      `workspace/.github/overrides/{type}/*.md` e chiama
      `registry.register_override(uri, path)`.

- [x] 2.5 Test PackageResourceStore
      File: `tests/test_resource_store.py`
      Casi: resolve corretto, list_resources, integrity check con
      file modificato.

- [x] 2.6 Test McpResourceRegistry
      File: `tests/test_resource_registry.py`
      Casi: register + resolve, override priority, has_override,
      list_by_type, resolve_engine.

- [x] 2.7 Test integrazione FrameworkInventory boot
      File: `tests/test_engine_inventory.py` (estendere)
      Verifica registry popolata correttamente con
      engine-manifest + 3 pacchetti.

## Test di accettazione

- [x] `PackageResourceStore.resolve("scf-master-codecrafter",
      "agents", "code-Agent-Code")` ritorna Path esistente.
- [x] `McpResourceRegistry.resolve("agents://code-Agent-Code")`
      ritorna engine path se nessun override.
- [x] Dopo `register_override`, `resolve` ritorna override path.
- [x] `verify_integrity` rileva SHA mismatch su file modificato.

## Note tecniche

- Le due classi sono pure-data (no I/O su MCP). Tutte le
  operazioni filesystem passano da metodi espliciti.
- Thread safety: registry è populated solo al boot e su tool
  override/drop. Le letture (resolve) non richiedono lock.
- Path engine: usare sempre `pathlib.Path` con `.resolve()`.
- Nomi senza estensione negli URI: `agents://code-Agent-Code`
  mappa a `code-Agent-Code.agent.md` o `code-Agent-Code.md` a
  seconda della convenzione del pacchetto. Il registry tiene
  traccia del path completo.
