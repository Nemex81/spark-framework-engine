---
type: prompt
name: scf-list-installed
description: Elenca i pacchetti SCF installati nel workspace attivo.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

Obiettivo: mostrare cosa e gia installato localmente.

Istruzioni operative:
1. Esegui `scf_list_installed_packages()`.
2. Non modificare file o stato del workspace.
3. Mostra per ogni pacchetto:
   - `package`
   - `version`
   - `file_count`

Se non e installato nulla, rispondi chiaramente che il workspace non ha pacchetti SCF installati.
