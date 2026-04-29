---
type: prompt
name: status
description: Riepiloga lo stato del workflow progetto e il prossimo passo consigliato.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

Leggi i seguenti file e produci un report di stato:
- docs/TODO.md (progresso fasi)
- docs/3 - coding plans/ (PLAN attivi)
- docs/2 - projects/ (DESIGN attivi)

Formato output (testo piano, accessibile screen reader):

```
Workflow attivo: [nome task o "nessuno"]
Agente corrente: [Agent-X o "nessuno"]
Fase corrente: [N di M -- descrizione]
Fasi completate: [N]
Fasi rimanenti: [N]
Gate coverage: [% se disponibile o "non ancora eseguito"]
Prossimo step: [azione suggerita]
```

Se non c'e alcun workflow attivo, suggerisci di usare #init.prompt.md
per avviare un nuovo task.
