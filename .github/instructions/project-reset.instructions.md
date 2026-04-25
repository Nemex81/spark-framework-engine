---
spark: true
scf_owner: "spark-base"
scf_version: "1.4.0"
scf_file_role: "instruction"
scf_merge_strategy: "replace"
scf_merge_priority: 10
scf_protected: false
name: project-reset
applyTo: ".github/**"
version: 1.0.0
---

# Instruction: Project Reset

Questa instruction descrive il comportamento atteso quando un agente o una
skill devono resettare il profilo progetto in `.github/project-profile.md`.

## Regole operative

- Prima di ogni operazione, verifica `framework_edit_mode` in `.github/project-profile.md`.
  - Se `false`: interrompi e indirizza l'utente a `#framework-unlock`.
  - Se `true`: procedi solo entro il perimetro dichiarato.
- Usa la skill `project-reset` per eseguire il flusso di reset guidato.
- Esegui sempre un backup del file prima di cancellare o modificare il frontmatter.
- Non eseguire commit o push automaticamente: proponi i comandi git oppure delega ad Agent-Git.

## Messaggi e conferme

- Richiedi conferma esplicita dell'utente con la frase `RESET PROFILO` prima di procedere con azioni distruttive.
- Registra sempre l'azione nel changelog framework del package come voce di audit o mostra la voce proposta al termine della procedura.

## Esempio di integrazione

Agent-Welcome puo offrire l'opzione "Reset profilo progetto" che, dopo aver raccolto le conferme e aver eseguito il backup, chiama `project-reset`.