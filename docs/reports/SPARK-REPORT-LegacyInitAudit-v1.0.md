---
spark: true
report_type: "audit-and-fix"
version: "1.0.0"
date: "2025-07-23"
status: "COMPLETED"
gate: "PASS"
audit_id: "spark-init-legacy-audit-v1.0"
---

# SPARK-REPORT-LegacyInitAudit-v1.0

## Identificazione

| Campo | Valore |
|-------|--------|
| Report ID | `SPARK-REPORT-LegacyInitAudit-v1.0` |
| Tipo | Audit di Inizializzazione + Fix Chirurgico |
| Engine version | `3.3.0` |
| Branch | `feature/dual-mode-manifest-v3.1` |
| Data | 2025-07-23 |
| Gate | PASS |
| Baseline test (pre-fix) | 534 passed / 9 skipped / 0 failed |
| Baseline test (post-fix) | 539 passed / 9 skipped / 0 failed |

---

## Obiettivo dell'Audit

Verificare il comportamento del sistema SPARK (`scf_bootstrap_workspace`) quando il
workspace dell'utente contiene già file preesistenti con lo stesso nome di un file
bootstrap SPARK, in due scenari distinti:

- **Scenario X**: file non-SPARK (senza frontmatter `spark: true`) con nome identico
  a un file bootstrap → il sistema NON deve sovrascrivere silenziosamente.
- **Scenario Y**: file SPARK con versione obsoleta/deprecata → il sistema deve
  identificarlo come tale e fornire informazioni per un aggiornamento sicuro.

**Vincolo principale:** "Non si scrive nulla prima di aver letto e compreso
integralmente il sistema coinvolto."

---

## Sessione Precedente: DocComplete-v1.0 (2025-07-22)

La sessione precedente a questo audit ha prodotto la documentazione tecnica
completa per il motore `spark-framework-engine` versione `3.3.0`, verificando
ogni affermazione nel codice reale prima della scrittura.

### File prodotti nella sessione precedente

| File | Tipo | Contenuto |
|------|------|-----------|
| `docs/architecture.md` | Documentazione tecnica | 9 sezioni: panoramica, componenti, dual-universe, bootstrap 11-step, flusso installazione, onboarding, invarianti, struttura directory, costanti |
| `docs/api.md` | Documentazione API | 51 tool MCP documentati (49 attivi + 2 deprecated), parametri, campi risposta, note deprecazione |
| `docs/testing.md` | Guida testing | Struttura suite test (62 file, 534 test), pattern fixture, run commands, test di regressione |
| `docs/contributing.md` | Guida contribuzione | 4 tipi di contribuzione, checklist pre-commit, politica git, processo review |
| `docs/troubleshooting.md` | Guida troubleshooting | 6 categorie problemi, diagnosi, soluzioni verificate nel codice |
| `docs/security.md` | Documentazione sicurezza | 5 livelli di controllo, OWASP alignment, gateway SHA256, preservation gate |
| `docs/performance.md` | Documentazione performance | 8 ottimizzazioni implementate (OPT-1→OPT-8), benchmark, mtime cache |
| `docs/glossary.md` | Glossario tecnico | 34 termini del dominio SPARK con definizioni precise |
| `docs/faq.md` | FAQ | 20 domande frequenti categorizzate |

### Impatto sessione precedente

- Nessuna modifica al codice sorgente
- Suite test invariata: 534 passed / 9 skipped
- Documentazione era completamente assente prima della sessione

---

## Sessione Corrente: LegacyInitAudit-v1.0 (2025-07-23)

### Fase 1 — Lettura integrale del sistema (COMPLETATA)

Sono stati letti e analizzati i seguenti file sorgente prima di qualsiasi modifica:

| File | Scopo della lettura |
|------|---------------------|
| `spark/boot/tools_bootstrap.py` | Ciclo bootstrap, preservation gate, return paths |
| `spark/boot/engine.py` | `ensure_minimal_bootstrap()`, sentinel gate, 5 required paths |
| `spark/boot/lifecycle.py` | `_install_workspace_files_v3()` (ora stub → PluginInstaller) |
| `spark/plugins/installer.py` | Preservation gate in `install_from_store()` |
| `spark/manifest/manifest.py` | `verify_integrity()` con classificazione SPARK/non-SPARK via frontmatter |
| `spark/core/utils.py` | `parse_markdown_frontmatter()` — disponibile, nessuna dipendenza aggiuntiva |
| `tests/test_bootstrap_workspace_extended.py` | Test esistenti, pattern fixture, coverage attuale |

