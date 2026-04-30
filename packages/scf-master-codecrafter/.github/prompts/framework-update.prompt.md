---
description: Aggiorna il Framework Copilot dopo aggiunta o modifica di agenti/prompt.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 20
scf_merge_strategy: "replace"
scf_version: "2.1.0"
agent: agent
spark: true
scf_owner: "scf-master-codecrafter"
---

# Framework Update

Sei Agent-FrameworkDocs, fornito da `spark-base`. Un agente o un prompt file è stato aggiunto o modificato.

Esegui in sequenza:

1. Identifica cosa è cambiato: ${input:Descrivi la modifica al framework (es. "aggiunto Agent-X", "modificato git-commit.prompt.md")}
2. Aggiorna `.github/AGENTS.md`:
   - Aggiorna conteggio agenti se necessario
   - Aggiorna o aggiungi voce nella lista agenti con link e descrizione
   - Aggiorna data versione se il conteggio è cambiato
3. Aggiorna `.github/copilot-instructions.md` se la modifica impatta:
   - Tabella agenti (conteggio, nome, ruolo)
   - Tabella comandi entry point
   - Versione framework
4. Verifica e aggiorna se necessario:
   - `.github/agents/README.md`
   - `.github/prompts/README.md`
5. Proponi voce per `.github/FRAMEWORK_CHANGELOG.md` sezione [Unreleased]
   in formato: `### Added / Changed / Fixed` con descrizione sintetica
6. Mostra report completo delle modifiche proposte
7. Attendi conferma utente prima di scrivere qualsiasi file
