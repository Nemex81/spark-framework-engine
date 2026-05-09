# SPARK Report — GAP-Y-2 Frontmatter-Only Update v1.0

**Audit ID:** spark-gap-y2-frontmatter-only-v1.0  
**Data:** 2026-05-XX  
**Autore:** spark-engine-maintainer  
**Status:** CHIUSO — RISOLTO  
**File principali:** `spark/boot/tools_bootstrap.py`, `tests/test_legacy_init_audit.py`

---

## Sommario Esecutivo

GAP-Y-2 era classificato come BLOCCO-ARCHITETTURALE nella sessione precedente
(audit `spark-init-legacy-audit-v1.0`). Nemex81 ha autorizzato esplicitamente
la strategia **frontmatter-only update**. Questa sessione implementa la strategia,
la valida con 7 nuovi test e chiude il blocco.

**Risultato:** `force=True` su file SPARK obsoleto aggiorna solo il blocco
frontmatter YAML, preservando il body utente invariato. I file non-SPARK
continuano a ricevere sovrascrittura completa (comportamento invariato).

---

## Problema Risolto

### Scenario di rischio

1. Utente installa workspace SPARK per la prima volta → bootstrap scrive
   `workflow-standard.instructions.md` con frontmatter engine + body standard.
2. Utente personalizza il body aggiungendo sezioni proprie.
3. Motore rileva nuova versione del file (`spark_outdated`).
4. Utente esegue `force=True` per aggiornare.
5. **Prima del fix:** l'intero file viene sovrascritto → personalizzazioni perse.
6. **Dopo il fix:** solo il frontmatter viene aggiornato → personalizzazioni intatte.

### Perché il problema esisteva

Il ramo `force=True` nel loop bootstrap di `scf_bootstrap_workspace` non distingueva
tra file SPARK obsoleti e file non-SPARK. Per entrambi cadeva nel write block con
`_gateway_write_bytes(source_path.read_bytes(), ...)`, sovrascrivendo tutto.

---

## Strategia Implementata

**Frontmatter-only update**: il file risultante è la concatenazione di:
- Blocco frontmatter verbatim dal file sorgente engine (`packages/spark-base/...`)
- Body verbatim dal file utente esistente nel workspace

### Formula di ricostruzione

```python
# Estrazione raw (senza parse/serialize YAML)
source_parts = source_content.split("---", 2)
source_fm_block = source_parts[1]   # testo tra primo e secondo ---

dest_parts = dest_content.split("---", 2)
user_body = dest_parts[2]           # tutto dopo il secondo ---

merged = "---" + source_fm_block + "---" + user_body
```

### Perché raw string e non yaml.dump

- Nessuna dipendenza nuova (PyYAML non richiesto)
- Preserva l'ordine esatto dei campi frontmatter
- Preserva lo stile di quoting esatto
- Nessun rischio di incompatibilità di formato

### Edge cases gestiti

| Caso | Comportamento |
|------|--------------|
| Source senza frontmatter `---` | `_apply_frontmatter_only_update()` → `None` → fallback a `files_protected` |
| Source con frontmatter non chiuso | `_apply_frontmatter_only_update()` → `None` → fallback |
| Dest senza body (solo frontmatter) | `user_body = ""` → merged = `---fm---` → valido |
| Dest senza frontmatter | Impossibile: `_classify_bootstrap_conflict()` ritorna `"non_spark"` → full overwrite |
| File non-SPARK con `force=True` | Comportamento invariato: sovrascrittura completa |
| Workspace vergine | `files_updated_frontmatter_only = []` (nessun file preesistente) |

---

## Struttura Implementativa

### Funzione helper `_apply_frontmatter_only_update()`

```
Posizione: spark/boot/tools_bootstrap.py (modulo-level, dopo _classify_bootstrap_conflict)
Firma: (source_path: Path, dest_path: Path) -> str | None
Ritorno: merged content string | None su failure
Effetti collaterali: zero (non scrive file, solo logging)
```

### Modifiche al loop bootstrap

**Ramo `force=True` (prima del write block):**
```
Se dest esiste + SHA diverso + force=True:
  → _classify_bootstrap_conflict(dest_path)
    Se "spark_outdated":
      → _apply_frontmatter_only_update(source, dest)
        Successo → scrive dest, aggiunge a files_updated_frontmatter_only + files_written + files_copied
        Failure  → fallback: aggiunge a files_conflict_non_spark + files_protected
      → continue (non cade nel write block)
    Se "non_spark":
      → comportamento invariato (cade nel write block con _gateway_write_bytes)
```

### Nuovo campo payload

| Campo | Tipo | Descrizione |
|-------|------|-------------|
| `files_updated_frontmatter_only` | `list[str]` | File SPARK obsoleti aggiornati frontmatter-only |

