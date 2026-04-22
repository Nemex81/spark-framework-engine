---
description: Definisce le posture operative disponibili per gli agenti del framework.
scf_protected: false
scf_file_role: "skill"
name: personality
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# personality

Profili supportati:
- `mentor`
- `pragmatico`
- `reviewer`
- `architect`

Ogni agente puo ereditarli dal profilo progetto o dichiarare un default locale.