# SPARK-DOC-SYNC-REPORT — 2026-05-06

**Tipo:** Audit documentale post-implementazione  
**Data:** 2026-05-06  
**Agente:** spark-engine-maintainer  
**Baseline test:** 313 passed / 9 skipped / 0 failed  
**ENGINE_VERSION:** 3.1.0 (`spark/core/constants.py`)  
**Commit head:** `0c9d7ec` — `perf(install): optimize v3 package installation` (già su `origin/main`)

---

## Sommario discrepanze identificate

| # | Area | Discrepanza | Azione |
|---|------|-------------|--------|
| D1 | `CHANGELOG.md` | OPT-1/8 non presenti in `[Unreleased]` | CORRETTO ✅ |
| D2 | `docs/todo.md` | Sezione OPT mancante, data obsoleta | CORRETTO ✅ |
| D3 | GitHub Releases | Nessuna release pubblicata per nessuna versione | PENDENTE ⏳ |
| D4 | `ENGINE_VERSION` | v3.1.0 — `[Unreleased]` contiene lavoro sufficiente per v3.2.0 | SEGNALATO ℹ️ |

---

## FASE 1 — Audit `docs/todo.md`

### Stato file pre-audit

- Tutte le fasi (0-5, 4-BIS, Refactoring Fase 1 e 2) erano già marcate `COMPLETATA`.
- Data "Ultimo aggiornamento": 2026-05-05.
- Nessun `[ ]` aperto tranne **P6** (promozione closure a attributi di istanza),
  esplicitamente marcato "IN ATTESA DI CONFERMA DA LUCA" — nessuna azione richiesta.

### Modifiche applicate

- Header `Sessione attiva` → "Ottimizzazioni Prestazionali v3 — COMPLETATA"
- Header `Ultimo aggiornamento` → 2026-05-06
- Header `Stato piano` → aggiunto "Ottimizzazioni Prestazionali v3 COMPLETATA"
- Aggiunta nuova sezione dopo "Refactoring Fase 2":

  ```
  ### Ottimizzazioni Prestazionali v3 — 8 OPT (COMPLETATA 2026-05-06)
  ```

  Con dettaglio dei 8 OPT (commit `0c9d7ec`), file toccati e validazione.

### Gate FASE 1: PASS ✅

---

## FASE 2 — Aggiornamento `CHANGELOG.md`

### Stato file pre-audit

- Sezione `[Unreleased]` attiva con voci per: bootstrap v3.1 params, WorkspaceWriteGateway,
  Fase 4-BIS, locator, auto-bootstrap hook.
- **Assente:** qualsiasi menzione di OPT-1/8 (commit `0c9d7ec`).
- Ultima versione taggata documentata: `[3.1.0] - 2026-04-28`.

### Modifiche applicate

Aggiunta nuova sottosezione `### Performance (OPT-1 — OPT-8)` all'interno di `[Unreleased]`,
tra la sezione `### Changed` e `### Fixed`, con voce per ognuno degli 8 OPT.

Estratto:
```
- **OPT-1** ManifestManager.load() — cache mtime-validata ...
- **OPT-3** _install_package_v3_into_store — ThreadPoolExecutor(max_workers=8) ...
- **OPT-8** _apply_phase6_assets — flush unica via gateway.write_many() ...
```

### Note versione

Il contenuto `[Unreleased]` copre lavoro sufficiente per un bump **MINOR → v3.2.0**:
`WorkspaceWriteGateway`, auto-bootstrap hook, 8 OPT. La promozione richiede:
1. Bump `ENGINE_VERSION` in `spark/core/constants.py` da `"3.1.0"` a `"3.2.0"`.
2. Spostare il blocco `[Unreleased]` → `## [3.2.0] - 2026-05-06`.
3. Creare tag git `v3.2.0` e GitHub Release.

Azione non eseguita in questo audit (modifica `.py` fuori perimetro). Da pianificare
come prossimo task di release.

### Gate FASE 2: PASS ✅

---

## FASE 3 — GitHub Release v3.1.0

### Stato pre-audit

- Tag git locale e remoto `v3.1.0` presente.
- Nessuna GitHub Release pubblicata su `Nemex81/spark-framework-engine` per nessun tag.

### Azione richiesta — PENDENTE ⏳

Non è stato possibile creare la release in autonomia:
- `gh` CLI non installato sul sistema.
- Nessun `GITHUB_TOKEN` in ambiente.
- Nessun tool MCP `create_release` disponibile.

