---
type: prompt
name: project-setup
description: Avvia il setup iniziale del profilo progetto tramite Agent-Welcome.
model: 
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
agent: agent
spark: true
scf_owner: "spark-base"
---

# Project Setup — Inizializzazione Framework

Sei Agent-Welcome. Avvia OP-1: Setup Iniziale.

Template canonico di riferimento:
→ .github/templates/project-profile.template.md

Controlla lo stato del progetto:

- Se .github/project-profile.md NON esiste:
  carica il template canonico come struttura base
  e procedi con il flusso guidato OP-1 completo.

- Se .github/project-profile.md esiste con initialized: false:
  carica il template canonico come struttura base,
  comunica all'utente che il profilo verrà reinizializzato,
  e procedi con il flusso guidato OP-1 completo.

- Se .github/project-profile.md esiste con initialized: true:
  comunica che il progetto è già configurato
  e suggerisci #project-update.
