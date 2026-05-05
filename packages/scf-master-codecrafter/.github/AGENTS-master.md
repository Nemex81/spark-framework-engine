---
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_version: "2.6.0"
scf_file_role: "config"
scf_merge_priority: 20
plugin: scf-master-codecrafter
spark: true
scf_merge_strategy: "replace"
---

# AGENTS Master

Agenti CORE-CRAFT forniti da `scf-master-codecrafter`.

- code-Agent-Analyze — dispatcher — analyze
- code-Agent-Code — executor — code, implementation, fallback
- code-Agent-CodeRouter — dispatcher — code, code-ui, routing
- code-Agent-CodeUI — dispatcher — code-ui, ui
- code-Agent-Design — dispatcher — design
- code-Agent-Docs — dispatcher — docs
- code-Agent-FrameworkDocs — executor — framework docs
- code-Agent-Git — executor — git
- code-Agent-Helper — executor — helper, consultivo
- code-Agent-Plan — dispatcher — plan
- code-Agent-Research — support — language-research, best-practice-synthesis, knowledge-cache
