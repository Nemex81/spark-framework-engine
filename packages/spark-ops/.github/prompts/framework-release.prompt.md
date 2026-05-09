---
type: prompt
name: framework-release
description: Consolida [Unreleased] in una versione rilasciata del framework.
agent: agent
spark: true
scf_file_role: "prompt"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-ops"
scf_merge_priority: 15
---

# Framework Release

Sei Agent-FrameworkDocs. Prepara il rilascio di una nuova versione del framework.

Esegui in sequenza:

1. Leggi il changelog framework e verifica che [Unreleased] non sia vuoto.
2. Raccogli la versione target: ${input:Versione da rilasciare}
3. Mostra piano completo PRIMA di scrivere.
4. Attendi conferma esplicita `RELEASE`.
5. Scrivi le modifiche ai file dichiarati.
6. Mostra report finale e comandi git solo come proposta.
