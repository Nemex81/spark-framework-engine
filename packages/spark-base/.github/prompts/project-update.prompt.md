---
type: prompt
name: project-update
description: Aggiorna il profilo progetto tramite Agent-Welcome.
model: 
argument-hint: "update_request — Cosa vuoi aggiornare nel profilo progetto? (opzionale — lascia vuoto per vedere il help)"
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
scf_protected: false
agent: agent
spark: true
scf_owner: "spark-base"
---

# Project Update — Aggiornamento Profilo Progetto

Sei Agent-Welcome. Avvia OP-2: Aggiornamento Profilo.

Input ricevuto: ${input:update_request}

Se l'input è vuoto o non specificato:
mostra il blocco help di OP-2 prima di procedere.
Se l'input contiene una richiesta specifica:
procedi direttamente con OP-2 per i campi indicati.
