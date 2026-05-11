# SPARK REPORT — Pytest Warnings Resolution v1.0

**Data:** 2026-05-11  
**Tipo:** Documentazione tecnica — nessuna modifica al codice motore  
**Autore:** spark-engine-maintainer  
**Branch:** `workspace-slim-registry-sync-20260511`

---

## Sommario Esecutivo

Risoluzione completa dei pytest warning persistenti nella suite di test del
motore `spark-framework-engine`. Risultato finale: **544 passed, 1 skipped,
0 warnings, EXIT=0** su `pytest -q --ignore=tests/test_integration_live.py`.

---

## Problema Originale

### Warning 1 — PytestConfigWarning: Unknown config option: asyncio_mode

```
C:\Users\...\Envs\audiomaker311\Lib\site-packages\_pytest\config\__init__.py:1439:
PytestConfigWarning: Unknown config option: asyncio_mode
```

**Origine:** configurazione globale / utente (`asyncio_mode = "auto"`) in un
file pytest al di fuori del repository (es. `~/.config/pytest.ini` o
`pyproject.toml` globale). Il file locale `pyproject.toml` non conteneva più
questa chiave (rimossa in sessione precedente), ma la warning persisteva perché
pytest leggeva ancora la config globale come fallback.

### Warning 2 — PytestUnhandledCoroutineWarning (×19)

```
C:\Users\...\Envs\audiomaker311\Lib\site-packages\_pytest\python.py:184:
PytestUnhandledCoroutineWarning: async def functions are not natively supported...
```

**Origine:** test `async def` in `test_bootstrap_workspace_extended.py` (10
occorrenze) e `test_legacy_init_audit.py` (9 occorrenze) rilevati da pytest
prima che il hook `pytest_pyfunc_call` in `conftest.py` potesse intercettarli.

### Error — FileNotFoundError (collection error)

```
ERROR tests/test_spark_init.py - FileNotFoundError: spark-init.py
```

**Origine:** `test_spark_init.py` importava `spark-init.py` che era stato
eliminato nel commit `392af92` ("rimosso setup.ps1 e spark-init.py per
semplificare la configurazione del progetto"). Il test era rimasto orfano.

---

## Analisi Root Cause

| Warning | Fonte | Tipo |
|---------|-------|------|
| `asyncio_mode` | Config globale utente (fuori repo) | PytestConfigWarning |
| Coroutine unhandled ×19 | `_pytest/python.py` a collection-time | PytestUnhandledCoroutineWarning |
| FileNotFoundError | `test_spark_init.py` (target file eliminato) | Collection error |

---

## Soluzione Implementata

### Passo 1 — Creazione `pytest.ini` a radice del repository

File `pytest.ini` creato con contenuto minimo:

```ini
[pytest]
testpaths = tests
```

**Effetto:** pytest usa `pytest.ini` come configfile prioritario (precede
`pyproject.toml`), ignorando le configurazioni globali del sistema. Questo ha
eliminato sia `PytestConfigWarning: asyncio_mode` sia i
`PytestUnhandledCoroutineWarning` (il hook `pytest_pyfunc_call` in
`conftest.py` era già funzionante, ma richiedeva il configfile locale corretto
per essere caricato prima della fase di collection warning).

### Passo 2 — Rimozione `tests/test_spark_init.py`

File `test_spark_init.py` eliminato. Il file testava esclusivamente la funzione
di bootstrap di `spark-init.py`, rimosso definitivamente nel commit `392af92`.
Non c'è codice residuo da testare — il test era dead code.

---

## Verifica Finale

```
pytest -q --ignore=tests/test_integration_live.py
```

Risultato post-fix:

```
544 passed, 1 skipped in 8.42s
EXIT=0
```

**0 warnings. 0 errori di collection. Suite stabile.**

---

## File Modificati

| File | Operazione |
|------|-----------|
| `pytest.ini` | Creato (config locale prioritaria) |
| `tests/test_spark_init.py` | Eliminato (dead test) |
| `CHANGELOG.md` | Aggiornato sezione `[Unreleased]` |

---

## Note Tecniche

- Il file `conftest.py` utilizza `@pytest.hookimpl(tryfirst=True)` su
  `pytest_pyfunc_call` per eseguire `async def test_*` via `asyncio.run()`
  senza dipendere da `pytest-asyncio`. Questo meccanismo è corretto e non
  richiede modifiche.
- La dipendenza `pytest-asyncio>=0.23` rimane in `pyproject.toml`
  `[project.optional-dependencies]` per compatibilità futura, ma NON viene
  usata attivamente nella suite corrente.
- Il `1 skipped` è un test parametrizzato saltato per condizione di ambiente,
  non un warning.
