---
name: scf-documentation
description: Mantiene sincronizzati README, file di design e piani di progetto con lo stato reale dell'implementazione del motore SCF.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.2"
scf_file_role: "skill"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

# Skill: scf-documentation

Obiettivo: mantenere coerenza tra implementazione reale e documentazione di progetto.

## Procedura aggiornamento README

- Leggere README.md e spark-framework-engine.py.
- Aggiornare contatore tool in base al numero reale in register_tools().
- Aggiornare contatore resource in base al numero reale in register_resources().
- Aggiornare elenco tool disponibili in caso di aggiunte/rimozioni.
- Proporre diff e attendere conferma prima di applicare.

## Procedura aggiornamento SCF-PROJECT-DESIGN.md

- Applicare solo per cambi architetturali sostanziali.
- Leggere file corrente e individuare sezioni obsolete.
- Modificare solo sezioni non allineate, evitando riscritture complete inutili.
- Proporre diff e attendere conferma prima di applicare.

## Procedura gestione piani *-PLAN.md

- Dopo completamento piano, aggiungere sezione Stato finale con data ed esito.
- Non eliminare i piani completati.
- Archiviare piano completato con prefisso DONE- quando richiesto dal flusso.
- Per piani parziali, aggiornare checklist con [x] e [ ].

## Regola generale

- Non modificare documentazione in autonomia senza conferma.
- Segnalare sempre disallineamenti prima di proporre correzioni.
- Proporre sempre diff + conferma esplicita prima dell'applicazione.

## Tool da usare

- readFile
- editFiles
- fetch
- scf_get_framework_version (restituisce `engine_version` e le versioni dei pacchetti installati)
