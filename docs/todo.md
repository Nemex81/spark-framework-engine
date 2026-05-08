# TODO - SPARK Dual-Mode Manifest v3.1

> Generato da Copilot Agent il 2026-05-08 UTC.
> Strategia: Dual-Mode Manifest - schema v3.1 + plugin_files
> Baseline: 409 passed / 9 skipped / 0 failed -> 413 passed post-implementazione finale
> Stato: COMPLETATO

## Riepilogo modifiche implementate

- [x] Letto e validato il report `docs/reports/SPARK-REPORT-DualMode-Architecture-v1.0.md`.
- [x] Localizzati i punti reali di implementazione in `spark/boot/lifecycle.py` e `spark/boot/tools_packages_install.py`.
- [x] Creato il piano tecnico self-contained in `docs/implementation-plan-dual-mode-v3.1.md`.
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
