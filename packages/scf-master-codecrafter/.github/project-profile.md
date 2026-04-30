---
initialized: false
scf_protected: true
scf_file_role: "config"
scf_merge_priority: 20
scf_merge_strategy: "user_protected"
active_plugins: []
scf_version: "2.1.0"
framework_edit_mode: false
scf_owner: "scf-master-codecrafter"
spark: true
framework_version: ""

---

# Project Profile Template

Questo file e la source of truth del framework installato nel workspace.

Compilazione iniziale prevista:

- Agent-Welcome raccoglie nome progetto, stack, workflow e vincoli.
- I plugin installati aggiornano `active_plugins` senza sovrascrivere il resto.
- `framework_version` viene valorizzato quando il layer master e installato nel workspace target.

Quando `initialized: false`, gli agenti devono:

- mostrare un avviso non bloccante;
- evitare assunzioni su linguaggio o stack;
- proporre `#project-setup` o Agent-Welcome per il bootstrap.
