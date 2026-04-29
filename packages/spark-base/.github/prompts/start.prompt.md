---
type: prompt
name: start
description: Riprende il primo task aperto in docs/TODO.md e lo delega a code-Agent-Code.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

Leggi il file docs/TODO.md corrente.

1. Identifica la prima voce con checkbox non spuntata [ ]
2. Leggi il PLAN collegato (indicato in TODO.md come "Piano di riferimento")
3. Comunica: "Riprendo da [Fase X]: [descrizione fase]"
4. Avvia code-Agent-Code per quella fase specifica

Se `code-Agent-Code` non è disponibile nel workspace corrente, segnala che è
fornito dal pacchetto `scf-master-codecrafter`.

Se docs/TODO.md non esiste, comunicalo e suggerisci di usare #init.prompt.md
per creare un nuovo task.