### Scheda di Stato Scenari (post-lettura)

```
SCENARIO X — File non-SPARK con nome identico
Preservation gate esiste:    SÌ (SHA mismatch → files_protected)
Gate attivato:               SÌ per ogni file nel bootstrap loop
Segnalazione utente:         MCP payload (files_protected list)
Test esistenti:              SÌ (test_bootstrap_returns_files_protected_for_non_sentinel_user_modified)
                             — ma testa solo la protezione, non la classificazione tipo conflitto
Stato:                       GAP PARZIALE — protezione attiva; manca classificazione nel payload

SCENARIO Y — File SPARK versione obsoleta
Rilevamento frontmatter:     ASSENTE nel bootstrap loop
                             (presente in verify_integrity() ma non nel bootstrap)
Confronto versione:          ASSENTE
Strategia update:            sovrascrittura brutale con force=True (no distinzione SPARK/non-SPARK)
Personalizzazioni preservate: N/D (force=True sovrascrive tutto)
Test esistenti:              NESSUNO
Stato:                       GAP PARZIALE — file protetto ma classificazione/versione assenti nel payload
```

### Fase 2-3 — Analisi Gap e Convalida Strategia (COMPLETATA)

#### Gap identificati

**GAP-X-1: Classificazione file protetti assente nel payload**
- Descrizione: `files_protected` contiene tutti i file preservati senza
  distinguere tra file non-SPARK (user file) e file SPARK obsoleti.
- Impatto: INFO — la protezione funziona correttamente, ma l'utente non sa
  se può usare `force=True` in sicurezza o se rischia di sovrascrivere
  un file che conosce.
- Complessità fix: BASSA (<20 righe)
- Dipende da: nessun altro gap

**GAP-Y-1: Rilevamento frontmatter SPARK nel bootstrap loop assente**
- Descrizione: Il bootstrap non legge il frontmatter YAML dei file protetti
  né confronta la versione dichiarata con quella del file engine.
- Impatto: DEGRADED — l'utente con un file SPARK obsoleto (`spark: true`,
  versione X.Y.Z) non ha informazioni per decidere se aggiornare.
- Complessità fix: BASSA per rilevamento; MEDIA per versione delta
- Dipende da: stesso loop di classificazione di GAP-X-1

**GAP-Y-2: Preservazione personalizzazioni durante update SPARK**
- Descrizione: `force=True` sovrascrive l'intero file SPARK obsoleto,
  comprese le sezioni personalizzate dall'utente che non fanno parte
  del template engine.
- Impatto: BLOCCANTE (potenziale perdita irreversibile di personalizzazioni)
- Complessità fix: ALTA (richiede formato per sezioni "managed")
- → **BLOCCO-ARCHITETTURALE**: non implementato (vedi sezione dedicata)

#### Convalida strategia implementata

```
CONVALIDA — GAP-X-1 + GAP-Y-1 (trattati insieme)
Strategia: _classify_bootstrap_conflict(dest_path) → str
           + files_conflict_non_spark + files_conflict_spark_outdated
           + spark_outdated_details nel payload
Tipo modifica: CHIRURGICA (~30 righe, solo in tools_bootstrap.py)
Impatto su caso nominale: NESSUNO — workspace vergine → lists vuote (setdefault)
Dipendenze nuove: NESSUNA — parse_markdown_frontmatter già in spark.core.utils
Breaking change: NO — nuovi campi aggiuntivi nel payload, firme invariate
Esito convalida: PASS
```

### Fase 4 — Implementazione (Test First + Fix) (COMPLETATA)

#### Test scritti prima del fix (TDD)

File: `tests/test_legacy_init_audit.py` (5 test, scritti prima del fix)

| Test | Scenario | Asserzione chiave |
|------|----------|-------------------|
| `test_bootstrap_classifies_non_spark_conflict_file` | X | file senza frontmatter → `files_conflict_non_spark` |
| `test_bootstrap_non_spark_conflict_payload_is_empty_on_clean_workspace` | baseline | workspace vergine → liste vuote |
| `test_bootstrap_classifies_spark_outdated_conflict_file` | Y | file con `spark: true` → `files_conflict_spark_outdated` |
| `test_bootstrap_spark_outdated_includes_version_details` | Y | versione dal frontmatter in `spark_outdated_details` |
| `test_bootstrap_non_md_file_classified_as_non_spark` | X (edge) | file `.json` preesistente → `non_spark` (no frontmatter) |