Backfillato con `setdefault([])` in `_finalize_bootstrap_result()` per tutti i return path.

---

## Verifica Test

### Test aggiunti (7 nuovi in `tests/test_legacy_init_audit.py`)

| # | Test | Tipo | Gate |
|---|------|------|------|
| 1 | `test_force_true_updates_frontmatter_only_for_spark_outdated` | Integrazione | PASS |
| 2 | `test_force_true_preserves_user_body_when_spark_outdated` | Integrazione | PASS |
| 3 | `test_force_true_non_spark_file_still_gets_full_overwrite` | Integrazione | PASS |
| 4 | `test_force_true_spark_outdated_payload_on_clean_workspace` | Integrazione | PASS |
| 5 | `test_apply_frontmatter_only_unit_builds_merged_content` | Unit | PASS |
| 6 | `test_apply_frontmatter_only_unit_returns_none_on_malformed_source` | Unit | PASS |
| 7 | `test_apply_frontmatter_only_unit_handles_empty_user_body` | Unit | PASS |

### Test preesistenti verificati non impattati

| Test | Motivo invarianza |
|------|------------------|
| `test_bootstrap_force_overwrites_user_modified_non_sentinel_file` | Usa file non-SPARK → full overwrite invariato |
| `test_bootstrap_force_overwrites_user_modified_sentinel` | Riguarda sentinel gate (pre-loop) → non impattato |
| Tutti i 5 test GAP-X-1/Y-1 | Usano `force=False` → ramo non toccato |

### Suite completa

```
Comando: C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_integration_live.py --tb=short
Baseline (pre-sessione):  539 passed / 9 skipped / 0 failed
Post-fix GAP-Y-2:         546 passed / 9 skipped / 0 failed
Delta: +7 nuovi test, 0 regressioni
```

---

## File Modificati

| File | Tipo modifica | Righe impattate (approx) |
|------|---------------|--------------------------|
| `spark/boot/tools_bootstrap.py` | Aggiunta funzione + modifica loop + 4 dict | +60 righe, 6 punti |
| `tests/test_legacy_init_audit.py` | Aggiunta import + 7 test | +185 righe |
| `CHANGELOG.md` | Aggiunta sezione `### Added — GAP-Y-2` | +32 righe |
| `docs/reports/SPARK-REPORT-LegacyInitAudit-v1.0.md` | Aggiornamento sezioni GAP-Y-2 | ~30 righe |

---

## Invarianti Rispettati

- ✅ Nessuna modifica a `spark-framework-engine.py`
- ✅ Nessuna modifica alle firme dei tool MCP
- ✅ Nessuna dipendenza Python nuova (no PyYAML)
- ✅ Zero output su `stdout` (solo `sys.stderr` via `_log`)
- ✅ Docstring Google Style su `_apply_frontmatter_only_update()`
- ✅ `framework_edit_mode` non richiesto (nessuna modifica a `.github/`)
- ✅ Suite completa PASS (546/9)

---

## Post-Step Analysis

```
OPERAZIONE COMPLETATA: GAP-Y-2 frontmatter-only update
GATE: PASS
CONFIDENCE: 0.97
FILE TOCCATI: spark/boot/tools_bootstrap.py, tests/test_legacy_init_audit.py,
              CHANGELOG.md, docs/reports/SPARK-REPORT-LegacyInitAudit-v1.0.md,
              docs/reports/SPARK-REPORT-FrontmatterOnlyUpdate-v1.0.md (creato)
OUTPUT CHIAVE: 546 passed / 9 skipped / 0 failed (+7 nuovi test, 0 regressioni)
PROSSIMA AZIONE: commit proposto (Agent-Git)
```

---

## Comandi Proposti per Commit

```bash
# Comandi da eseguire manualmente (o tramite Agent-Git):
git add spark/boot/tools_bootstrap.py
git add tests/test_legacy_init_audit.py
git add CHANGELOG.md
git add docs/reports/SPARK-REPORT-LegacyInitAudit-v1.0.md
git add docs/reports/SPARK-REPORT-FrontmatterOnlyUpdate-v1.0.md
git commit -m "fix(bootstrap): frontmatter-only update for SPARK outdated files with force=True (GAP-Y-2)

- Adds _apply_frontmatter_only_update() helper that merges engine frontmatter
  with user body using raw string split (no yaml.dump, no new dependencies)
- bootstrap loop now classifies spark_outdated files before force-overwriting
  and routes them to frontmatter-only update path
- New payload field files_updated_frontmatter_only (backfilled in finalize)
- Non-SPARK files and clean workspace behavior unchanged
- 7 new tests: 4 integration + 3 unit (546 passed / 9 skipped)
- Closes GAP-Y-2 BLOCCO-ARCHITETTURALE from legacy-init-audit-v1.0"
```
