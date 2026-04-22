---
description: Pattern per interrogare il framework SCF e descriverne struttura, agenti e tool runtime.
scf_protected: false
scf_file_role: "skill"
name: framework-query
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# framework-query

- Per agenti: usa `scf://agents-index` o il relativo tool MCP.
- Per versioni: usa `scf_get_framework_version()`.
- Per runtime: usa `scf_get_runtime_state()` o `scf://runtime-state`.
- Mantieni le risposte orientate al task dell'utente, non a un dump completo.