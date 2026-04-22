---
description: Definisce il blocco standard per modifiche ai componenti del framework SCF.
scf_protected: false
scf_file_role: "skill"
name: framework-guard
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# framework-guard

- Verifica se il task e framework-scope o application-scope.
- Se tocchi `.github/**`, dichiara esplicitamente il perimetro.
- Non mischiare nello stesso changeset framework e codice applicativo se evitabile.