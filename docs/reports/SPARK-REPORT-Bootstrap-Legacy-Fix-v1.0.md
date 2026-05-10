# SPARK REPORT — Bootstrap Legacy Fix v1.0

**Data:** 2026-05-10  
**Branch:** `feature/dual-mode-manifest-v3.1`  
**Basato su:** `spark-bootstrap-legacy-fix-fullcycle-v1.0`  
**Autore:** spark-engine-maintainer  
**Stato:** VERDE PER MERGE

---

## 1. Sintesi

Fix completo del gap bloccante identificato in `SPARK-REPORT-Legacy-Audit-v1.0`:  
il bootstrap sentinel era hardcoded su `spark-assistant.agent.md` e `spark-guide.agent.md`,  
file non più presenti nel manifest `spark-base v2.1.0` post role-inversion.  
Il sentinel è stato sostituito con `Agent-Welcome.md` (agente neutro, sempre in `spark-base`).  
Tutti i riferimenti nei test e nella documentazione sono stati allineati.

---

## 2. Cicli iterativi

| Ciclo | Fase | Verdetto |
|-------|------|----------|
| Pre-impl 1 | Analisi + Strategia v1.0 | PASS (nessuna iterazione extra) |
| Post-impl 1 | Test bootstrap focused | PASS (17/17, 6 skipped) |
| Post-impl 2 | Full suite non-live | PASS (550/550, 9 skipped) |

Cicli extra: 0 — strategia accettata al primo ciclo.

---

## 3. Modifiche — file e righe coinvolte

### Engine / Boot

| File | Modifica |
|------|----------|
| `spark/boot/tools_bootstrap.py` | `sentinel` e `sentinel_rel`: `spark-assistant.agent.md` → `Agent-Welcome.md`; `_SPARK_BASE_BOOTSTRAP_SENTINELS`: rimossi `spark-guide.agent.md` e `spark-assistant.agent.md`, aggiunto `Agent-Welcome.md` |
| `spark/boot/install_helpers.py` | `sentinel_path` in `_detect_workspace_migration_state`: `agents/spark-assistant.agent.md` → `AGENTS.md` |

### Documentazione pacchetti

| File | Modifica |
|------|----------|
| `packages/spark-base/.github/AGENTS.md` | Rimosso `"da \`spark-ops\`"` dalla riga "Invocato da" di Agent-Research |
| `packages/spark-base/README.md` | Versione `2.0.0` → `2.1.0`; tabella agenti 10→9 (rimossi `spark-assistant`, `spark-guide`; aggiunto `Agent-Orchestrator`); nota skill corretta (`semantic-gate/error-recovery/task-scope-guard` sono in `spark-base` da v2.1.0) |

### Test

| File | Modifica |
|------|----------|
| `tests/test_bootstrap_workspace.py` | ~14 sostituzioni sentinel; `test_bootstrap_does_not_retrack_spark_guide_when_owned_by_spark_base` rinominato in `test_bootstrap_does_not_retrack_agent_welcome_when_owned_by_spark_base` e riscritto; skipped tests aggiornati per compatibilità |
| `tests/test_bootstrap_workspace_extended.py` | ~6 sostituzioni sentinel; `test_bootstrap_preserves_missing_cross_owner_file_without_rewriting` aggiornato da `spark-guide.agent.md` → `instructions/framework-guard.instructions.md` |

### Documentazione progetto

| File | Modifica |
|------|----------|
| `CHANGELOG.md` | Voce `[Unreleased]` aggiunta: "Fixed — bootstrap sentinel legacy → Agent-Welcome.md" |

---

## 4. Test risultati finali

```
pytest -q --ignore=tests/test_integration_live.py
550 passed, 9 skipped, 12 subtests passed — 0 failed
```

Bootstrap focused:

```
pytest tests/test_bootstrap_workspace.py tests/test_bootstrap_workspace_extended.py -q --tb=short
17 passed, 6 skipped — 0 failed
```

---

## 5. Piano cleanup legacy (MANUALE — Nemex81)

I seguenti file fisici in `packages/spark-base/.github/` sono **legacy post spark-ops v1.1.0**  
e non sono più presenti nel manifest v2.1.0.  
Il bootstrap non li usa più (sentinel aggiornato). Possono essere rimossi con sicurezza.

### File da rimuovere (8)

```bash
# Agenti legacy — ora in spark-ops
git rm packages/spark-base/.github/agents/Agent-FrameworkDocs.md
git rm packages/spark-base/.github/agents/Agent-Release.md
git rm packages/spark-base/.github/agents/spark-assistant.agent.md
git rm packages/spark-base/.github/agents/spark-guide.agent.md

# Prompt legacy — ora in spark-ops
git rm "packages/spark-base/.github/prompts/framework-changelog.prompt.md"
git rm "packages/spark-base/.github/prompts/framework-release.prompt.md"
git rm "packages/spark-base/.github/prompts/framework-update.prompt.md"
git rm "packages/spark-base/.github/prompts/release.prompt.md"
```

### File da preservare (2 — storici/design)

```bash
# Preservare come riferimento storico o documento di design
# packages/spark-base/.github/prompts/package-update.prompt.md
# packages/spark-base/.github/prompts/spark-engine-decoupling-validation.prompt.md
```

### Commit proposto post-cleanup

```bash
git add packages/spark-base/.github/AGENTS.md packages/spark-base/README.md
git add spark/boot/tools_bootstrap.py spark/boot/install_helpers.py
git add tests/test_bootstrap_workspace.py tests/test_bootstrap_workspace_extended.py
git add CHANGELOG.md docs/reports/SPARK-REPORT-Bootstrap-Legacy-Fix-v1.0.md
git commit -m "fix(bootstrap): sentinel legacy → Agent-Welcome.md; docs: spark-base v2.1.0 align"

# Dopo git rm dei legacy files:
git commit -m "chore(legacy): rm spark-base legacy files post spark-ops v1.1.0"
```

---

## 6. Verdetto

**VERDE PER MERGE**

- Gap bloccante GIALLO risolto: nessun riferimento hardcoded a file legacy nel bootstrap
- Test suite mantenuta: 550 passed, 0 failed (baseline invariata)
- Documentazione allineata: AGENTS.md, README, CHANGELOG
- Piano cleanup legacy pronto con comandi git copy-paste