**Azione manuale richiesta:** Crea la GitHub Release per `v3.1.0` all'indirizzo:

```
https://github.com/Nemex81/spark-framework-engine/releases/new?tag=v3.1.0
```

Usa le note seguenti come corpo della release (già presenti in `CHANGELOG.md § [3.1.0]`):

---

**Titolo suggerito:** `v3.1.0 — v3-aware Package Lifecycle (Fase 9)`

**Note release:**

```markdown
## Added

- **v3-aware package lifecycle (Fase 9).** I tool `scf_install_package`,
  `scf_update_package` e `scf_remove_package` ora rilevano i pacchetti
  v3 (con `min_engine_version >= 3.0.0`) e li installano nel store
  centralizzato `engine_dir/packages/{pkg_id}/.github/` invece che in
  `workspace/.github/`. La install registra una entry sentinella
  `installation_mode: "v3_store"` nel manifest workspace e popola
  `McpResourceRegistry` live; remove deregistra le URI e cancella lo
  store ma preserva sempre gli override workspace; update riusa la
  install idempotente e segnala via `override_blocked` quali risorse
  hanno un override workspace attivo.
- Nuovi helper interni: `_is_v3_package()`, `_install_package_v3_into_store()`,
  `_remove_package_v3_from_store()`, `_list_orphan_overrides_for_package()`,
  `_v3_overrides_blocking_update()`, `McpResourceRegistry.unregister()` e
  `McpResourceRegistry.unregister_package()`.
- Nuova suite test `tests/test_package_lifecycle_v3.py` (10 test) che
  copre install/update/remove v3 + retrocompat v2.

## Changed

- `ManifestManager.verify_integrity()` e `ManifestManager.remove_package()`
  ora ignorano le entry sentinella v3 (`installation_mode == "v3_store"`),
  evitando lookup falliti su path workspace.
- I pacchetti legacy con `min_engine_version < 3.0.0` continuano a usare
  il flusso v2 (copia file in workspace) con un warning su stderr.
```

---

### Gate FASE 3: PENDENTE ⏳ (azione manuale richiesta)

---

## FASE 4 — Analisi stdout in `_ensure_bootstrap`

### Scope analisi

- `spark/boot/onboarding.py` — `OnboardingManager._ensure_bootstrap()`
- `spark/boot/sequence.py` — chiamante di `OnboardingManager`
- `spark-framework-engine.py` — entry point
- Tutti i file `spark/**/*.py`

### Risultati

| Check | Risultato |
|-------|-----------|
| `print()` in `spark/**/*.py` | 0 occorrenze 🟢 |
| `print()` in `spark-framework-engine.py` | 0 occorrenze 🟢 |
| `print()` in `spark-init.py` | 0 occorrenze 🟢 |
| `sys.stdout.write` in `spark/**/*.py` | 0 occorrenze 🟢 |
| `StreamHandler` su stdout in `spark/**/*.py` | 0 occorrenze 🟢 |

**Analisi `_ensure_bootstrap`:** Usa esclusivamente `_log.info()` e `_log.warning()`
sul logger `spark-framework-engine`. Il logger usa `stderr` come handler di default
(configurato in `spark/boot/sequence.py` via `logging.basicConfig(stream=sys.stderr)`
o equivalente). Nessun canale stdout contaminato.

### Classificazione rischio: 🟢 CLEAN

Nessuna azione correttiva richiesta.

### Gate FASE 4: PASS ✅

---

## Prossime azioni raccomandate

| Priorità | Azione | File |
|----------|--------|------|
| ALTA | Creare GitHub Release v3.1.0 (manuale) | GitHub web UI |
| MEDIA | Bump ENGINE_VERSION → 3.2.0 e promuovere `[Unreleased]` → `[3.2.0]` | `spark/core/constants.py`, `CHANGELOG.md` |
| BASSA | Decidere P6 (promozione closure → attributi di istanza) | `spark/boot/engine.py` |

---

## Gate finale audit

| Fase | Stato |
|------|-------|
| FASE 1 — docs/todo.md | ✅ PASS |
| FASE 2 — CHANGELOG.md | ✅ PASS |
| FASE 3 — GitHub Release | ⏳ PENDENTE (manuale) |
| FASE 4 — stdout safety | ✅ PASS |

**Audit COMPLETATO** — 3/4 fasi chiuse automaticamente. 1 azione manuale pendente.
