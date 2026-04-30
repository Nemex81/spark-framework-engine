---
task: razionalizzazione-agenti-comuni
agent: Agent-Orchestrator
status: DRAFT
date: 2026-04-23
plan_ref: docs/PIANO-RAZIONALIZZAZIONE-AGENTI-COMUNI-2026-04-23.md
---

# TODO — Razionalizzazione Agenti Comuni 2026-04-23

Piano di riferimento:
`docs/PIANO-RAZIONALIZZAZIONE-AGENTI-COMUNI-2026-04-23.md`

## Audit e convalida

- [x] Confrontare gli 11 agenti comuni tra `spark-base` e `scf-master-codecrafter`
- [x] Verificare i file del master che referenziano agenti comuni ed esclusivi
- [x] Stabilire se il piano originale e eseguibile in sicurezza
- [x] Formalizzare la strategia correttiva

## Prerequisiti

- [x] Ottenere `#framework-unlock` per `spark-base/.github/**`
- [x] Ottenere `#framework-unlock` per `scf-master-codecrafter/.github/**`

## Esecuzione correttiva

- [x] Costruire la matrice di riconciliazione semantica dei common agent
- [x] Allineare in `spark-base` i contenuti master realmente mancanti
- [x] Eliminare dal master solo i common agent diventati duplicati reali
- [x] Aggiornare `AGENTS.md`, `AGENTS-master.md`, `copilot-instructions.md` e i prompt impattati
- [x] Rinominare gli agenti esclusivi del master con prefisso `code-`
- [x] Aggiornare tutti i riferimenti ai nuovi nomi file
- [x] Aggiornare changelog del master

## Validazione e chiusura

- [x] Verificare assenza di riferimenti rotti ai vecchi agenti
- [x] Eseguire validazione finale dei file modificati
- [ ] Delegare eventuale commit locale ad Agent-Git
- [ ] Eseguire push solo con conferma `PUSH`
