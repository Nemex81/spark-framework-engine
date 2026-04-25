---
type: prompt
name: sync-docs
description: Avvia Agent-Docs per sincronizzare la documentazione del progetto.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

Avvia Agent-Docs per sincronizzare la documentazione dopo i commit recenti.

Contesto da analizzare:
- File modificati: ${input:Elenca i file .py modificati (separati da virgola)}
- Tipo di modifica: ${input:Tipo (feat/fix/refactor)}
- Versione target: ${input:Versione (es: v3.6.0)}

Segui la Sync Strategy definita in .github/agents/Agent-Docs.md.
Produci al termine la Sync Checklist con stato di ogni documento.
