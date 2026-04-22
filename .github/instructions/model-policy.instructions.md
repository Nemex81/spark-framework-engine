---
scf_protected: false
scf_file_role: "instruction"
name: model-policy
applyTo: "**"
scf_merge_strategy: "replace"
scf_version: "1.2.0"
package: scf-master-codecrafter
scf_merge_priority: 10
scf_owner: "spark-base"
spark: true
version: 1.0.0
---

# Model Policy

- Leggi il contesto reale prima di modificare file.
- Non fare refactor non richiesti.
- Se esistono piu approcci validi, dichiara il trade-off principale.
- Le modifiche multi-file richiedono piano o checklist condivisa.
- Gli agenti dispatcher non implementano direttamente: instradano o fanno fallback.