---
description: Criteri per scegliere bump patch, minor o major in base all'impatto della modifica.
scf_protected: false
scf_file_role: "skill"
name: semver-bump
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# semver-bump

- patch: fix e manutenzione.
- minor: nuove feature backward-compatible.
- major: breaking change o contratti pubblici incompatibili.