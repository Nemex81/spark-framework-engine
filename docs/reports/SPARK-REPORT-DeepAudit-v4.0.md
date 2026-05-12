# SPARK Deep Code Audit v4.0

Data audit: 2026-05-12
Branch: workspace-slim-registry-sync-20260511
Scope: Universe v3.0 + Registry U2 v1.0
Mode: read-only audit (no code implementation)

## Executive Summary

Audit completato file-by-file su:
- spark/boot/tools_plugins.py
- spark/boot/tools_resources.py
- spark/boot/sequence.py
- spark/boot/tools_registry_client.py

Stato runtime verificato con test live:
- 28 passed: test_registry_u2_client + test_tools_registry_client
- 4 passed: test_spark_ops_decoupling_manifest
- 1 passed: test_server_stdio_smoke
- 578 passed: suite non-live completa

Verdetto: PASS con gap tecnici da pianificare in v4.1 (1 P0, 3 P1, 2 P2, 1 P3).

Confidence: 0.96

---

## FASE 1 - Inventory (file e dipendenze)

### Import graph essenziale

- tools_plugins.py
  - dipende da tools_registry_client.find_remote_package
  - dipende da RegistryClient
  - dipende da PluginManagerFacade
  - usa download_plugin/list_available_plugins legacy compat

- tools_resources.py
  - dipende da FrameworkInventory / EngineInventory
  - dipende da McpResourceRegistry
  - dipende da _REGISTRY_CACHE_FILENAME per registry_hint U2

- sequence.py
  - dipende da WorkspaceLocator, FrameworkInventory
  - dipende da validate_engine_manifest / resolve_runtime_dir
  - dipende da migrazione runtime e bootstrap spark-ops files

- tools_registry_client.py
  - dipende da RegistryClient.fetch_if_stale
  - centralizza TTL cache, force_refresh e annotazione U1/U2

---

## FASE 2 - File-by-File dissezione

### 1) spark/boot/tools_plugins.py

Punti confermati:
- routing U2 list remote con TTL via fetch_if_stale: linee 403-483
- install remoto U2 con reject mcp_only: linee 490-731
- guard base path traversal (solo controllo ..): linea 656
- enforcement HTTPS repo/raw: linee 630 e 672

Osservazioni tecniche:
- from_cache può risultare semanticalmente ambiguo: dopo un refresh remoto, is_cache_fresh ritorna true e from_cache può apparire true anche se la rete è stata usata nella stessa richiesta (linea 431).
- install remoto usa cache del workspace engine ctx.github_root, non workspace_root target (linee 540-545). In multi-workspace il metadata cache può riferirsi a un altro workspace.
- controllo path non blocca path assoluti su Windows (es. C:/...): dest = github_root / github_rel può uscire da .github quando github_rel è assoluto (linee 656-661).

### 2) spark/boot/tools_resources.py

Punti confermati:
- detect U1/U2 basato su percorso relativo a packages_root: linee 318-324 (agent), 404-410 (prompt)
- U2 hint da cache locale: _build_u2_registry_hint linee 85-124
- divergenza nota tra scf_get_agent e scf_get_agent_resource già documentata in commento interno: linee 328-336

Osservazioni tecniche:
- hint update_available usa inequality stringa versione, non confronto semver (linee 117-120).
- dipendenza diretta da inventory._ctx.github_root in tool getter (linea 325) rende il metodo più fragile ai refactor del contesto interno.

### 3) spark/boot/sequence.py

Punti confermati:
- migrazione runtime protetta da sessioni merge attive: linee 68-77
- spark-ops workspace_files copiati solo se dest assente (idempotenza presence-based): linee 165-171
- copy eseguito post ensure_minimal_bootstrap: linee 253 e 262

Osservazioni tecniche:
- idempotenza su sola esistenza file, non su contenuto/hash: aggiornamenti del file sorgente non vengono propagati se file esiste già (linea 165).
- potenziale race write in avvii concorrenti: check then copy non è atomico (linee 165-180).

### 4) spark/boot/tools_registry_client.py

Punti confermati:
- TTL centralizzato default 3600: linea 35
- force_refresh tradotto in ttl=0: linea 87
- helper di annotazione universe centralizzati: linee 91-131
- lookup case-insensitive: linee 134-169

Osservazioni tecniche:
- get_remote_packages intercetta solo RuntimeError e ritorna [] (linee 113-121): errori non RuntimeError vengono propagati al chiamante.

---

## FASE 3 - Flussi End-to-End (diagramma testuale)

### Flusso A: scf_get_agent

Richiesta: scf_get_agent(name)
1. inventory.list_agents
2. match per nome (case-insensitive)
3. detection universo:
   - U1 se path agente è sotto engine_root/packages
   - U2 altrimenti (workspace)
4. se U2: tenta registry_hint da cache locale
5. ritorna payload con content + metadata + universe + source_package

Fallback chain:
- trovato in inventory ma non in registry MCP: source_warning aggiunto
- non trovato: success false + available list

### Flusso B: scf_plugin_list_remote

Richiesta: scf_plugin_list_remote(force_refresh)
1. crea/riusa RegistryClient
2. ttl=0 se force_refresh, altrimenti 3600
3. fetch_if_stale
4. annota pacchetti U1/U2 su delivery_mode
5. ritorna packages + counts + from_cache

### Flusso C: scf_plugin_install_remote

