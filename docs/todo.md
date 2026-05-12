# TODO - SPARK Dual-Mode Manifest v3.1

## Addendum 2026-05-12 - DeepAudit v4.1 fixset

- [x] Fix P0: containment path sicuro in `scf_plugin_install_remote` per path assoluti e drive-rooted.
- [x] Fix P1: telemetria `from_cache` deterministica + `cache_age_seconds`.
- [x] Fix P1: registry cache coerente con `workspace_root` target nei flussi remoti U2.
- [x] Fix P1: `registry_hint.update_available` semver-aware.
- [x] Fix P2: lock cross-platform su bootstrap transfer `spark-ops`.
- [ ] Commit/PR delegato ad Agent-Git.

> Generato da Copilot Agent il 2026-05-08 UTC.
> Strategia: Dual-Mode Manifest - schema v3.1 + plugin_files
> Baseline: 409 passed / 9 skipped / 0 failed -> 413 passed post-implementazione finale
> Stato: COMPLETATO

## Riepilogo modifiche implementate

### Addendum 2026-05-10 - spark-ops decoupling

- [x] Convalidata la strategia aggiornata: `Agent-Research`, `rollback-procedure`,
	`framework-scope-guard`, `semver-bump` e `framework-unlock` restano in `spark-base`.
- [x] Creato `packages/spark-ops/` come package `mcp_only` per Orchestrator,
	FrameworkDocs, Release, skill E2E e prompt operativi.
- [x] Aggiornato `spark-base` a `2.0.0` rimuovendo dal catalogo distribuito le
	risorse operative migrate senza eliminare fisicamente i file legacy.
- [x] Aggiornati manifest embedded e documentazione per `scf-master-codecrafter`
	e `scf-pycode-crafter`.
- [x] Aggiunto test manifest `tests/test_spark_ops_decoupling_manifest.py`.

- [x] Letto e validato il report `docs/reports/SPARK-REPORT-DualMode-Architecture-v1.0.md`.
 - [x] Letto e validato il report `docs/reports/archiviati/SPARK-REPORT-DualMode-Architecture-v1.0.md`.
- [x] Localizzati i punti reali di implementazione in `spark/boot/lifecycle.py` e `spark/boot/tools_packages_install.py`.
- [x] Creato il piano tecnico self-contained in `docs/implementation-plan-dual-mode-v3.1.md`.
 - [x] Creato il piano tecnico self-contained in `docs/coding plans/implementation-plan-dual-mode-v3.1.md`.
- [x] Aggiunto supporto `plugin_files` opzionale con default `[]` nel lifecycle v3.
- [x] Aggiornato il payload v3 con `mcp_services_activated`, `workspace_files_written`, `plugin_files_installed` e alias deprecato `installed`.
- [x] Esteso il cleanup v3 per rimuovere o preservare anche i `plugin_files` installati.
- [x] Aggiornati i test per schema manifest v3.1, install plugin file, payload tool e cleanup.
- [x] Aggiornati i manifest embedded engine di `scf-master-codecrafter` e `scf-pycode-crafter` a schema `3.1`.
- [x] Aggiornata la documentazione correlata su installazione pacchetti e Dual-Mode.

## Anomalie gestite

- AP-GIT-0: Agent-Git ha preparato il branch `feature/dual-mode-manifest-v3.1` creando manualmente la ref dopo un tentativo instabile di `git switch`. Da verificare con Agent-Git prima di review/commit finali.
- AP-SCHEMA-0: non esiste `schemas/package-manifest.schema.json`; il supporto v3.1 e stato implementato tramite parsing permissivo, test e manifest reali.
- AP-PERIMETER-0: l'agente corrente `spark-engine-maintainer` opera esclusivamente nel repository `spark-framework-engine`; i manifest nei repository secondari reali vanno applicati da agente/perimetro appropriato. Le copie embedded nel repo engine sono state aggiornate.

## Gate finale

- Baseline pre-implementazione: `409 passed, 9 skipped, 12 subtests passed`.
- Gate Task 1 focalizzato: `26 passed`.
- Gate manifest/schema: `9 passed`.
- Gate completo intermedio: `413 passed, 9 skipped, 12 subtests passed`.
- Gate finale completo: `413 passed, 9 skipped, 12 subtests passed`.

## Prossimi passi suggeriti

- Applicare la stessa modifica `schema_version: "3.1"` + `plugin_files` ai repository sorgente `scf-master-codecrafter` e `scf-pycode-crafter` con un agente autorizzato al perimetro multi-repo.
- Delegare ad Agent-Git i commit atomici sul branch preparato, senza push.
