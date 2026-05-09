# SPARK Ops Layer

`spark-ops` contiene le risorse operative del framework SPARK che non sono necessarie al bootstrap o all'onboarding utente: orchestrazione E2E, manutenzione della documentazione framework e coordinamento release.

Il package e `mcp_only`: non scrive file nel workspace utente e dipende da `spark-base >= 2.0.0` per le skill condivise, le policy comuni e gli agenti user-facing.

## Risorse MCP

### Agenti

| Agente | Ruolo |
| --- | --- |
| `Agent-Orchestrator` | Coordina il ciclo E2E con gate e checkpoint |
| `Agent-FrameworkDocs` | Mantiene documentazione e changelog del framework |
| `Agent-Release` | Coordina versioning, package e release |

### Skill

| Skill | Ruolo |
| --- | --- |
| `semantic-gate` | Verifica semantica tra fasi Analyze, Design e Plan |
| `error-recovery` | Retry, escalata e recupero errori agenti |
| `task-scope-guard` | Protezione del perimetro nei task multi-step |

### Prompt

| Prompt | Ruolo |
| --- | --- |
| `orchestrate` | Avvia il ciclo E2E tramite `Agent-Orchestrator` |
| `release` | Avvia la release coordination tramite `Agent-Release` |
| `framework-changelog` | Aggiunge voci al changelog framework |
| `framework-release` | Consolida una release framework |
| `framework-update` | Sincronizza indice e documentazione framework |

## Non include

- `Agent-Research`, che resta in `spark-base` perche e fallback di agenti user-facing.
- `framework-unlock`, che resta in `spark-base` perche viene referenziato da guard e instruction base.
- Skill condivise come `git-execution`, `rollback-procedure`, `framework-scope-guard` e `semver-bump`, che restano in `spark-base` per evitare dipendenze inverse.
