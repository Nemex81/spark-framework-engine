---
task: razionalizzazione-spark-ownership-cleanup
agent: Agent-Orchestrator
status: DRAFT
date: 2026-04-23
plan_ref: docs/PIANO-RAZIONALIZZAZIONE-SPARK-OWNERSHIP-CLEANUP-2026-04-23.md
---

# TODO — Razionalizzazione SPARK 2026-04-23

Piano di riferimento:
`docs/PIANO-RAZIONALIZZAZIONE-SPARK-OWNERSHIP-CLEANUP-2026-04-23.md`

## Audit e validazione

- [x] Verificare stato reale di `spark-base/package-manifest.json`
- [x] Verificare stato reale di `scf-master-codecrafter/package-manifest.json`
- [x] Verificare stato reale di `scf-registry/registry.json`
- [x] Inventariare skill e instruction di `spark-base`
- [x] Inventariare skill e instruction di `scf-master-codecrafter`
- [x] Validare il piano originario contro lo stato reale
- [x] Formalizzare la strategia correttiva

## Coordinamento documentale

- [x] Creare piano tecnico correttivo
- [x] Creare TODO per-task
- [ ] Aggiornare coordinatore `docs/TODO.md`

## Delta eseguibile

- [x] Confermare che `scf-master-codecrafter` non richiede ulteriori rimozioni manifeste
- [x] Confermare che `dependencies: ["spark-base"]` e gia presente
- [x] Confermare che `scf-registry` e gia allineato alle versioni correnti

## Delta bloccato da framework guard

- [ ] Ottenere `#framework-unlock` per `spark-base/.github/**`
- [ ] Ottenere `#framework-unlock` per `scf-master-codecrafter/.github/**`
- [ ] Correggere i path cross-package errati nei file agenti di `spark-base`
- [ ] Rimuovere i riferimenti rotti a `project.instructions.md`
- [ ] Rimuovere i riferimenti rotti a `tests.instructions.md`
- [ ] Aggiungere note di dipendenza per skill fornite da `scf-master-codecrafter`
- [ ] Aggiornare `spark-base/.github/changelogs/spark-base.md`
- [ ] Aggiornare `scf-master-codecrafter/.github/changelogs/scf-master-codecrafter.md`

## Delta bloccato da policy git

- [ ] Eseguire eventuali commit locali via Agent-Git
- [ ] Eseguire push di `spark-base` con `PUSH`
- [ ] Eseguire push di `scf-master-codecrafter` con `PUSH`
- [ ] Creare e pushare tag `v1.4.0` di `spark-base`

## Chiusura

- [ ] Rieseguire validazione finale cross-repo
- [ ] Produrre report finale consolidato
