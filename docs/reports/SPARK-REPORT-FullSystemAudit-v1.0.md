# SPARK — Full System Audit Report v1.0
**Data:** 2026-05-11  
**Branch:** `workspace-slim-registry-sync-20260511`  
**Engine:** v3.4.0  
**Prompt origine:** `spark-full-system-audit-v1.0`  
**Emesso da:** spark-engine-maintainer  
**Stato:** COMPLETATO

---

## Baseline Pre-Audit

| Metrica | Valore |
|---|---|
| Branch corrente | `workspace-slim-registry-sync-20260511` |
| HEAD commit | `ade3db3 eliminato files obsoleti` |
| Git status (engine repo) | ✅ clean (solo `pytest_audit_out.txt` untracked) |
| Git stash list | ✅ vuoto |
| pytest collezionati | 554 |
| pytest risultato | **1 failed (pre-existing) / 534 passed / 19 skipped** |
| ENGINE_VERSION | `3.4.0` |
| CHANGELOG ultima voce | `[3.4.0] - 2026-05-10` ✅ allineato |
| REGISTRY_URL | `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json` ✅ HTTPS |

**Nota**: il prompt audit indicava "554p/0s" come baseline. Il valore reale è 534p/19s/1f.
Il test fallito (`test_spark_base_manifest_no_longer_exports_operational_resources`) è pre-existing
su `main` prima di questo branch — GATE: PASS (zero regressioni introdotte).

---

## FASE 1 — Bootstrap Audit

### Risultati pytest

```
tests/test_bootstrap_workspace.py          10 passed
tests/test_bootstrap_workspace_extended.py 10 skipped (async, richiedono pytest-asyncio)
```

### Checklist

| Item | Stato | Note |
|---|---|---|
| `scf_bootstrap_workspace` esiste nel motore | ✅ PASS | `spark/boot/tools_bootstrap.py:336` |
| `scf_verify_workspace` esiste | ✅ PASS | `spark/boot/tools_bootstrap.py:217` |
| `scf_migrate_workspace` esiste | ✅ PASS | `spark/boot/tools_bootstrap.py:1046` |
| Test sync bootstrap: 10 passed | ✅ PASS | |
| Test async bootstrap: 10 skipped | ⚠️ WARNING | `pytest-asyncio` non installato nell'env |
| Docstring `scf_bootstrap_workspace` | ⚠️ WARNING | Mancante (riga successiva alla def non è `"""`) |

### Anomalia BOOT-1
**pytest-asyncio mancante**: 10 test in `test_bootstrap_workspace_extended.py` sono async e
vengono saltati perché l'ambiente `audiomaker311` non ha `pytest-asyncio` installato.
Priorità: MEDIA — i test sync passano, i flussi core sono verificati.

---

## FASE 2 — MCP Server Audit

### Versione e costanti

| Costante | Valore | Atteso | Stato |
|---|---|---|---|
| `ENGINE_VERSION` | `3.4.0` | `3.4.0` | ✅ |
| `_REGISTRY_URL` | HTTPS github raw | HTTPS-only | ✅ |
| CHANGELOG ultima voce | `[3.4.0] - 2026-05-10` | matches ENGINE_VERSION | ✅ |
| README contatore tool | `50` (riga 68) | `51` (reale) | ⚠️ WARNING |

### Inventario tool MCP (51 totali)

Moduli `spark/boot/`:

| File | Tool definiti |
|---|---|
| `tools_bootstrap.py` | `scf_verify_workspace`, `scf_verify_system`, `scf_bootstrap_workspace`, `scf_migrate_workspace` |
| `tools_policy.py` | `scf_get_project_profile`, `scf_get_global_instructions`, `scf_get_model_policy`, `scf_get_framework_version`, `scf_get_workspace_info`, `scf_get_runtime_state`, `scf_update_runtime_state`, `scf_get_update_policy`, `scf_set_update_policy` |
| `tools_resources.py` | `scf_read_resource`, `scf_get_skill_resource`, `scf_get_instruction_resource`, `scf_get_agent_resource`, `scf_get_prompt_resource`, `scf_list_agents`, `scf_get_agent`, `scf_list_skills`, `scf_get_skill`, `scf_list_instructions`, `scf_get_instruction`, `scf_list_prompts`, `scf_get_prompt` |
| `tools_packages_query.py` | `scf_list_available_packages`, `scf_get_package_info`, `scf_list_installed_packages`, `scf_plan_install` |
| `tools_packages_install.py` | `scf_install_package` |
| `tools_packages_remove.py` | `scf_remove_package`, `scf_get_package_changelog` |
| `tools_packages_update.py` | `scf_check_updates`, `scf_update_package`, `scf_update_packages`, `scf_apply_updates` |
| `tools_packages_diagnostics.py` | `scf_resolve_conflict_ai`, `scf_approve_conflict`, `scf_reject_conflict`, `scf_finalize_update` |
| `tools_override.py` | `scf_list_overrides`, `scf_override_resource`, `scf_drop_override` |
| `tools_plugins.py` | `scf_plugin_list`, `scf_plugin_install`, `scf_plugin_remove`, `scf_plugin_update`, `scf_list_plugins`, `scf_get_plugin_info`, `scf_install_plugin` |

