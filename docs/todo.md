# TODO — SPARK Framework Engine

> Coordinatore cicli di sviluppo. Aggiornato al: 2026-05-14
> ENGINE_VERSION corrente: 3.6.0
> Suite test: 729 passed (baseline post-CICLO 5)
> Branch: workspace-slim-registry-sync-20260511

***

## Ciclo corrente

Nessun ciclo attivo. Il CICLO 5 (release 3.6.0) è stato chiuso
il 2026-05-14.

***

## Sospesi aperti

- [x] **DOC-GAP-CLI** — `docs/`: gap layer CLI rilevato in audit — chiuso 2026-05-14
  pre-3.6.0. Documentato come debito tecnico. Nessuna modifica
  al codice runtime richiesta. Da affrontare in ciclo futuro
  se necessario.
- [x] **MULTI-REPO-1** — Aggiornare `min_engine_version` a `"3.6.0"` — chiuso 2026-05-14
  in `scf-master-codecrafter` e `scf-pycode-crafter`
  (repo separati, fuori perimetro engine). Richiede agente
  con accesso multi-repo.

***

## Prossimo ciclo

Da definire. Candidati:

- Verifica allineamento `docs/api.md` con tool aggiunti in 3.5.0
  (`scf_plugin_list_remote`, `scf_plugin_install_remote`) e
  CLI entry points di 3.6.0.
- Chiusura sospesi MULTI-REPO-1 tramite agente dedicato.
