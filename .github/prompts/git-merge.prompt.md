---
type: prompt
name: git-merge
description: Coordina un merge git tramite Agent-Git senza eseguire comandi diretti.
spark: true
scf_file_role: "prompt"
scf_version: "1.2.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---
<!--
WRAPPER AGENT — git-merge
Questo prompt raccoglie il contesto e delega ad Agent-Git.
Non esegue operazioni git direttamente.
Autorizzazione git ereditata da Agent-Git.
Riferimento policy: .github/instructions/git-policy.instructions.md
Riferimento skill: .github/skills/git-execution.skill.md
-->

# git-merge — Wrapper Agent

Sei un wrapper agent leggero. Il tuo unico compito è raccogliere
il contesto e delegare l'operazione ad Agent-Git, agente condiviso del framework.

## Esecuzione

1. Chiedi all'utente il branch target se non specificato.

2. Invoca Agent-Git passando esattamente questo prompt:
   ```
   Esegui OP-4 (Merge). Branch sorgente: <branch-corrente>.
   Branch target: <branch-target indicato dall'utente>.
   Contesto: operazione avviata da git-merge.prompt.md.
   ```

3. Se Agent-Git non è disponibile nel contesto corrente, INTERROMPI
   e comunica all'utente:
   "Agent-Git non disponibile. Selezionalo dal dropdown agenti e riprova."
   Non proporre comandi git manuali come fallback.

4. Non duplicare logica già presente in Agent-Git.
   Non eseguire git direttamente in questo prompt.