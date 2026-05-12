# SPARK Report - Fixes v4.1

Data: 2026-05-12
Scope: P0-P2 fixes derived from DeepAudit v4.0
Mode: autonomous sequential SCF
Baseline suite: 578 passed

## Executive Summary

Implementati i fix P0-P2 richiesti dal report [docs/reports/SPARK-REPORT-DeepAudit-v4.0.md](docs/reports/SPARK-REPORT-DeepAudit-v4.0.md) con validazione sequenziale per task.

Risultato finale:
- sicurezza path remoti U2 hardenizzata
- telemetria cache resa deterministica
- cache root allineata al workspace target
- confronto versioni U2 reso semver-aware
- bootstrap transfer protetto da lock cross-platform
- suite non-live finale: 585 passed

## Task 1 - P0 Security Path

File: spark/boot/tools_plugins.py
Delta:
- aggiunto helper `_resolve_safe_github_destination(...)`
- rifiuto di path assoluti, drive-rooted e destinazioni fuori containment `.github/`

Test aggiunti:
- `test_scf_plugin_install_remote_rejects_absolute_manifest_path`

Checkpoint pytest:
- plugin integration slice: 3 passed
- tools registry client: 14 passed

Esito: PASS

## Task 2 - P1 Cache Telemetry

File: spark/boot/tools_plugins.py
File supporto: spark/registry/client.py
Delta:
- `RegistryClient.cache_age_seconds()`
- `scf_plugin_list_remote` ora espone:
  - `from_cache` = cache hit pre-fetch
  - `cache_age_seconds`

Test aggiunti:
- `test_scf_plugin_list_remote_reports_cache_hit_and_age`
- `test_scf_plugin_list_remote_reports_refresh_without_cache_hit`

Checkpoint pytest:
- plugin integration slice: 2 passed
- registry client + registry U2: 34 passed

Esito: PASS

## Task 3 - P1 Workspace Cache Coherence

File: spark/boot/tools_plugins.py
Delta:
- `_make_registry_client(...)` riusa il client engine solo quando il `github_root` coincide
- `scf_plugin_install_remote(...)` usa il `.github/` del `workspace_root` target per lookup registry e manifest flow

Test aggiunti:
- `test_scf_plugin_install_remote_uses_target_workspace_cache_root`

Checkpoint pytest:
- plugin integration slice: 4 passed
- registry U2 slices: 28 passed

Esito: PASS

## Task 4 - P1 SemVer Compare

File: spark/boot/tools_resources.py
Delta:
- aggiunto helper `_is_registry_version_newer(...)`
- `_build_u2_registry_hint()` ora calcola `update_available` con ordering semver-aware

Test aggiunti:
- `test_u2_registry_hint_uses_semver_ordering_for_minor_versions`
- `test_u2_registry_hint_detects_stable_newer_than_prerelease`

Checkpoint pytest:
- registry U2 suite: 16 passed
- plugin integration guard slice: 4 passed

Esito: PASS

## Task 5 - P2 Bootstrap Lock

File: spark/boot/sequence.py
Delta:
- aggiunta lock directory `.spark-ops-copy.lock`
- skip sicuro se un altro transfer bootstrap è già in corso
- cleanup lock in `finally`
- creazione preventiva di `.github/` prima dell'acquisizione del lock

Test aggiunti:
- `test_ensure_spark_ops_workspace_files_skips_when_lock_exists`

Checkpoint pytest:
- universe v3 distribution: 5 passed
- spark-ops decoupling manifest: 4 passed

Esito: PASS

## Full Validation

Comando:
- `pytest tests/ -q --ignore=tests/test_integration_live.py --tb=short`

Risultato:
- 585 passed

## CHANGELOG Proposal Applied

Aggiornata la sezione `Unreleased` in [CHANGELOG.md](CHANGELOG.md) con voce `Fixed — DeepAudit v4.1 P0-P2 hardening`.

## Commit Proposal

```bash
git add spark/boot/tools_plugins.py
git add spark/boot/tools_resources.py
git add spark/boot/sequence.py
git add spark/registry/client.py
git add tests/test_plugin_manager_integration.py
git add tests/test_registry_u2_client.py
git add tests/test_universe_v3_distribution.py
git add CHANGELOG.md docs/todo.md docs/reports/SPARK-REPORT-Fixes-v4.1.md

git commit -m "fix(registry): harden U2 path, cache telemetry and bootstrap lock

- harden scf_plugin_install_remote destination containment
- report deterministic from_cache + cache_age_seconds
- scope registry cache to target workspace when roots differ
- make U2 registry_hint semver-aware
- add cross-platform lock for spark-ops bootstrap transfer
- add focused regression tests
- suite: 585 passed"
```