**Verifica test first:** tutti e 5 i test fallivano prima del fix con
`KeyError`/`AssertionError` su `files_conflict_non_spark` assente nel payload.

#### Fix implementato

**File modificato:** `spark/boot/tools_bootstrap.py`

**Modifiche applicate (4 punti):**

1. **Import aggiunto** (riga 30):
   ```python
   # Prima:
   from spark.core.utils import _utc_now
   # Dopo:
   from spark.core.utils import _utc_now, parse_markdown_frontmatter
   ```

2. **Helper function aggiunta** (modulo-level, prima di `register_bootstrap_tools`):
   ```python
   def _classify_bootstrap_conflict(dest_path: Path) -> str:
       """Classifica il tipo di conflitto per un file preesistente nel workspace.
       ...
       Returns: "spark_outdated" | "non_spark"
       """
       if dest_path.suffix != ".md":
           return "non_spark"
       try:
           content = dest_path.read_text(encoding="utf-8", errors="replace")
           fm = parse_markdown_frontmatter(content)
           if bool(fm.get("spark", False)):
               return "spark_outdated"
       except OSError:
           pass
       return "non_spark"
   ```

3. **Inizializzazione nuove liste** (in `scf_bootstrap_workspace`):
   ```python
   files_conflict_non_spark: list[str] = []
   files_conflict_spark_outdated: list[str] = []
   spark_outdated_details: list[dict[str, Any]] = []
   ```

4. **Classificazione nella branch di protezione** (sostituisce il semplice `_log.warning`):
   ```python
   if not force:
       conflict_type = _classify_bootstrap_conflict(dest_path)
       if conflict_type == "spark_outdated":
           # Legge versione dal frontmatter del file esistente
           existing_version = str(fm.get("version", "unknown"))
           files_conflict_spark_outdated.append(rel_path)
           spark_outdated_details.append(
               {"file": rel_path, "existing_version": existing_version}
           )
           _log.warning("Bootstrap file preserved (spark_outdated v%s): %s", ...)
       else:
           files_conflict_non_spark.append(rel_path)
           _log.warning("Bootstrap file preserved (non_spark conflict): %s", ...)
       preserved.append(rel_path)
       files_protected.append(rel_path)
       continue
   ```

5. **setdefault in `_finalize_bootstrap_result`** (garantisce i campi su tutti i return path):
   ```python
   result.setdefault("files_conflict_non_spark", [])
   result.setdefault("files_conflict_spark_outdated", [])
   result.setdefault("spark_outdated_details", [])
   ```

6. **Return path principale aggiornato** (include i nuovi campi nel dict).
7. **Return path error (OSError)** aggiornato (include i nuovi campi nel dict).

#### Comportamento nuovo del payload MCP

Esempio payload per utente con file non-SPARK preesistente:
```json
{
  "success": true,
  "status": "bootstrapped",
  "files_written": ["...altri file..."],
  "files_protected": [".github/copilot-instructions.md"],
  "files_conflict_non_spark": [".github/copilot-instructions.md"],
  "files_conflict_spark_outdated": [],
  "spark_outdated_details": []
}
```

Esempio payload per utente con file SPARK obsoleto preesistente:
```json
{
  "success": true,
  "status": "bootstrapped",
  "files_written": ["...altri file..."],
  "files_protected": [".github/instructions/workflow-standard.instructions.md"],
  "files_conflict_non_spark": [],
  "files_conflict_spark_outdated": [".github/instructions/workflow-standard.instructions.md"],
  "spark_outdated_details": [
    {
      "file": ".github/instructions/workflow-standard.instructions.md",
      "existing_version": "0.1.0"
    }
  ]
}
```

### Fase 5 — Documentazione e CHANGELOG (COMPLETATA)

