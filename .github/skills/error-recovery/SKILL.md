---
description: Fornisce una procedura sintetica per classificare e recuperare errori operativi comuni.
scf_protected: false
scf_file_role: "skill"
name: error-recovery
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

# error-recovery

1. Identifica se il problema e di ambiente, validazione o logica.
2. Riproduci con il set minimo di file e comandi.
3. Applica la correzione minima verificabile.
4. Aggiorna piano o TODO se il problema cambia il percorso implementativo.