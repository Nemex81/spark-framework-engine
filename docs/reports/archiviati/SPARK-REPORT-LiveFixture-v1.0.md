# SPARK-REPORT — Live Fixture Fix v1.0

**Data:** 2026-05-09
**Branch:** `feature/dual-mode-manifest-v3.1`
**Autore:** spark-engine-maintainer
**Status:** COMPLETATO

---

## 1. Obiettivo

Correggere i 4 test fallenti in `tests/test_integration_live.py` identificati
come pre-merge blocker R1 dal report `SPARK-REPORT-MergeReadiness-Step5-v1.0.md`.

**Target di accettazione:**
- Tutti e 4 i live test PASS
- Suite non-live ≥ 472 passed (baseline pre-fix)
- Nessuna modifica a `spark-framework-engine.py`

---

## 2. Analisi delle cause radice

### Bug A — Fixture mancante: `orchestrator-state.json`

**File:** `tests/test_integration_live.py` — fixture `tmp_workspace`
**Causa:** La fixture creava un `.github/` vuoto senza inizializzare
`runtime/orchestrator-state.json`. Il gate `_is_github_write_authorized_v3()`
in `spark/boot/lifecycle.py` leggeva questo file e lo trovava assente →
restituiva `github_write_authorized = False` → tutti e 4 i tool `scf_install_*`
bloccavano l'esecuzione prima ancora di toccare la rete.
**Impatto:** 4/4 test bloccati.

### Bug B — `_normalize_string_list` su dipendenze schema 3.1

**File:** `spark/boot/install_helpers.py`, `spark/core/utils.py`
**Causa:** Il manifest di `scf-master-codecrafter` dichiara le dipendenze come
oggetti `{"id": "spark-base", "min_version": "1.6.1"}` (schema 3.1). La funzione
`_normalize_string_list` trattava ogni oggetto come stringa tramite `repr()`,
producendo `'{"id": "spark-base", ...}'` che non corrispondeva a nessun pacchetto
installato → `missing_dependencies = ["{'id': 'spark-base', ...}"]` → install
bloccato per dipendenza mancante.
**Impatto:** Test 2 e 4 bloccati dopo Fix A.

### Bug C — Sentinel entry `__store__/` in manifest + replan assertion

**File:** `tests/test_integration_live.py`
**Causa-1:** Il registry v3 (`spark/registry/v3_store.py:17`) scrive in manifest
una entry con `"file": "__store__/{package_id}"` come sentinella di idempotenza.
L'assertion `{entry["file"] for entry in master_entries} == expected_files`
includeva questa sentinella nel set, causando mismatch.
**Causa-2:** L'assertion `len(replan["write_plan"]) + len(replan["extend_plan"]) == len(expected_files)`
assumeva che `scf_plan_install` usi `workspace_files + plugin_files` (14 file),
ma in realtà usa `files` (19 file, includendo changelogs/skills/prompts store-only).
I file store-only appaiono come `create_new` nel write_plan, non come
`update_tracked_clean`, e non sono in `expected_files`.
**Impatto:** Test 1 fallente.

### Bug D — Nome file agente stale pre-rename

**File:** `tests/test_integration_live.py`
**Causa:** `conflict_rel = ".github/agents/Agent-Code.md"` — nome pre-rename.
Dopo la razionalizzazione con prefisso `code-`, il file si chiama
`code-Agent-Code.md`. Il file "untracked" creato dalla fixture non corrispondeva
ad alcun file dichiarato in `plugin_files` → nessun conflitto rilevato.
**Impatto:** Test 3 fallente (fase rilevazione conflitti).

### Bug E — Mancanza pre-check conflitti `plugin_files` nel path v3

**File:** `spark/boot/tools_packages_install.py`
**Causa:** Nel branch v3 di `scf_install_package`, il check
`conflict_mode="abort"` per i `plugin_files` non veniva mai eseguito. La verifica
untracked-conflict esisteva solo nel path v2 legacy (riga 705), mai raggiunto
per pacchetti `min_engine_version >= 3.0.0`. L'install avanzava fino al download
nello store e poi installava i plugin_files sovrascrivendo il file untracked.
**Impatto:** Test 3 fallente (`result["success"] is True` invece di `False`).

---

## 3. Interventi applicati

### Fix A — Inizializzazione `orchestrator-state.json` in fixture

```python
# tests/test_integration_live.py — fixture tmp_workspace
runtime_dir = github_root / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)
(runtime_dir / "orchestrator-state.json").write_text(
    json.dumps({
        "github_write_authorized": True,
        "current_phase": "",
        ...
    }, indent=2),
    encoding="utf-8",
)
```

