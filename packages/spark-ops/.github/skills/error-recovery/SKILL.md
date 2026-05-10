---
spark: true
name: error-recovery
description: Procedura standardizzata di retry ed escalata quando un subagente fallisce l'esecuzione di un task.
scf_owner: "spark-ops"
scf_file_role: "skill"
scf_version: "1.0.0"
scf_merge_strategy: "replace"
scf_merge_priority: 15
scf_protected: false
---

# Skill: Error Recovery

## Procedura

1. Classifica l'errore: contesto insufficiente, comando fallito, gate fallito, conflitto o policy block.
2. Arricchisci il contesto con una sola ricerca mirata.
3. Esegui al massimo due retry automatici.
4. Se il secondo retry fallisce, passa a supervised mode e segnala `ATTENZIONE:`.

## Output richiesto

```text
PROBLEMA: <descrizione>
CORREZIONE: <azione>
VERIFICA: <gate o test>
ESITO: PASS | FAIL | ESCALATA
```

## Vincoli

- Non bypassare gate falliti.
- Non usare comandi distruttivi come fallback.
- Non nascondere errori di dipendenza o policy.