**CHANGELOG.md** — aggiunta sezione `### Added — Legacy Init Audit v1.0` in `[Unreleased]`
con descrizione completa di:
- `_classify_bootstrap_conflict()` helper
- 3 nuovi campi payload: `files_conflict_non_spark`, `files_conflict_spark_outdated`, `spark_outdated_details`
- `tests/test_legacy_init_audit.py` (5 nuovi test)
- Nota `### Planned` con GAP-Y-2 (BLOCCO-ARCHITETTURALE).

### Fase 6 — Verifica Suite Finale (COMPLETATA)

```
Baseline pre-fix:  534 passed / 9 skipped / 0 failed
Post-fix (5 nuovi test):  539 passed / 9 skipped / 0 failed
Delta: +5 nuovi test, 0 regressioni
```

Comando di verifica:
```
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_integration_live.py --tb=short
```

---

## BLOCCO-ARCHITETTURALE: GAP-Y-2

### Descrizione

Quando un file SPARK obsoleto viene aggiornato con `force=True`, l'intero
file viene sovrascritto con la versione engine. Qualsiasi personalizzazione
dell'utente nelle sezioni non-gestite dal framework viene persa irreversibilmente.

### Scenario di rischio

L'utente ha personalizzato `copilot-instructions.md` aggiungendo sezioni
proprie al di fuori del blocco `SCF:BEGIN`/`SCF:END`. Con `force=True`,
il file viene riscritto da zero, le sezioni personalizzate spariscono.

### Analisi opzioni

| Opzione | Pro | Contro |
|---------|-----|--------|
| A — Marker `<!-- SPARK-MANAGED -->` | Semplice, leggibile | Richiede tutti i file SPARK aggiornati |
| B — `merge_sections` marker (già usato in `copilot-instructions.md`) | Pattern già esistente | Applicabile solo ai file con sezioni strutturate |
| C — Frontmatter-only update | Minimale, non tocca il corpo | Risolve solo il caso in cui la differenza è nel frontmatter |
| D — Diff + patch interattivo | Massima preservazione | Complessità molto alta, richiede UI aggiuntiva |

### Condizione per implementazione

Non implementare GAP-Y-2 senza decisione architetturale esplicita da Nemex81
su quale opzione adottare e su quali file applicarla.

---

## Riepilogo Impatto nel Sistema

### File modificati in questa sessione

| File | Tipo modifica | Impatto |
|------|---------------|---------|
| `spark/boot/tools_bootstrap.py` | Fix chirurgico | Payload arricchito, behavior invariato |
| `tests/test_legacy_init_audit.py` | Nuovo file | 5 test TDD (Scenario X + Y) |
| `CHANGELOG.md` | Documentazione | Voce [Unreleased] + nota GAP-Y-2 |

### Invarianti rispettati

- ✅ Zero modifiche alle firme dei tool MCP
- ✅ Nessuna modifica a `.github/` (framework_edit_mode non richiesto)
- ✅ Nessuna dipendenza Python nuova (solo `parse_markdown_frontmatter` da `spark.core.utils`)
- ✅ Zero output su `stdout` — solo `sys.stderr`
- ✅ Docstring Google Style sulla funzione helper
- ✅ SemVer: fix minore non breaking (nessun bump ENGINE_VERSION)
- ✅ Test scritti PRIMA del fix (TDD)
- ✅ Suite completa PASS post-fix (539/9)

### Impatto utenti

| Utente | Prima del fix | Dopo il fix |
|--------|---------------|-------------|
| Workspace vergine | `files_protected: []` | `files_protected: []`, `files_conflict_*: []` |
| File non-SPARK preesistente | `files_protected: [file]` — nessuna classificazione | + `files_conflict_non_spark: [file]` |
| File SPARK obsoleto preesistente | `files_protected: [file]` — nessuna classificazione | + `files_conflict_spark_outdated: [file]` + `spark_outdated_details` con versione |

---

## Conclusione

L'audit `spark-init-legacy-audit-v1.0` ha verificato il sistema di protezione
dei file preesistenti durante il bootstrap SPARK, identificato 3 gap (X-1, Y-1,
Y-2), implementato fix chirurgico per X-1 + Y-1 con 5 nuovi test TDD, e
documentato il blocco architetturale Y-2 per futura decisione.

Il sistema ora comunica all'utente il tipo di conflitto rilevato durante il
bootstrap, permettendo una scelta informata sull'uso di `force=True`.

---

*Generato da `spark-engine-maintainer` · spark-framework-engine v3.3.0*
