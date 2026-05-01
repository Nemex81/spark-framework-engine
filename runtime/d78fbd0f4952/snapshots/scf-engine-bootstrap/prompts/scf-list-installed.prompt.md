---
description: Elenca i pacchetti SCF installati nel workspace attivo.
scf_protected: false
scf_file_role: "prompt"
name: scf-list-installed
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
type: prompt
spark: true
scf_owner: "spark-base"
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