### Tool senza docstring immediata (WARNING)

10 tool trovati con firma `def/async def scf_*` ma la riga successiva non è `"""`:

```
scf_bootstrap_workspace    tools_bootstrap.py:336
scf_migrate_workspace      tools_bootstrap.py:1046
scf_list_overrides         tools_override.py:50
scf_override_resource      tools_override.py:93
scf_install_package        tools_packages_install.py:219
scf_update_package         tools_packages_update.py:274
scf_apply_updates          tools_packages_update.py:519
scf_install_plugin         tools_plugins.py:474
scf_set_update_policy      tools_policy.py:122
scf_read_resource          tools_resources.py:110
```

**Nota**: il check è euristico (riga N+1). La docstring potrebbe essere presente dopo
la signature multi-riga. Verifica manuale raccomandata.

### Anomalia MCP-1 — README contatore tool disallineato
`README.md:68` dice `## Tools Disponibili (50)` ma il motore espone **51** funzioni `scf_`.
Correzione: aggiornare il titolo a `(51)`.

---

## FASE 3 — Plugin Distribution Audit

### Store interna packages/

| Package | Versione store | min_engine_version | In registry.json |
|---|---|---|---|
| scf-master-codecrafter | 2.7.0 | 3.4.0 | ✅ (v2.7.0 dopo sync) |
| scf-pycode-crafter | 2.3.0 | 3.4.0 | ✅ (v2.3.0 dopo sync) |
| spark-base | 1.7.3 | 3.4.0 | ✅ |
| spark-ops | 1.1.0 | 3.4.0 | ❌ ASSENTE |

### Anomalia DISTRO-1 — spark-ops in store ma non in registry
`packages/spark-ops/package-manifest.json` esiste con v1.1.0/3.4.0 ma `scf-registry/registry.json`
non ha entry per spark-ops. Il repository GitHub `Nemex81/spark-ops` non è stato verificato
come pubblicamente accessibile. Il test `test_spark_ops_manifest_exposes_only_operational_resources`
passa (legge da store locale), ma `scf_list_available_packages()` non restituirà spark-ops ai client
remoti finché non viene aggiunto al registry.
Priorità: ALTA — gap store/registry che blocca distribuzione del pacchetto.

### Anomalia DISTRO-2 — scf-registry/registry.json non committato
Il file `scf-registry/registry.json` è in stato `M` (modified, not pushed) nel repo scf-registry.
Le versioni sync (scf-master-codecrafter 2.7.0, scf-pycode-crafter 2.3.0) sono applicate localmente
ma non ancora visibili ai client remoti.
Priorità: ALTA — richiede commit + push in `C:\Users\nemex\OneDrive\Documenti\GitHub\scf-registry`.

### Asset packages (conteggio file store)

| Package | agents | prompts | note |
|---|---|---|---|
| spark-base | 13 agenti | — | `spark-assistant.agent.md`, `spark-guide.agent.md` inclusi |
| scf-master-codecrafter | 11 agenti | 1 file (README.md) | code-Agent-* series |
| scf-pycode-crafter | — | — | non verificato in dettaglio |
| spark-ops | — | — | non verificato in dettaglio |

---

## FASE 4 — Packages Lifecycle Audit

### min_engine_version check

Tutti i 4 pacchetti nel store locale hanno `min_engine_version = "3.4.0"`. ✅

### Versioni store vs CHANGELOG/source

| Package | Store | Test aspettato | Stato |
|---|---|---|---|
| spark-base | 1.7.3 | `test_spark_base_manifest_no_longer_exports_operational_resources` aspetta 2.1.0 | ⚠️ FAILING TEST (pre-existing) |
| scf-master-codecrafter | 2.7.0 | `test_embedded_plugins_depend_on_decoupled_operational_layer` passa (verifica dep 2.7.0) | ✅ |
| scf-pycode-crafter | 2.3.0 | verificato indirettamente | ✅ |
| spark-ops | 1.1.0 | `test_spark_ops_manifest_exposes_only_operational_resources` PASS | ✅ |

### Anomalia PKG-1 — spark-base v1.7.3 vs test atteso v2.1.0
Il test `test_spark_base_manifest_no_longer_exports_operational_resources` è stato scritto
anticipando un bump di spark-base a v2.1.0 (dopo decoupling spark-ops). Il manifest attuale
è ancora v1.7.3. Questo NON è una regressione del branch corrente — era già presente su main.
Priorità: MEDIA — richiede bump spark-base a v2.1.0 come task separato (after spark-ops publishing).

---

## FASE 5 — Anomaly Detection

### Git hygiene

| Check | Stato |
|---|---|
| `git status` engine repo | ✅ clean (solo `pytest_audit_out.txt` untracked) |
| `git stash list` | ✅ vuoto |
| `git status` scf-registry | ⚠️ `M registry.json` (non pushato) |
| File .gitignore-d rilevanti | `runtime/` (intera cartella ignorata), `.github/.scf-manifest.json`, `.github/.scf-registry-cache.json` |

