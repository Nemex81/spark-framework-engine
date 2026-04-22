---
description: Strategia di rollback dopo fallimenti post-commit o modifiche parziali non valide.
scf_protected: false
scf_file_role: "skill"
name: rollback-procedure
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# rollback-procedure

- Commit non pushato: preferisci reset soft tramite Agent-Git.
- Commit gia pushato: preferisci revert tramite Agent-Git.
- Dopo rollback, riapri la checklist TODO della fase interessata.