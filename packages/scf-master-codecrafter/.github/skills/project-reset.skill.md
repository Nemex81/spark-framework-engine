---
spark: true
name: project-reset
description: Checklist di reset contesto a inizio sessione per evitare assunzioni stale.
---

# project-reset

All'inizio di una sessione:
- leggi `scf_get_project_profile()`;
- leggi `scf_get_global_instructions()`;
- controlla stato git in sola lettura;
- leggi solo i file rilevanti per il task corrente.