# SPARK Framework - Report Implementazione: Dual-Mode Manifest v3.1

**Data:** 2026-05-08 UTC  
**Implementatore:** GitHub Copilot (Agent Mode)  
**Proposta originale:** `docs/reports/SPARK-REPORT-DualMode-Architecture-v1.0.md`

## Riepilogo esecutivo

La proposta Dual-Mode e stata implementata nel repository `spark-framework-engine` rendendo esplicito il campo manifest `plugin_files` per file fisici plugin. Il lifecycle v3 installa questi file con lo stesso preservation gate dei `workspace_files`, li include nel payload di `scf_install_package` e li gestisce in rimozione. I manifest embedded dei package `scf-master-codecrafter` e `scf-pycode-crafter` sono stati portati a schema `3.1`.

## Modifiche al codice

- `spark/boot/lifecycle.py` - aggiunti helper per URI MCP e deduplica stabile; `_install_standalone_files_v3` legge `plugin_files` con default `[]`, separa `standalone_files_written` da `plugin_files_installed`, e `_remove_workspace_files_v3` include i plugin file nel cleanup sicuro. `_install_package_v3` espone `mcp_services_activated`, alias deprecato `installed` e campi plugin vuoti nel path base/idempotente.
- `spark/boot/tools_packages_install.py` - il tool `scf_install_package` installa `plugin_files` in `deployment_mode="auto"` quando dichiarati, evita il `deployment_notice` store-only in quel caso, aggiorna `deployment_summary.plugin_files_count` e mantiene `installed` come alias deprecato dei file fisici scritti.
- `tests/test_standalone_files_v3.py` - aggiunti test per installazione plugin file e separazione categorie nel risultato.
- `tests/test_install_workspace_files.py` - aggiunto test di rimozione di un plugin file tracciato.
- `tests/test_deployment_modes.py` - aggiunto test end-to-end del tool install in auto mode con `plugin_files` schema `3.1`.
- `tests/test_engine_inventory.py` - compatibilita manifest estesa a schema `3.0` e `3.1`, con `plugin_files` opzionale/lista.

## Modifiche ai manifest dei pacchetti

- `packages/scf-master-codecrafter/package-manifest.json` - `schema_version` aggiornato a `3.1`; aggiunto `plugin_files: []`.
- `packages/scf-pycode-crafter/package-manifest.json` - `schema_version` aggiornato a `3.1`; aggiunto `plugin_files` con:
  - `.github/workflows/notify-engine.yml`
  - `.github/python.profile.md`
  - `.github/skills/error-recovery/reference/errors-python.md`

Nota di perimetro: i repository sorgente esterni `scf-master-codecrafter` e `scf-pycode-crafter` non sono stati modificati da questo agente per vincolo operativo `spark-engine-maintainer`, che opera esclusivamente nel repository engine. Le copie embedded usate dall'engine sono aggiornate.

## Risultati test

| Fase | Passed | Skipped | Failed | Note |
| --- | --- | --- | --- | --- |
| Baseline pre-implementazione | 409 | 9 | 0 | 12 subtests passed |
| Post Task 1 - lifecycle/payload | 26 | 0 | 0 | `test_standalone_files_v3`, `test_install_workspace_files`, `test_deployment_modes` |
| Post Task 2-5 - manifest/schema | 9 | 0 | 0 | `test_engine_inventory` |
| Gate completo intermedio | 413 | 9 | 0 | 12 subtests passed |
| Gate finale | 413 | 9 | 0 | 12 subtests passed |

## Adattamenti rispetto alla proposta originale

- Le funzioni target sono in `spark/boot/lifecycle.py`, non in `spark/packages/lifecycle.py`.
- Non esiste `schemas/package-manifest.schema.json`; il supporto schema `3.1` e stato validato tramite test e manifest reali.
- `plugin_files` viene installato anche in `deployment_mode="auto"` quando dichiarato, per rispettare la semantica di file fisico plugin.
- La rimozione package include `plugin_files`, per evitare file fisici orfani.
- L'alias `installed` include file fisici scritti nel workspace, deduplicando `workspace_files_written`, `plugin_files_installed` e `standalone_files_written`.

## Anomalie gestite

- AP-GIT-0 - Branch: Agent-Git ha preparato `feature/dual-mode-manifest-v3.1` creando manualmente la ref dopo un tentativo instabile di `git switch`. Richiede verifica Agent-Git prima di review/commit finali.
- AP-SCHEMA-0 - Schema JSON assente: risolto aggiornando test e documentazione del contratto manifest.
- AP-PERIMETER-0 - Multi-repo: i manifest sorgente esterni devono essere aggiornati da un agente autorizzato al perimetro multi-repo o manualmente, replicando le modifiche gia applicate alle copie embedded.

## Note operative per il Coordinatore

- Verificare se `deployment_mode="store"` debba continuare a sopprimere `plugin_files`. L'implementazione attuale lo mantiene come opt-out esplicito per file fisici non minimi.
- Allineare i repository sorgente `scf-master-codecrafter` e `scf-pycode-crafter` prima della merge finale o del rilascio package.
- Delegare ad Agent-Git i commit atomici richiesti, senza push, dopo verifica dello stato branch.
