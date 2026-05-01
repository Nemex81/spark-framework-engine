# Fase 3 — Tool MCP override (4 nuovi tool)
# Dipende da: Fase 2
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_override_tools.py (nuovo)

## Prerequisiti

- [x] Fase 2 completata
- [x] `McpResourceRegistry` operativa al boot
- [x] `ManifestManager.write_override()` da implementare prima di 3.3

## Task

- [x] 3.1 Estendere `ManifestManager` con metodo `write_override`
      File: `spark-framework-engine.py`
      Riga partenza: 1391.
      Signature:
      `def write_override(self, workspace: Path, resource_type: str,
                          name: str, content: str) -> Path`.
      Verifica `github_write_authorized`, scrive su
      `.github/overrides/{type}/{name}.md`, aggiorna `.scf-manifest`.

- [x] 3.2 Estendere `ManifestManager` con metodo `drop_override`
      File: `spark-framework-engine.py`
      Signature:
      `def drop_override(self, workspace, resource_type, name) -> bool`.
      Rimuove file e aggiorna `.scf-manifest`.

- [x] 3.3 Tool `scf_list_overrides`
      File: `spark-framework-engine.py`
      Punto di inserimento: vicino a `scf_list_agents` (riga 2589).
      Signature:
      `async def scf_list_overrides(resource_type: str | None = None)
        -> dict[str, Any]`.
      Risposta: `{"items": [{"uri", "type", "name", "path",
                              "sha256"}]}`.
      Capability "lista risorse complete con flag has_override"
      è già coperta dai tool esistenti `scf_list_agents`,
      `scf_list_skills`, `scf_list_instructions`, `scf_list_prompts`
      che in v3.0 verranno estesi col campo `has_override` (Fase 4).

- [x] 3.4 Tool `scf_read_resource`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_read_resource(uri: str,
                                   source: str = "auto") -> dict`.
      `source`: "auto" | "engine" | "override".
      Errore se `source="override"` e non esiste.

- [x] 3.5 Tool `scf_override_resource`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_override_resource(uri: str, content: str) -> dict`.
      Logica: parse uri → (type, name), verifica risorsa
      registrata, chiama `manifest_manager.write_override()`,
      registra override in registry.

- [x] 3.6 Tool `scf_drop_override`
      File: `spark-framework-engine.py`
      Signature:
      `async def scf_drop_override(uri: str) -> dict`.
      Logica: rimuove override file, deregistra dal registry.

- [x] 3.7 Aggiornare contatore tool registrati
      Da 36 (post-Fase 0) a 40.

- [x] 3.8 Test suite override tools
      File: `tests/test_override_tools.py`
      Casi: ciclo completo override → read → drop, lettura
      `source="engine"` ignora override, `source="override"`
      errore se assente, write fallisce se
      `github_write_authorized=False`.

## Test di accettazione

- [x] `scf_list_overrides()` ritorna lista vuota su workspace pulito.
- [x] `scf_list_overrides("agents")` filtra per tipo.
- [x] `scf_override_resource("agents://X", "...")` crea
      `.github/overrides/agents/X.md`.
- [x] `scf_read_resource("agents://X", "auto")` ritorna override.
- [x] `scf_read_resource("agents://X", "engine")` ritorna engine.
- [x] `scf_drop_override("agents://X")` rimuove file e
      `scf_read_resource` torna a engine.

## Note tecniche

- Parsing URI: helper `_parse_resource_uri(uri) -> (type, name)`.
  Rifiuta URI non riconosciuti con isError MCP.
- L'override viene SEMPRE letto da workspace, mai cachato in RAM
  (il file può essere modificato da editor utente).
- I tool override sono NO-OP su URI `scf://` (runtime state,
  workspace-info, ecc.).
