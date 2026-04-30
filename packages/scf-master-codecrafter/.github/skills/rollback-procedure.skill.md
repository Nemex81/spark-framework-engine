---
spark: true
name: rollback-procedure
description: Strategia di rollback dopo fallimenti post-commit o modifiche parziali non valide.
---

# rollback-procedure

- Commit non pushato: preferisci reset soft tramite Agent-Git.
- Commit gia pushato: preferisci revert tramite Agent-Git.
- Dopo rollback, riapri la checklist TODO della fase interessata.