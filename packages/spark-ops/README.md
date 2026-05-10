# SPARK Ops Layer

`spark-ops` contiene le risorse operative del framework SPARK: onboarding e routing utente (spark-assistant, spark-guide), manutenzione della documentazione framework e coordinamento release.

Il package e `mcp_only`: non scrive file nel workspace utente e dipende da `spark-base >= 2.0.0` per le skill condivise, le policy comuni e il core operativo.

## Risorse MCP

### Agenti

| Agente | Ruolo |
| --- | --- |
| `spark-assistant` | Onboarding workspace, installazione e aggiornamento pacchetti SCF |
| `spark-guide` | Orientamento utente, routing verso spark-assistant |
| `Agent-FrameworkDocs` | Mantiene documentazione e changelog del framework |
| `Agent-Release` | Coordina versioning, package e release |

### Prompt

| Prompt | Ruolo |
| --- | --- |
| `release` | Avvia la release coordination tramite `Agent-Release` |
| `framework-changelog` | Aggiunge voci al changelog framework |
| `framework-release` | Consolida una release framework |
| `framework-update` | Sincronizza indice e documentazione framework |

## Non include

- `Agent-Orchestrator`, che e tornato in `spark-base` come agente core del ciclo E2E utente.
- `Agent-Research`, che resta in `spark-base` perche e fallback di agenti user-facing.
- `framework-unlock`, che resta in `spark-base` perche viene referenziato da guard e instruction base.
- `orchestrate` prompt, che segue `Agent-Orchestrator` in `spark-base`.
- Skill operative (`semantic-gate`, `error-recovery`, `task-scope-guard`), che sono in `spark-base` insieme a `Agent-Orchestrator`.
