---
description: Regole trasversali per organizzare componenti in layer e dipendenze stabili.
scf_protected: false
scf_file_role: "skill"
name: clean-architecture
scf_merge_priority: 20
scf_merge_strategy: "replace"
scf_version: "2.1.0"
spark: true
scf_owner: "scf-master-codecrafter"
---

# clean-architecture

- Separare orchestration, domain logic, infrastructure e presentation.
- Evitare dipendenze circolari tra layer.
- Tenere la logica di business indipendente da I/O e tooling.