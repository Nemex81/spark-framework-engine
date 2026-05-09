---
type: prompt
name: framework-changelog
description: Aggiunge una voce al changelog del framework sezione [Unreleased].
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 15
scf_merge_strategy: "replace"
scf_version: "1.0.0"
agent: agent
spark: true
scf_owner: "spark-ops"
---

# Framework Changelog Update

Sei Agent-FrameworkDocs. Aggiungi una voce al changelog del framework.

Esegui in sequenza:

1. Leggi il changelog framework pertinente.
2. Raccogli la voce da aggiungere: ${input:Descrivi la modifica}
3. Determina la categoria: Added / Changed / Fixed / Removed.
4. Mostra la voce formattata e il contesto aggiornato.
5. Attendi conferma utente se tocchi file protetti.
6. Scrivi la voce nella categoria corretta.
