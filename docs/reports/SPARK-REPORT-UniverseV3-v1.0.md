# SPARK-REPORT-UniverseV3-v1.0

**Data:** 2026-05-12
**Tipo:** Architetturale / Implementativo
**Autore:** spark-engine-maintainer
**Branch:** workspace-slim-registry-sync-20260511
**Status:** IMPLEMENTATO

---

## Obiettivo

Implementare il layer "Universe V3.0" per `spark-ops` come distribuzione MCP core,
distinguendo le risorse engine-self (Universe U1) dalle risorse esterne/registry (Universe U2).

---

## FASE 1-5: Analisi READ-ONLY

### AREA 1 — Mappa packages/spark-ops (U1 vs U2)

#### Struttura rilevata

```
packages/spark-ops/
├── package-manifest.json        (v1.1.0 → v1.2.0 dopo fix)
├── README.md
└── .github/
    ├── AGENTS.md
    ├── agents/
    │   ├── Agent-FrameworkDocs.md     [U1 — engine self]
    │   ├── Agent-Orchestrator.md      [non dichiarato nel manifest — gap]
    │   ├── Agent-Release.md           [U1 — engine self]
    │   ├── spark-assistant.agent.md   [U1 — engine self gateway]
    │   └── spark-guide.agent.md       [U1 — engine self gateway]
    ├── prompts/
    │   ├── framework-changelog.prompt.md  [U1]
    │   ├── framework-release.prompt.md    [U1]
    │   ├── framework-update.prompt.md     [U1]
    │   ├── orchestrate.prompt.md          [U1 — non dichiarato nel manifest — gap]
    │   └── release.prompt.md              [U1]
    └── skills/
        ├── error-recovery/
        ├── semantic-gate.skill.md
        └── task-scope-guard.skill.md
```

#### Gap identificati

| ID | Descrizione | Severity |
|----|-------------|----------|
| G-1 | `orchestrate.prompt.md` esiste fisicamente ma non dichiarato in `mcp_resources.prompts` né in `files` | HIGH |
| G-2 | `Agent-Orchestrator.md` esiste in spark-ops/.github/agents/ ma non dichiarato (duplicato da spark-base) | LOW |
| G-3 | `workspace_files: []` — file sentinella (spark-assistant, spark-guide) non trasferiti via boot transfer | HIGH |
| G-4 | JSON manifest ha `"instructions": []` duplicato (bug strutturale) | MEDIUM |

#### Classificazione U1 / U2

| Risorsa | Universe | Source Package |
|---------|----------|----------------|
| `spark-assistant` agent | U1 | spark-ops |
| `spark-guide` agent | U1 | spark-ops |
| `Agent-FrameworkDocs` agent | U1 | spark-ops |
| `Agent-Release` agent | U1 | spark-ops |
| `orchestrate` prompt | U1 | spark-ops |
| `framework-changelog` prompt | U1 | spark-ops |
| `framework-release` prompt | U1 | spark-ops |
| `framework-update` prompt | U1 | spark-ops |
| `release` prompt | U1 | spark-ops |
| Agenti in `.github/agents/` del workspace utente | U2 | workspace |
| Plugin SCF (scf-master-codecrafter, ecc.) | U2 | registry (GitHub) |

---

### AREA 2 — Analisi dispatcher MCP

**File analizzato:** `spark/boot/tools_resources.py`

#### Comportamento pre-Universe V3

- `scf_get_agent(name)` → iterava `inventory.list_agents()` → leggeva il file → restituiva payload senza indicazione della fonte.
- `scf_get_prompt(name)` → stessa logica, nessun campo `universe`.
- Non c'era distinzione tra risorse engine-local (U1) e risorse workspace/external (U2).
- Il commento AP.1 nel codice segnalava la divergenza tra `scf_get_agent` e `scf_get_agent_resource` ma non aggiungeva metadata utili all'utente.

#### Comportamento post-Universe V3

- `scf_get_agent(name)` → aggiunge `universe: "U1"|"U2"` e `source_package: str` nel payload.
- `scf_get_prompt(name)` → stessa aggiunta.
- Logica: `ff.path.resolve().is_relative_to(engine_root / "packages")` → U1 con `source_package` = primo segmento path (es. "spark-ops"). Altrimenti U2, `source_package = "workspace"`.

