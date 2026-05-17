# TODO — SPARK Framework Engine

> Coordinatore cicli di sviluppo. Aggiornato al: 2026-05-14 (pulizia post-CICLO 5)
> ENGINE_VERSION corrente: 3.6.0
> Suite test: 729 passed (baseline post-CICLO 5)
> Branch: workspace-slim-registry-sync-20260511

***

## Ciclo corrente

Nessun ciclo attivo. Il CICLO 5 (release 3.6.0) è stato chiuso
il 2026-05-14.

***

## Sospesi aperti

- [x] **DOC-GAP-CLI** — `docs/api.md`: sezione CLI aggiunta in ciclo post-3.6.0.
  Layer CLI (InitManager, PackageManager, RegistryManager, entry points)
  documentato. Audit documentazione completa eseguito. Chiuso definitivamente.
- [x] **MULTI-REPO-1** — Aggiornare `min_engine_version` a `"3.6.0"` — chiuso 2026-05-14
  in `scf-master-codecrafter` e `scf-pycode-crafter`
  (repo separati, fuori perimetro engine). Richiede agente
  con accesso multi-repo.
- [x] **DEPRECATED-REMOVAL** — `tools_plugins.py`: `scf_list_plugins` e
  `scf_install_plugin` rimossi. Costanti legacy e import orfano rimossi.
  Tool count 53 → 51. Chiuso in ciclo post-3.6.0 — 2026-05-14.

***

## Prossimo ciclo

Da definire. Nessun candidato residuo dal CICLO 5.

Consolidamento post-CICLO 5 completato il 2026-05-17:
sezione `### Changed` duplicata in `[Unreleased]` rimossa,
costanti `_BOOTSTRAP_UPDATE_MODES` e `SparkToolResult` aggiunte,
diagnostica CLI estesa. Tutti i sospesi aperti sono chiusi.

I task già completati nel CICLO 5 e rimossi da questo elenco:

- Verifica allineamento docs/api.md con tool aggiunti in 3.5.0
  (scf_plugin_list_remote, scf_plugin_install_remote): CHIUSO 2026-05-14.
- Chiusura sospesi MULTI-REPO-1 (min_engine_version nei manifest remoti
  scf-master-codecrafter e scf-pycode-crafter): CHIUSO 2026-05-14.
