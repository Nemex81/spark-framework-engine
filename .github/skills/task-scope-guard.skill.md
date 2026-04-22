---
description: Controlla che il task resti nel perimetro richiesto e segnala deviazioni prima di implementare.
scf_protected: false
scf_file_role: "skill"
name: task-scope-guard
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# task-scope-guard

- Esplicita repository e file in scope.
- Se emergono side effect cross-repo, dichiarali prima di modificare.
- Non estendere il task senza motivo verificabile.