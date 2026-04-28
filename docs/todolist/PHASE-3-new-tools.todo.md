# Fase 3 — Tool MCP override (4 nuovi tool)
# Dipende da: Fase 2
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_override_tools.py (nuovo)

## Prerequisiti

- [ ] Fase 2 completata
- [ ] `McpResourceRegistry` operativa al boot
- [ ] `ManifestManager.write_override()` da implementare prima di 3.3

## Task

- [ ] 3.1 Estendere `ManifestManager` con metodo `write_override`
      File: `spark-framework-engine.py`
      Riga partenza: 1391.
      Signature:
      `def write_override(self, workspace: Path, resource_type: str,
                          name: str, content: str) -> Path`.
      Verifica `github_write_authorized`, scrive su
      `.github/overrides/{type}/{name}.md`, aggiorna `.scf-manifest`.

- [ ] 3.2 Estendere `ManifestManager` con metodo `drop_override`
      File: `spark-framework-engine.py`
      Signature:
      `def drop_override(self, workspace, resource_type, name) -> bool`.
      Rimuove file e aggiorna `.scf-manifest`.

- [ ] 3.3 Tool `scf_list_resources`
      File: `spark-framework-engine.py`
      Punto di inserimento: vicino a `scf_list_agents` (riga 2589).
      Signature:
      `async def scf_list_resources(resource_type: str,
                                    package_id: str = None) -> dict`.
      Risposta: `{"type", "items": [{"name", "has_override",
                                     "package", "version"}]}`.

- [ ] 3.4 Tool `scf_read_resource`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_read_resource(uri: str,
                                   source: str = "auto") -> dict`.
      `source`: "auto" | "engine" | "override".
      Errore se `source="override"` e non esiste.

- [ ] 3.5 Tool `scf_override_resource`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_override_resource(uri: str, content: str) -> dict`.
      Logica: parse uri → (type, name), verifica risorsa
      registrata, chiama `manifest_manager.write_override()`,
      registra override in registry.

- [ ] 3.6 Tool `scf_drop_override`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_drop_override(uri: str) -> dict`.
      Logica: rimuove override file, deregistra dal registry.

- [ ] 3.7 Aggiornare contatore tool registrati
      Da 36 (post-Fase 0) a 40.

- [ ] 3.8 Test suite override tools
      File: `tests/test_override_tools.py`
      Casi: ciclo completo override → read → drop, lettura
      `source="engine"` ignora override, `source="override"`
      errore se assente, write fallisce se
      `github_write_authorized=False`.

## Test di accettazione

- [ ] `scf_list_resources("agents")` lista tutti gli agenti con
      flag `has_override` corretto.
- [ ] `scf_override_resource("agents://X", "...")` crea
      `.github/overrides/agents/X.md`.
- [ ] `scf_read_resource("agents://X", "auto")` ritorna override.
- [ ] `scf_read_resource("agents://X", "engine")` ritorna engine.
- [ ] `scf_drop_override("agents://X")` rimuove file e
      `scf_read_resource` torna a engine.

## Note tecniche

- Parsing URI: helper `_parse_resource_uri(uri) -> (type, name)`.
  Rifiuta URI non riconosciuti con isError MCP.
- L'override viene SEMPRE letto da workspace, mai cachato in RAM
  (il file può essere modificato da editor utente).
- I tool override sono NO-OP su URI `scf://` (runtime state,
  workspace-info, ecc.).
