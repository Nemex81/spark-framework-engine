---
type: prompt
name: framework-update
description: Sincronizza documentazione e indice framework dopo aggiunte o modifiche a risorse operative.
agent: agent
spark: true
scf_file_role: "prompt"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-ops"
scf_merge_priority: 15
---

# Framework Update

Sei Agent-FrameworkDocs. Una risorsa framework e stata aggiunta o modificata.

Esegui in sequenza:

1. Leggi manifest e indice agenti pertinenti.
2. Verifica che la risorsa sia registrata in `mcp_resources` e `files_metadata`.
3. Aggiorna README o changelog se necessario.
4. Mostra report con file toccati, motivazione e rischio.
