# SPARK Report — Post-Dual-Universe Cleanup v1.0

**Data**: 2026-05-11
**Branch**: workspace-slim-registry-sync-20260511
**Autore**: spark-engine-maintainer
**Suite di riferimento**: `pytest tests/ --ignore=tests/test_integration_live.py`

---

## Sommario esecutivo

Dopo il completamento del task Dual Universe (Universo A locale / Universo B remoto),
è stata eseguita una sessione di pulizia su 3 task sequenziali:

| Task | Titolo | Risultato |
|------|--------|-----------|
| T1 | Fix 19 async test skippati | PASS |
| T2 | scf_verify_system gap analysis e copertura | PASS |
| T3 | GAP-Y-2 Bootstrap Preservation — verifica completezza | PASS |

**Suite finale**: 575 passed, 1 failed (pre-esistente), 0 skipped, 0 regressioni.

---

## TASK 1 — Fix 19 async test skippati

### Problema

19 test `async def` distribuiti in due file erano saltati da pytest per
assenza di `pytest-asyncio`. Il `pyproject.toml` dichiara `asyncio_mode = "auto"`
ma il package non era installato nell'ambiente `audiomaker311`.

### Soluzione

Aggiunta hook `pytest_pyfunc_call` in `tests/conftest.py`:

```python
@pytest.hookimpl(tryfirst=True)
def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    if not asyncio.iscoroutinefunction(pyfuncitem.function):
        return None
    funcargs = pyfuncitem.funcargs
    argnames = pyfuncitem._fixtureinfo.argnames
    testargs = {arg: funcargs[arg] for arg in argnames if arg in funcargs}
    asyncio.run(pyfuncitem.obj(**testargs))
    return True
```

**Vincolo rispettato**: zero nuove dipendenze.

### File modificati

- `tests/conftest.py` — import `asyncio` + hook `pytest_pyfunc_call`

### Risultato

```
22 passed  (test_legacy_init_audit.py: 12, test_bootstrap_workspace_extended.py: 10)
0 skipped
```

---

## TASK 2 — scf_verify_system gap analysis e copertura

### Analisi scf_verify_system

Output tool prima del fix:

```json
{
  "is_coherent": false,
  "issues": [{
    "type": "engine_min_mismatch",
    "package": "spark-base",
    "registry_engine_min": "3.1.0",
    "manifest_engine_min": "3.4.0",
    "fix": "Aggiornare registry.json: min_engine_version → 3.4.0"
  }]
}
```

### Fix registry cache

Entrambi i file cache aggiornati con `min_engine_version: "3.4.0"`:
- `.scf-registry-cache.json`
- `.github/.scf-registry-cache.json`

Pacchetti aggiornati: `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`.

### Copertura RegistryClient

File `spark/registry/client.py` — copertura precedente: **39%** (righe 53-64, 68-71,
78-84, 87-93, 96-104, 114-127, 138 non coperte).

Nuovo file `tests/test_registry_client.py` — 18 test con mock completo di rete:
- Costruttore e cache_path
- `fetch()` — validazione URL, successo rete, fallback cache
- `list_packages()` — successo e fallback RuntimeError
- `_load_cache()` — file mancante, JSON corrotto, successo
- `_save_cache()` — scrittura e gestione OSError
- `fetch_package_manifest()` — validazione URL, costruzione raw URL, mock risposta, errori
- `fetch_raw_file()` — mock urlopen completo

**Copertura finale: 90%** (righe 78-84, 92-93 richiedono rete reale — accettabile).

---

## TASK 3 — GAP-Y-2 Bootstrap Preservation — verifica completezza

### Stato implementazione

Il GAP-Y-2 (Bootstrap Preservation) era **già implementato** in `tools_bootstrap.py`:

| Campo payload | Linea | Stato |
|---------------|-------|-------|
| `files_protected` | 1067 | Presente |
| `files_conflict_non_spark` | 1071 | Presente |
| `files_conflict_spark_outdated` | 1072 | Presente |
| `spark_outdated_details` | 1073 | Presente |
| `files_updated_frontmatter_only` | 1074 | Presente |
| `_apply_frontmatter_only_update()` | 96 | Presente |

### Test GAP-Y-2 (già in test_legacy_init_audit.py)

Tutti 9 test erano skippati per il problema async (risolto in TASK 1).
Dopo il fix, tutti **PASS**:

| Test | Scenario | Risultato |
|------|----------|-----------|
| `test_bootstrap_classifies_non_spark_conflict_file` | Scenario X | PASS |
| `test_bootstrap_non_spark_conflict_payload_is_empty_on_clean_workspace` | Scenario X clean | PASS |
| `test_bootstrap_classifies_spark_outdated_conflict_file` | Scenario Y | PASS |
| `test_bootstrap_spark_outdated_includes_version_details` | Scenario Y dettagli | PASS |
| `test_bootstrap_non_md_file_classified_as_non_spark` | Scenario Y non-.md | PASS |
| `test_force_true_updates_frontmatter_only_for_spark_outdated` | GAP-Y-2 force | PASS |
| `test_force_true_preserves_user_body_when_spark_outdated` | GAP-Y-2 body | PASS |
| `test_force_true_non_spark_file_still_gets_full_overwrite` | GAP-Y-2 non-SPARK | PASS |
| `test_force_true_spark_outdated_payload_on_clean_workspace` | GAP-Y-2 clean | PASS |

---

## Gate finale

```
GATE: PASS
Suite: 575 passed, 1 failed (pre-existing: test_spark_base_manifest_no_longer_exports_operational_resources),
       0 skipped, 0 regressions
Delta vs baseline: +37 test (19 async riabilitati + 18 registry client)
```

### File toccati da questa sessione

| File | Tipo modifica |
|------|---------------|
| `tests/conftest.py` | MODIFIED — import asyncio + hook pytest_pyfunc_call |
| `tests/test_registry_client.py` | NEW — 18 test RegistryClient |
| `.scf-registry-cache.json` | MODIFIED — min_engine_version 3.1.0→3.4.0 |
| `.github/.scf-registry-cache.json` | MODIFIED — min_engine_version 3.1.0→3.4.0 |
| `CHANGELOG.md` | MODIFIED — sezione Post-Dual-Universe Cleanup |
| `docs/reports/SPARK-REPORT-PostDualUniverse-v1.0.md` | NEW — questo file |
