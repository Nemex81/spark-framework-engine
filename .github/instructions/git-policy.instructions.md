---
scf_protected: false
scf_file_role: "instruction"
name: git-policy
applyTo: "**"
scf_merge_strategy: "replace"
scf_version: "1.2.0"
package: scf-master-codecrafter
scf_merge_priority: 10
scf_owner: "spark-base"
spark: true
version: 1.0.0
---

# Git Policy

- Fuori da Agent-Git, Copilot non esegue `git push`, `git merge`, `git commit`, `git rebase`.
- Sono sempre consentiti i comandi read-only: `git status`, `git diff`, `git log`, `git show`, `git branch`.
- I commit proposti devono seguire Conventional Commits.
- Ogni push richiede conferma esplicita `PUSH`.
- Ogni merge richiede conferma esplicita `MERGE`.