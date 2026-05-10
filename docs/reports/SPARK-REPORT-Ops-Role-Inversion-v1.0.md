---
spark: true
scf_file_role: "report"
scf_version: "1.0.0"
report_version: "1.0.0"
status: "COMPLETED"
date: "2026-05-10"
author: "spark-engine-maintainer"
task: "spark-ops-role-inversion-correction-v1.0"
---

# SPARK Report — Ops Role Inversion Correction

## Sommario

Inversione concettuale della distribuzione dei ruoli tra `spark-base` e `spark-ops`,
a seguito dell'analisi che ha identificato un errore nel task precedente:

- `Agent-Orchestrator` è un agente **user-operativo** (coordina il ciclo E2E
  Analyze→Plan→Code→Validate→Docs→Release che l'utente avvia ogni giorno) →
  appartiene a `spark-base`.
- `spark-assistant` e `spark-guide` sono **gateway sistemici** (onboarding workspace,
  installazione pacchetti, routing) → appartengono a `spark-ops`.

## Motivazione architetturale

| Agente | Frequenza d'uso | Soggetto | Package corretto |
|--------|----------------|---------|-----------------|
| `Agent-Orchestrator` | Ogni sessione di sviluppo | Utente finale | `spark-base` |
| `spark-assistant` | Setup, manutenzione workspace | Sistema/admin | `spark-ops` |
| `spark-guide` | Onboarding, orientamento | Sistema/admin | `spark-ops` |

## Modifiche applicate

### Nuovi file fisici creati

- `packages/spark-ops/.github/agents/spark-assistant.agent.md` (scf_owner: spark-ops)
- `packages/spark-ops/.github/agents/spark-guide.agent.md` (scf_owner: spark-ops)

### File fisici già esistenti (nessun cambio)

- `packages/spark-base/.github/agents/Agent-Orchestrator.md` (scf_owner: spark-base)
- `packages/spark-base/.github/skills/error-recovery/SKILL.md`
- `packages/spark-base/.github/skills/semantic-gate.skill.md`
- `packages/spark-base/.github/skills/task-scope-guard.skill.md`
- `packages/spark-base/.github/prompts/orchestrate.prompt.md`

### Manifest aggiornati

#### `packages/spark-base/package-manifest.json` — v2.0.0 → v2.1.0

- **mcp_resources.agents**: rimossi `spark-assistant`, `spark-guide`; aggiunto `Agent-Orchestrator`
- **mcp_resources.prompts**: aggiunto `orchestrate`
- **mcp_resources.skills**: aggiunti `error-recovery`, `semantic-gate`, `task-scope-guard`
- **files[]**: rimossi `spark-assistant.agent.md`, `spark-guide.agent.md`; aggiunti
  `Agent-Orchestrator.md`, `orchestrate.prompt.md`, `error-recovery/SKILL.md`,
  `semantic-gate.skill.md`, `task-scope-guard.skill.md`
- **files_metadata[]**: aggiornato di conseguenza (6 patch)
- **engine_provided_skills[]**: aggiunti `error-recovery`, `semantic-gate`, `task-scope-guard`

#### `packages/spark-ops/package-manifest.json` — v1.0.0 → v1.1.0

- **mcp_resources.agents**: rimosso `Agent-Orchestrator`; aggiunti `spark-assistant`, `spark-guide`
- **mcp_resources.prompts**: rimosso `orchestrate`
- **mcp_resources.skills**: svuotato (tutte le 3 skill tornate in spark-base)
- **files[]**: rimosso `Agent-Orchestrator.md`, `orchestrate.prompt.md`, 3 skill files;
  aggiunti `spark-assistant.agent.md`, `spark-guide.agent.md`
- **files_metadata[]**: aggiornato di conseguenza
- **engine_provided_skills[]**: svuotato

### Test aggiornati

- `tests/test_spark_ops_decoupling_manifest.py`:
  - `MIGRATED_AGENTS`: `{Agent-FrameworkDocs, Agent-Release, spark-assistant, spark-guide}`
  - `MIGRATED_PROMPTS`: `{framework-changelog, framework-release, framework-update, release}`
  - `MIGRATED_SKILLS`: `set()`
  - `BASE_OWNED_AFTER_SPLIT["agents"]`: `{Agent-Research, Agent-Git, Agent-Orchestrator}`
  - Version check: `"2.1.0"`

### Documentazione aggiornata

- `packages/spark-ops/.github/AGENTS.md` — rimosso Orchestrator, aggiunti assistant/guide
- `packages/spark-base/.github/AGENTS.md` — aggiunto Orchestrator, rimossi assistant/guide
- `packages/spark-ops/README.md` — aggiornato con la nuova lista risorse
- `packages/spark-ops/.github/changelogs/spark-ops.md` — voce [Unreleased] v1.1.0
- `packages/spark-base/.github/changelogs/spark-base.md` — voce [Unreleased] v2.1.0
- `CHANGELOG.md` — sezione "Fixed — spark-ops role inversion (2026-05-10)"

## Validazione

```
pytest -q --ignore=tests/test_integration_live.py
550 passed, 9 skipped, 12 subtests passed (0 failed)

pytest tests/test_spark_ops_decoupling_manifest.py -v
4 passed in 0.04s
```

## Dipendenza fra package (invariata)

```
spark-base  v2.1.0  (no deps)
    ↑
spark-ops   v1.1.0  (spark-base >= 2.0.0)
    ↑
scf-master-codecrafter  (spark-base >= 2.0.0, spark-ops >= 1.0.0)
    ↑
scf-pycode-crafter  (scf-master-codecrafter >= 2.7.0)
```

## Conformità

- Nessun file fisico eliminato (file-deletion-guard rispettato)
- Nessuna scrittura su `.github/` del workspace root
- Nessun commit autonomo (vedi sezione comandi proposti)
- Engine_provided_skills = files[] skills = mcp_resources.skills (coerenza manifesto)

## Comandi da eseguire manualmente

```bash
git add packages/spark-base/package-manifest.json
git add packages/spark-ops/package-manifest.json
git add packages/spark-ops/.github/agents/spark-assistant.agent.md
git add packages/spark-ops/.github/agents/spark-guide.agent.md
git add packages/spark-ops/.github/AGENTS.md
git add packages/spark-base/.github/AGENTS.md
git add packages/spark-ops/README.md
git add packages/spark-ops/.github/changelogs/spark-ops.md
git add packages/spark-base/.github/changelogs/spark-base.md
git add tests/test_spark_ops_decoupling_manifest.py
git add CHANGELOG.md
git add docs/reports/SPARK-REPORT-Ops-Role-Inversion-v1.0.md
git commit -m "fix(ops): invert roles Agent-Orchestrator→spark-base v2.1.0, spark-assistant/guide→spark-ops v1.1.0"
```
