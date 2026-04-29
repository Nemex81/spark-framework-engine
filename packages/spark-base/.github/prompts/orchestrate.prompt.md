---
type: prompt
name: orchestrate
description: Avvia l'Agent-Orchestrator per gestire un task E2E completo.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
agent: agent
spark: true
scf_owner: "spark-base"
---

Attiva Agent-Orchestrator per orchestrare il ciclo completo di sviluppo.

Task da orchestrare: ${input:task:Descrivi il task da implementare}

Istruzioni per l'orchestratore:
1. Leggi docs/TODO.md per verificare se c'è un task in corso.
2. Se il task è nuovo, parti da Fase 0 (analisi stato + conferma).
3. Se il task è in corso, riprendi dalla fase non completata.
4. Mostra il report di stato iniziale PRIMA di qualsiasi azione.
5. Rispetta tutti i checkpoint: chiedi conferma prima di avanzare.

Modalità operativa: orchestrazione completa con gate e checkpoint.