---

### AREA 3 — Boot flow spark-ops → .github workspace

#### Situazione pre-Universe V3

- `scf_bootstrap_workspace` (legacy mode) usava SOLO `packages/spark-base/.github/` come source.
- `spark-ops` aveva `workspace_files: []` → nessun file copiato nel workspace.
- I file `spark-assistant.agent.md` e `spark-guide.agent.md` venivano copiati nel workspace
  SOLO perché erano ancora fisicamente presenti in `packages/spark-base/.github/agents/`
  (residuo della separazione — file di spark-base non rimossi fisicamente nonostante la
  rimozione dal manifest v2.1.0).

#### Gap critico rilevato

Sebbene il bootstrap funzionasse per ragione storica (file fisicamente in spark-base),
l'ownership dichiarata dal manifest spark-ops non era supportata da alcun meccanismo
di transfer esplicito. In caso di rimozione fisica dei file da spark-base (prevista
in versioni future), il bootstrap sarebbe fallito silenziosamente.

#### Comportamento post-Universe V3

- `spark/boot/sequence.py` aggiunge `_ensure_spark_ops_workspace_files(context, engine_root)`
  chiamata dopo `ensure_minimal_bootstrap()`.
- La funzione legge `workspace_files` dal manifest di spark-ops e copia ogni file
  dalla source `packages/spark-ops/<rel_path>` verso `<github_root>/<within_github>`.
- **Idempotente**: non sovrascrive file già presenti.
- **Sicura**: logga warning se la source non esiste; non causa crash.

---

### AREA 4 — Update logic

**Distinzione chiave:**

| Scenario | Tool | Sorgente |
|----------|------|----------|
| "aggiornamenti spark-engine" | nessun tool MCP (locale Git) | GitHub releases / manuale |
| "aggiornamento spark-ops" | `scf_update_package("spark-ops")` | Universe A (local store) |
| "aggiornamento plugin X" | `scf_plugin_update("X")` | Universe B (registry GitHub) |

---

## FASE 6: Verdetto

**PROCEDERE** con implementazione.

**Rischio:** BASSO. Le modifiche sono additive:
- Il manifest spark-ops aggiunge campi senza rompere backward compatibility.
- Il dispatcher aggiunge campi nel payload senza modificare signature MCP.
- Il boot transfer è idempotente e non modifica file esistenti.
- I test aggiornati riflettono il nuovo design intenzionale.

---

## FASE 7: Implementazione

### File modificati

| File | Tipo | Descrizione |
|------|------|-------------|
| `packages/spark-ops/package-manifest.json` | manifest | v1.1.0 → v1.2.0: fix JSON, aggiungi orchestrate, workspace_files |
| `spark/boot/tools_resources.py` | code | U1/U2 detection in scf_get_agent e scf_get_prompt |
| `spark/boot/sequence.py` | code | _ensure_spark_ops_workspace_files() + chiamata post-bootstrap |
| `tests/test_spark_ops_decoupling_manifest.py` | test | Aggiorna MIGRATED_PROMPTS, fix asserzione workspace_files |
| `tests/test_universe_v3_distribution.py` | test | +4 test universe v3 |
| `CHANGELOG.md` | docs | Entry "universe: v3.0 core spark-ops MCP distribution" |

### Suite pytest

Target: ≥ 578 passed (pre-implementazione) + 4 nuovi test = ≥ 582 passed.

---

## Conclusioni

L'implementazione Universe V3.0 realizza:

1. **Manifest coherence** — spark-ops v1.2.0 con `orchestrate` dichiarato, `workspace_files`
   popolati, JSON senza duplicati.
2. **Dispatcher U1/U2** — `scf_get_agent` e `scf_get_prompt` espongono la provenienza
   delle risorse MCP per consentire routing intelligente ai chiamanti.
3. **Boot transfer esplicito** — `_ensure_spark_ops_workspace_files()` formalizza il
   meccanismo di copia workspace con idempotenza garantita.
4. **Test coverage** — 4 nuovi test verificano tutte le aree implementate.

La separazione `spark-base` (risorse fondamentali) / `spark-ops` (layer operativo)
è ora pienamente supportata a livello di manifest, dispatcher e boot flow.
