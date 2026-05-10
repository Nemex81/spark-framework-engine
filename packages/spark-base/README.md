<!-- markdownlint-disable MD040 MD060 -->

# packages/spark-base/ — Layer Fondazionale SCF

**ID pacchetto:** `spark-base`  
**Versione corrente:** `2.1.0`  
**Schema manifest:** `3.1`  
**Delivery mode:** `mcp_only`  
**Motore minimo richiesto:** `3.1.0`

---

## Descrizione

`spark-base` è il layer fondazionale del framework SCF.
Definisce agenti base user-facing, skill condivise, instruction comuni e prompt
general-purpose riutilizzabili da tutti i plugin linguaggio-specifici.

Le risorse operative di framework maintenance e ciclo E2E vivono ora in
`spark-ops`, che dipende da `spark-base` senza creare dipendenze inverse.

**Non installa file fisici nel workspace utente** (`workspace_files: []`).
Tutte le risorse sono servite esclusivamente via MCP dall'engine store.

---

## Struttura locale

```
packages/spark-base/
├── package-manifest.json    Manifest pacchetto (schema 3.1)
└── .github/                 Risorse MCP del pacchetto
    ├── agents/              9 agenti user-facing/support
    ├── prompts/             25 prompt user-facing e SCF lifecycle
    ├── skills/              20 skill condivise
    └── instructions/        8 instruction
```

Le risorse in `.github/` sono copiate nello store engine al momento
dell'installazione e servite via URI `agents://`, `skills://`, ecc.
Non vengono mai scritte nel workspace utente.

---

## Risorse MCP esposte

### Agenti (9)

| Nome | Descrizione sintetica |
|------|-----------------------|
| `Agent-Analyze` | Discovery e analisi codebase (read-only) |
| `Agent-Docs` | Sincronizzazione documentazione (API.md, ARCHITECTURE.md, CHANGELOG.md) |
| `Agent-Git` | Operazioni git autorizzate (commit, push, merge, tag) |
| `Agent-Helper` | Consultivo read-only sul framework installato |
| `Agent-Orchestrator` | Orchestratore E2E autonomo (ciclo Analyze→Release) |
| `Agent-Plan` | Breakdown architetturale in fasi implementabili |
| `Agent-Research` | Fallback per ricerca linguaggio-dominio e best practice |
| `Agent-Validate` | Validazione, test coverage e quality gates |
| `Agent-Welcome` | Setup e manutenzione profilo progetto |

### Prompt (25)

Git, onboarding, operazioni SCF
(`scf-install`, `scf-update`, `scf-remove`, `scf-status`, …)
e prompt di gestione documentazione progetto (`sync-docs`, `project-*`, …).

I prompt operativi `orchestrate`, `release`, `framework-changelog`,
`framework-release` e `framework-update` sono forniti da `spark-ops`.

### Skill (20)

| Skill | Ambito |
|-------|--------|
| `changelog-entry` | Formato e sezione voci CHANGELOG |
| `conventional-commit` | Convenzione commit Conventional Commits |
| `document-template` | Template documenti di progetto |
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
| `semver-bump` | Calcolo bump semantico da diff |
| `validate-accessibility` | Checklist accessibilità WAI-ARIA |
| + 5 altri | `accessibility-output`, `agent-selector`, `personality`, `style-setup`, `verbosity` |

Le skill operative `semantic-gate`, `error-recovery` e `task-scope-guard`
sono incluse in `spark-base` da v2.1.0.

### Instruction (8)

`framework-guard`, `git-policy`, `model-policy`, `personality`,
`project-reset`, `spark-assistant-guide`, `verbosity`, `workflow-standard`

---

## Compatibilità e dipendenze

- **Nessuna dipendenza** su altri pacchetti SCF
- **`spark-ops` dipende da `spark-base`**, non il contrario
- **Tutti i plugin** (`scf-master-codecrafter`, `scf-pycode-crafter`, …)
  elencano `spark-base` come dipendenza diretta
- `file_ownership_policy: "error"` — conflitti di ownership bloccano l'installazione