### Fix B — `_normalize_dependency_ids()` in `spark/core/utils.py`

Aggiunta helper che gestisce sia stringhe plain che oggetti `{"id": ...}`.
`_get_package_install_context()` aggiornata per usarla al posto di
`_normalize_string_list()` per il campo `dependencies`.

### Fix C1 — Filtro sentinel `__store__/` in manifest assertion

```python
master_entries = [
    entry for entry in entries
    if entry["package"] == "scf-master-codecrafter"
    and not str(entry.get("file", "")).startswith("__store__/")
]
```

### Fix C2 — Replan assertion corretta

Sostituita l'assertion basata su count totale con una che verifica che tutti
i file installati (`expected_files` = workspace_files + plugin_files) siano
presenti in `write_plan` o `extend_plan` come `update_tracked_clean` /
`extend_section`, indipendentemente dai file store-only.

### Fix D — Aggiornamento `conflict_rel` post-rename

```python
conflict_rel = ".github/agents/code-Agent-Code.md"  # ex: Agent-Code.md
```

### Fix E — Pre-check conflitti `plugin_files` nel branch v3

In `tools_packages_install.py`, aggiunto blocco prima di `_install_package_v3`:

```python
_v3_plugin_files_check = list(pkg_manifest.get("plugin_files") or [])
if _v3_plugin_files_check and conflict_mode == "abort":
    _v3_precheck = _classify_install_files(package_id, _v3_plugin_files_check, file_policies)
    _v3_untracked = [
        item for item in _v3_precheck.get("conflict_plan", [])
        if item.get("classification") == "conflict_untracked_existing"
    ]
    if _v3_untracked:
        return _build_install_result(False, error=..., conflicts_detected=_v3_untracked, ...)
```

---

## 4. File modificati

| File | Tipo modifica | Bug risolto |
|------|---------------|-------------|
| `tests/test_integration_live.py` | Fixture + assertion | A, C1, C2, D |
| `spark/core/utils.py` | Nuova helper | B |
| `spark/boot/install_helpers.py` | Usa nuova helper | B |
| `spark/boot/tools_packages_install.py` | Pre-check v3 plugin_files | E |

---

## 5. Risultati di validazione

| Round | Comando | Risultato |
|-------|---------|-----------|
| Baseline (pre-fix) | `pytest tests/ -q --tb=short` | 4 failed, 470 passed |
| Round 2 (post Fix A+B+D) | `pytest tests/ -q --tb=short` | 2 failed, 474 passed |
| Round 3 (post Fix C1+C2) | `pytest tests/ -q --tb=short` | 1 failed, 475 passed |
| Round 4 (post Fix E) | `pytest tests/ -q --tb=short` | **476 passed, 9 skipped** |

---

## 6. Invarianti rispettati

- Nessuna modifica a `spark-framework-engine.py`
- Nessuna modifica a `.github/` (framework_edit_mode: false)
- Nessun `print()` in `src/`
- Baseline non-live: 476 passed ≥ 472 richiesti
- Type hints presenti su `_normalize_dependency_ids()`
- Fix E chirurgico: pre-check solo per `conflict_mode="abort"`, nessun impatto
  su `conflict_mode="replace"` o `"auto"`

---

## 7. Note architetturali

**Bug E è un gap pre-esistente**, non introdotto dalla sessione corrente.
Il path v2 legacy controllava i conflitti `plugin_files` prima dell'install
(riga 705 in `tools_packages_install.py`). Il path v3 non aveva questa guardia.
Fix E la aggiunge in modo minimale, usando `_classify_install_files` già
disponibile nella closure `scf_install_package`, senza modificare lifecycle.py
né PluginInstaller.

**Bug B diagnostica:** La radice era lo schema 3.1 delle dipendenze. Tutti i
pacchetti con `min_engine_version >= 3.0.0` e dipendenze object-typed
(`{"id": ..., "min_version": ...}`) erano affetti. Il fix è retrocompatibile:
dipendenze string-format continuano a funzionare.

---

## 8. Stato branch post-fix

- Branch: `feature/dual-mode-manifest-v3.1`
- Test suite: **476 passed, 9 skipped, 0 failed**
- CHANGELOG.md: aggiornato in `[Unreleased]` sezione "Fixed — Live Fixture Fix v1.0"
- Merge readiness: VERDE (tutti i blocker R1 risolti)
