---
type: prompt
name: framework-changelog
description: Aggiunge una voce al FRAMEWORK_CHANGELOG.md sezione [Unreleased].
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
agent: agent
spark: true
scf_owner: "spark-base"
---

# Framework Changelog Update

Sei Agent-FrameworkDocs. Aggiungi una voce al changelog del framework.

Esegui in sequenza:

1. Leggi `.github/FRAMEWORK_CHANGELOG.md` — stato attuale sezione [Unreleased]
2. Raccogli la voce da aggiungere: ${input:Descrivi la modifica (es. "Added: Agent-FrameworkDocs")}
3. Determina la categoria: Added / Changed / Fixed / Removed
4. Mostra la voce formattata e il contesto [Unreleased] aggiornato
5. Attendi conferma utente
6. Scrivi la voce in `.github/FRAMEWORK_CHANGELOG.md` sotto [Unreleased]
   nella categoria corretta, in ordine cronologico inverso

Nessun altro file viene modificato da questo prompt.