Richiesta: scf_plugin_install_remote(pkg_id, workspace_root, overwrite, force_refresh)
1. resolve workspace target
2. find_remote_package su cache registry
3. reject se mcp_only (U1)
4. fetch package-manifest remoto
5. per ogni plugin_file:
   - guard path traversal su ..
   - skip se file già esiste e overwrite false
   - download raw HTTPS
   - write su .github target
6. ritorna files_written/files_skipped/errors

### Flusso D: boot sequence spark-ops

Avvio engine _build_app
1. resolve workspace + runtime dir
2. migra runtime legacy se possibile
3. register resources/tools
4. ensure_minimal_bootstrap
5. _ensure_spark_ops_workspace_files (copy idempotente)
6. onboarding first-run

---

## FASE 4 - Gap critici (P0-P3)

| Priority | File:Line | Gap | Impatto | Fix Cost |
|---|---|---|---|---|
| P0 | spark/boot/tools_plugins.py:656-661 | Path guard incompleto: non blocca path assoluti/drive-rooted; possibile write fuori da .github in scenari crafted manifest | Security boundary break (filesystem write escape) | 30-45 min |
| P1 | spark/boot/tools_plugins.py:431 | from_cache semantica ambigua dopo fetch_if_stale; telemetria può essere fuorviante | Diagnostica operativa e observability inaccurate | 15-20 min |
| P1 | spark/boot/tools_plugins.py:540-545 | Cache registry letta da ctx.github_root anche quando workspace_root target è diverso | In multi-workspace possibile incoerenza cache/context | 20-30 min |
| P1 | spark/boot/tools_resources.py:117-120 | update_available usa confronto stringa != (non semver-aware) | False positive/negative su versioning hint | 20 min |
| P2 | spark/boot/sequence.py:165 | Idempotenza presence-based: update sorgente non propagato su file già presente | Drift silenzioso di asset bootstrap | 30-60 min |
| P2 | spark/boot/sequence.py:165-180 | Check-then-copy non atomico; race in bootstrap concorrente | Possibili copy conflict in startup parallelo | 30-45 min |
| P3 | spark/boot/tools_registry_client.py:113-121 | get_remote_packages gestisce solo RuntimeError, non uniforma tutte le failure class | Robustezza error envelope non omogenea | 15 min |

---

## FASE 5 - Verify runtime (live)

Comandi eseguiti:
- pytest tests/test_registry_u2_client.py tests/test_tools_registry_client.py -q --tb=short
  - 28 passed
- pytest tests/test_spark_ops_decoupling_manifest.py -q --tb=short
  - 4 passed
- pytest tests/test_server_stdio_smoke.py -q --tb=short
  - 1 passed
- pytest tests/ -q --ignore=tests/test_integration_live.py --tb=short
  - 578 passed

Esito gate runtime: PASS

---

## FASE 6 - Proposte v4.1 (no implementation)

### Proposta 1 (P0): harden path safety su install remoto

Snippet proposta:
- normalizzare github_rel
- rifiutare path assoluti, drive-letter, root-anchored
- verificare containment finale con resolved path sotto github_root

Test aggiuntivi:
- manifest con file path C:/temp/x.md deve essere rifiutato
- manifest con /etc/passwd deve essere rifiutato
- manifest con .. già coperto, mantenere test

### Proposta 2 (P1): from_cache accurato

Snippet proposta:
- acquisire flag cache_fresh_before_fetch
- from_cache = cache_fresh_before_fetch and not force_refresh
- evitare verifica freshness post-fetch

Test aggiuntivi:
- cache stale + rete ok => from_cache false
- cache fresh => from_cache true

### Proposta 3 (P1): cache scope coerente col target workspace

Snippet proposta:
- quando workspace_root è valorizzato, usare quel .github per registry client/cache
- mantenere fallback su ctx.github_root per backward compat

Test aggiuntivi:
- due workspace distinti con cache diverse
- install su workspace B non deve leggere cache di A

### Proposta 4 (P1): semver compare per registry_hint

Snippet proposta:
- usare helper version compare centralizzato
- update_available true solo se latest > installed

Test aggiuntivi:
- 1.10.0 vs 1.2.0
- prerelease handling

### Proposta 5 (P2): bootstrap file sync policy

Snippet proposta:
- opzionale hash compare + overwrite controlled per workspace_files
- default conservativo invariato

Test aggiuntivi:
- sorgente aggiornata + target esistente invariato
- modalità sync abilitata aggiorna solo file non user-modified

---

## CHANGELOG proposals (non applicate)

Sezione proposta per Unreleased:
- Added: Deep audit v4.0 su flussi U1/U2 e registry cache con gap classification P0-P3
- Proposed: hardening path containment in scf_plugin_install_remote
- Proposed: accurate from_cache telemetry in scf_plugin_list_remote
- Proposed: workspace-scoped registry cache for remote install flows
- Proposed: semver-aware update_available in U2 registry_hint
- Proposed: optional hash-based sync policy for spark-ops workspace_files

---

## FASE 7 - Conclusione

Audit puro completato senza modifiche al codice runtime.

Checklist autonomous:
- FASE 1-5 complete: SI
- Flussi mappati end-to-end: SI
- Gap P0 identificati: SI
- Verify runtime eseguito: SI
- Report strutturato: SI

Confidence finale: 0.96