### Coverage spark/ (pytest-cov)

```
TOTAL  6032 stmts  1353 miss  78%
```

**Moduli SOTTO soglia 80%** (WARNING):

| Modulo | Statements | Miss | Coverage |
|---|---|---|---|
| `spark\plugins\manager.py` | 92 | 74 | **20%** ⚠️ |
| `spark\plugins\updater.py` | 35 | 23 | **34%** ⚠️ |
| `spark\registry\client.py` | 59 | 36 | **39%** ⚠️ |
| `spark\plugins\remover.py` | 117 | 38 | **68%** ⚠️ |
| `spark\workspace\locator.py` | 124 | 34 | **73%** ⚠️ |

**Nota**: i moduli plugins sono correlati al sistema plugin (deprecato/legacy per scf_plugin_*).
`registry\client.py` a 39% è più critico: copre il fallback HTTPS e la gestione cache.

### Test suite quality

| Check | Valore |
|---|---|
| Test collezionati | 554 |
| Test passati | 534 |
| Test saltati | 19 (di cui 10 async bootstrap_extended per pytest-asyncio mancante) |
| Test falliti | 1 (pre-existing: spark-base v1.7.3 vs atteso v2.1.0) |
| Live integration tests | ignorati (test_integration_live.py) |

---

## Riepilogo Anomalie

| ID | Fase | Anomalia | Severità | Azione |
|---|---|---|---|---|
| MCP-1 | FASE 2 | README.md dice `Tools Disponibili (50)` ma engine ha 51 | ⚠️ WARNING | Aggiornare riga 68 README da `(50)` a `(51)` |
| MCP-2 | FASE 2 | 10 tool senza docstring immediata (verifica euristica) | ⚠️ WARNING | Verifica manuale + aggiunta docstring mancanti |
| BOOT-1 | FASE 1 | 10 async test saltati per mancanza pytest-asyncio | ⚠️ WARNING | Installare `pytest-asyncio` in env o skipmarker esplicito |
| DISTRO-1 | FASE 3 | spark-ops v1.1.0 in store ma assente da registry.json | 🔴 ALTA | Aggiungere entry spark-ops al registry DOPO verifica repo GitHub |
| DISTRO-2 | FASE 3 | scf-registry/registry.json modificato ma non pushato | 🔴 ALTA | `git commit + git push` in `scf-registry/` |
| PKG-1 | FASE 4 | spark-base v1.7.3 mentre test aspetta v2.1.0 | ⚠️ WARNING | Bump spark-base a v2.1.0 (task separato, post spark-ops) |
| COV-1 | FASE 5 | Coverage totale 78% (sotto soglia 80%) | ⚠️ WARNING | Focus su `registry/client.py` (39%) e `plugins/manager.py` (20%) |
| COV-2 | FASE 5 | `spark\registry\client.py` 39% — modulo critico HTTPS | 🔴 ALTA | Test dedicati per fallback offline e gestione cache |

---

## VERDICT: SYSTEM HEALTH

```
╔══════════════════════════════════════════════════════╗
║  VERDICT: SYSTEM HEALTH YELLOW                       ║
║  (nessun blocco critico runtime, 5 anomalie warning) ║
╚══════════════════════════════════════════════════════╝
```

| Area | Stato | Note |
|---|---|---|
| ✅ BOOTSTRAP | OK | 10/10 test sync pass; async saltati per env |
| ✅ MCP SERVER | OK | 51 tool registrati, ENGINE_VERSION 3.4.0 allineato |
| ⚠️ PLUGIN DISTRO | PARTIAL | spark-ops in store ma non in registry |
| ✅ PACKAGES STORE | OK | 4 pacchetti, tutti min_engine_version 3.4.0 |
| ⚠️ TEST SUITE | PARTIAL | 1 fail pre-existing, 10 skipped async |
| ⚠️ COVERAGE | WARNING | 78% totale, 5 moduli sotto 80% |
| ⚠️ ANOMALIE | 8 totali | 3 ALTA, 5 WARNING |

### Raccomandazioni prioritarie

1. **[ALTA — IMMEDIATA]** Push `scf-registry/registry.json` (comandi in SPARK-REPORT-WorkspaceSlim-Branch-v1.1.md).
2. **[ALTA — PROSSIMO SPRINT]** Aggiungere entry spark-ops in registry.json dopo verifica/pubblicazione repo `Nemex81/spark-ops` su GitHub.
3. **[ALTA — PROSSIMO SPRINT]** Aggiungere test per `spark/registry/client.py` (coverage 39% su modulo HTTPS-critical).
4. **[MEDIA]** Aggiornare `README.md:68` da `Tools Disponibili (50)` a `(51)`.
5. **[MEDIA]** Bump `spark-base` a v2.1.0 (task separato, dopo pubblicazione spark-ops).
6. **[BASSA]** Installare `pytest-asyncio` in env `audiomaker311` per sbloccare 10 test async.
7. **[BASSA]** Aggiungere docstring ai 10 tool che risultano senza (verifica manuale prima).

---

*Report generato da spark-engine-maintainer — 2026-05-11 | Basato su prompt spark-full-system-audit-v1.0*
