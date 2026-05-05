---
description: Classifica un task di implementazione come UI o non-UI per il dispatcher code router.
scf_protected: false
scf_file_role: "skill"
name: code-routing
scf_merge_priority: 20
scf_merge_strategy: "replace"
scf_version: "2.1.0"
spark: true
scf_owner: "scf-master-codecrafter"
---

# code-routing

- Se il task tocca accessibilita, interazioni visive o componenti UI: route `code-ui`.
- Se il task tocca logica, backend, tooling o docs tecniche: route `code`.
- Se il task e misto, spezzalo in fasi e segnala l'ambiguita all'orchestratore.
