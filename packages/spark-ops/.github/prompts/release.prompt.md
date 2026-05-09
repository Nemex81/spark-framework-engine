---
type: prompt
name: release
description: Avvia Agent-Release per preparare una release del progetto o del framework.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 15
scf_merge_strategy: "replace"
scf_version: "1.0.0"
spark: true
scf_owner: "spark-ops"
---

Avvia Agent-Release per la versione ${input:Versione da rilasciare (es: v3.6.0)}.

Prerequisiti da verificare PRIMA di procedere:
1. Leggi CHANGELOG.md e verifica la sezione [Unreleased].
2. Verifica che tutti i piani attivi siano completati o READY.
3. Verifica che i test richiesti siano passati.

Se un prerequisito non e soddisfatto: blocca e comunica cosa manca.
Se tutti OK: segui il workflow release in `agents://Agent-Release`.
