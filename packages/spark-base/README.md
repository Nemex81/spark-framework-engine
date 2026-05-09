# packages/spark-base/ — Layer Fondazionale SCF

**ID pacchetto:** `spark-base`  
**Versione corrente:** `1.7.3`  
**Schema manifest:** `3.1`  
**Delivery mode:** `mcp_only`  
**Motore minimo richiesto:** `3.1.0`

---

## Descrizione

`spark-base` è il layer fondazionale del framework SCF.
Definisce agenti base, skill condivise, instruction comuni e prompt
general-purpose riutilizzabili da tutti i plugin linguaggio-specifici.

**Non installa file fisici nel workspace utente** (`workspace_files: []`).
Tutte le risorse sono servite esclusivamente via MCP dall'engine store.

---

## Struttura locale

```
packages/spark-base/
├── package-manifest.json    Manifest pacchetto (schema 3.1)
└── .github/                 Risorse MCP del pacchetto
    ├── agents/              13 agenti
    ├── prompts/             30 prompt
    ├── skills/              23 skill
    └── instructions/        8 instruction
```

Le risorse in `.github/` sono copiate nello store engine al momento
dell'installazione e servite via URI `agents://`, `skills://`, ecc.
Non vengono mai scritte nel workspace utente.

---

## Risorse MCP esposte

### Agenti (13)

| Nome | Descrizione sintetica |
|------|-----------------------|
| `Agent-Analyze` | Discovery e analisi codebase (read-only) |
| `Agent-Docs` | Sincronizzazione documentazione (API.md, ARCHITECTURE.md, CHANGELOG.md) |
| `Agent-FrameworkDocs` | Manutenzione documentazione e changelog del framework |
| `Agent-Git` | Operazioni git autorizzate (commit, push, merge, tag) |
| `Agent-Helper` | Consultivo read-only sul framework installato |
| `Agent-Orchestrator` | Orchestratore autonomo del ciclo E2E |
| `Agent-Plan` | Breakdown architetturale in fasi implementabili |
| `Agent-Release` | Versioning, build, packaging e release coordination |
| `Agent-Research` | Fallback per ricerca linguaggio-dominio e best practice |
| `Agent-Validate` | Validazione, test coverage e quality gates |
| `Agent-Welcome` | Setup e manutenzione profilo progetto |
| `spark-assistant` | Gateway workspace: bootstrap, install/update/remove pacchetti |
| `spark-guide` | Onboarding e routing verso spark-assistant |

### Prompt (30)

Framework, git, release, onboarding, operazioni SCF
(`scf-install`, `scf-update`, `scf-remove`, `scf-status`, …)
e prompt di gestione documentazione (`sync-docs`, `framework-changelog`, …).

### Skill (23)

| Skill | Ambito |
|-------|--------|
| `changelog-entry` | Formato e sezione voci CHANGELOG |
| `conventional-commit` | Convenzione commit Conventional Commits |
| `document-template` | Template documenti di progetto |
| `error-recovery` | Procedura retry e escalata su errori agente |
| `file-deletion-guard` | Protezione eliminazione file |
| `framework-guard` | Protezione componenti framework protetti |
| `framework-index` | Panoramica framework da sorgenti interne |
| `framework-query` | Contratto output per Agent-Helper |
| `framework-scope-guard` | Delimitazione perimetro di modifica |
| `git-execution` | Matrice autorizzazioni comandi git per contesto agente |
| `project-doc-bootstrap` | Bootstrap iniziale documentazione di progetto |
| `project-profile` | Gestione project-profile.md |
| `project-reset` | Reset profilo progetto |
| `rollback-procedure` | Procedura rollback standardizzata |
| `semantic-gate` | Gate semantico per validazione output |
| `semver-bump` | Calcolo bump semantico da diff |
| `task-scope-guard` | Protezione scope durante task multi-file |
| `validate-accessibility` | Checklist accessibilità WAI-ARIA |
| + 5 altri | `accessibility-output`, `agent-selector`, `framework-guard`, `personality`, `style-setup`, `verbosity` |

### Instruction (8)

`framework-guard`, `git-policy`, `model-policy`, `personality`,
`project-reset`, `spark-assistant-guide`, `verbosity`, `workflow-standard`

---

## Compatibilità e dipendenze

- **Nessuna dipendenza** su altri pacchetti SCF
- **Tutti i plugin** (`scf-master-codecrafter`, `scf-pycode-crafter`, …)
  elencano `spark-base` come dipendenza diretta
- `file_ownership_policy: "error"` — conflitti di ownership bloccano l'installazione
