---
description: Impone conferma esplicita e elenco impatti prima di eliminare file o directory.
scf_protected: false
scf_file_role: "skill"
name: file-deletion-guard
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# file-deletion-guard

- Non eliminare file senza conferma utente esplicita.
- Elenca sempre i path coinvolti e il motivo.
- Se il file appartiene al framework, verifica anche il perimetro `framework-guard`.