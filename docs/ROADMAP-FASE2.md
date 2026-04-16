# SPARK Framework Engine — Roadmap Fase 2

## 1. conflict_mode: "merge" — REALIZZATA in v2.0.0

- Comportamento implementato: merge a 3 vie sui file markdown tra versione installata (snapshot BASE), versione utente e nuova versione pacchetto.
- Modalita supportate: `manual`, `auto`, `assisted` — in aggiunta ai precedenti `abort` e `replace`.
- Euristica frontmatter: i casi divergenti vengono trattati in modo conservativo e degradano a `manual`.
- `MergeEngine` e i validator post-merge sono implementati nel motore come helper puri; il merge non e delegato a `ManifestManager`.
- Validator post-merge per verifica coerenza strutturale del file risultante.
- Sessioni stateful per `manual` / `assisted`: `scf_finalize_update`, `scf_approve_conflict`, `scf_reject_conflict`, `scf_resolve_conflict_ai`.
- Versione motore: 2.0.0 (come pianificato).

## 2. scf_plan_install batch

- Estensione del dry-run a liste di pacchetti in input.
- Dependency graph completo calcolato prima di qualsiasi operazione su disco.
- Conflict report aggregato per tutti i pacchetti in un unico oggetto strutturato.
- Stima complessità: media — richiede versione motore 1.10.0.

## 3. notify-engine.yml — meccanismo push-to-registry

- Il workflow GitHub Actions gia presente in scf-pycode-crafter (.github/workflows/notify-engine.yml) e il prototipo del meccanismo futuro per notificare il registry di nuove versioni.
- Comportamento target: push su main nei repo pacchetto che innesca l'aggiornamento automatico di registry.json.
- Prerequisiti: GitHub Actions con write access su scf-registry, token dedicato e schema webhook in RegistryClient.
- Stima complessità: media — indipendente dalla versione motore.

## 4. Stato attuale

- Engine version: 2.0.0
- Tool registrati: 33
- conflict_mode supportati in produzione: "abort", "replace", "manual", "auto", "assisted"
- Note operative: `auto` usa una risoluzione best-effort conservativa e degrada a `manual` nei casi ambigui; `scf_apply_updates(conflict_mode=...)` inoltra il mode scelto a tutto il batch.
- conflict_mode pianificati Fase 2: tutti implementati e rilasciati in v2.0.0
