# Fase 5 — WorkspaceLocator + RegistryClient cache + CLI flag
# Dipende da: Fase 2
# Effort stimato: S
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_workspace_locator.py (estensione)

## Prerequisiti

- [ ] Fase 2 completata
- [ ] `McpResourceRegistry` operativa

## Task

- [ ] 5.1 Aggiungere metodo `get_engine_cache_dir()`
      File: `spark-framework-engine.py`
      Riga partenza: 458 (`class WorkspaceLocator`).
      Logica: tenta `engine_dir/cache/`, se write KO fallback su
      `%APPDATA%\spark-engine\cache\` (Windows) o
      `~/.cache/spark-engine/` (Unix).
      Crea directory se assente.

- [ ] 5.2 Aggiungere metodo `get_override_dir(workspace, type)`
      File: `spark-framework-engine.py`
      Logica: ritorna
      `workspace/.github/overrides/{type}/`. Crea se non esiste e
      `github_write_authorized=True`.

- [ ] 5.3 Implementare CLI flag `--workspace`
      File: `spark-framework-engine.py`
      Punto: parsing argv all'avvio (cerca pattern `sys.argv` o
      `argparse`).
      Se presente, override del default workspace. Validazione:
      path esistente o errore.

- [ ] 5.4 Aggiornare `RegistryClient` per usare nuova cache path
      File: `spark-framework-engine.py`
      Riga partenza: 2277.
      Sostituire path cache con
      `WorkspaceLocator.get_engine_cache_dir() / "registry-cache.json"`.

- [ ] 5.5 Test get_engine_cache_dir
      File: `tests/test_workspace_locator.py`
      Casi: cartella scrivibile → engine_dir/cache, fallback con
      mock `Path.touch` che fallisce.

- [ ] 5.6 Test get_override_dir
      File: `tests/test_workspace_locator.py`
      Casi: directory creata correttamente, lock se
      `github_write_authorized=False`.

- [ ] 5.7 Test CLI flag --workspace
      File: `tests/test_workspace_locator.py`
      Lancia engine con `--workspace tmp_path` e verifica
      `WorkspaceLocator.workspace_root == tmp_path`.

## Test di accettazione

- [ ] `--workspace C:\path\reale` → locator usa il path indicato.
- [ ] Cache scritta in `engine_dir/cache/registry-cache.json`.
- [ ] Fallback cache funzionante quando engine_dir read-only.
- [ ] `get_override_dir(ws, "agents")` crea
      `ws/.github/overrides/agents/` se manca.

## Note tecniche

- Il flag `--workspace` deve coesistere con `WORKSPACE_FOLDER` env
  (Copilot). Priorità: CLI > env > working directory.
- La cache vecchia (`workspace/.scf-registry-cache.json`) non va
  cancellata in questa fase: `scf_migrate_workspace` (Fase 0) la
  sposta. Engine v3.x ignora il file vecchio.
- Su Windows: `os.environ["APPDATA"]`. Su Unix:
  `os.path.expanduser("~/.cache")`.
