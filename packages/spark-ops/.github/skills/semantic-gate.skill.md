---
spark: true
name: semantic-gate
description: Criteri minimi osservabili da verificare prima di avanzare tra le fasi Analyze, Design e Plan nel ciclo E2E.
scf_owner: "spark-ops"
scf_file_role: "skill"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_merge_priority: 15
scf_protected: false
---

# Skill: Semantic Gate

Verifica la qualita minima del contenuto prodotto nelle fasi E2E.

## Gate 1 - Findings

Il report Analyze deve contenere: `Componenti coinvolti`, `Dipendenze`, `Rischi`, `Vincoli accessibilita NVDA`.

## Gate 2 - Design

Il design deve avere frontmatter `status: REVIEWED` e conferma utente esplicita prima del planning.

## Gate 3 - Plan

Il piano deve avere frontmatter `status: READY` e conferma utente esplicita prima della codifica.

## Regola

Non avanzare se una sezione obbligatoria manca o se un gate CLI fallisce.
