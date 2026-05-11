# SPARK-REPORT — Dual Universe Package Resolution v2.0

**Branch:** `workspace-slim-registry-sync-20260511`
**Data esecuzione:** 2026-05-11
**Prompt origine:** `spark-dual-universe-architect`
**Agente:** `@spark-engine-maintainer`
**Stato:** COMPLETATO ✓

---

## 1. Obiettivo

Implementare routing `delivery_mode`-based in `tools_bootstrap.py`:

- **Universo A** (`mcp_only`): risoluzione da `packages/` locali nel repo engine (zero HTTP).
- **Universo B** (fallback): risoluzione da registry remoto HTTPS (`scf-registry`).

Output atteso: `{success:true, strategy:"A-local/B-remote", tests_added:4}`.

---

## 2. Gap Analysis (pre-implementazione)

| Package | delivery_mode prima | delivery_mode dopo | Universe |
|---------|--------------------|--------------------|---------|
| `spark-base` | ❌ assente | ✅ `"mcp_only"` | A |
| `spark-ops` | ✅ `"mcp_only"` | invariato | A |
| `scf-master-codecrafter` | ✅ `"mcp_only"` | invariato | A |
| `scf-pycode-crafter` | ✅ `"mcp_only"` | invariato | A |

**Tutti e 4 i pacchetti engine-embedded sono ora Universo A.**

---

## 3. Flusso Decisionale ASCII

```
scf_bootstrap_workspace(install_base=True)
        │
        ▼
_get_package_install_context(package_id)
        │
        ├─► _try_local_install_context(package_id)
        │           │
        │           ├─► _resolve_local_manifest(engine_root, package_id)
        │           │       └─► legge packages/{id}/package-manifest.json dal disco
        │           │
        │           ├── manifest trovato E delivery_mode == "mcp_only"?
        │           │       YES ──► ritorna context dict con _universe="A"
        │           │       NO  ──► ritorna None  (Universe B fallback)
        │           │
        ├── result is not None?
        │       YES ──► UNIVERSO A: legge file da packages/{id}/ su disco locale
        │               (nessuna chiamata HTTP, no RegistryClient.fetch_package_manifest)
        │
        └── result is None?
                YES ──► UNIVERSO B: _ih._get_package_install_context()
                         └─► RegistryClient.fetch()  →  remote registry HTTPS
```

---

## 4. File Modificati

| File | Tipo | Descrizione modifica |
|------|------|---------------------|
| `spark/boot/tools_bootstrap.py` | modifica | Aggiunta `_resolve_local_manifest`, `_try_local_install_context`, `_build_local_file_records`, routing in `_get_package_install_context` |
| `packages/spark-base/package-manifest.json` | modifica | Aggiunto `"delivery_mode": "mcp_only"` |
| `tests/test_dual_universe_resolution.py` | nuovo | 4 test dual universe |
| `docs/architecture.md` | modifica | Sezione 3.1 Flusso Decisionale Dual-Universe aggiunta |
| `CHANGELOG.md` | modifica | Entry `[Unreleased]` Dual Universe Resolution |
| `README.md` | modifica | Contatore tools: 50 → 51 |

---

## 5. Implementazione Tecnica

### `_resolve_local_manifest(engine_root, package_id)`

Funzione standalone a livello di modulo. Legge
`engine_root/packages/{package_id}/package-manifest.json` dal disco.
Ritorna il dict JSON oppure `None` se il file non esiste.

```python
def _resolve_local_manifest(engine_root: Path, package_id: str) -> dict[str, Any] | None:
    manifest_path = engine_root / "packages" / package_id / "package-manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
```

### `_try_local_install_context(package_id)` — closure

Chiama `_resolve_local_manifest`. Se il manifest dichiara
`delivery_mode == "mcp_only"`, costruisce e ritorna un context dict con
`_universe: "A"`. Altrimenti ritorna `None`.

### `_get_package_install_context(package_id)` — shim aggiornato

```python
def _get_package_install_context(package_id):
    local_ctx = _try_local_install_context(package_id)
    if local_ctx is not None:
        return local_ctx                     # Universe A
    return _ih._get_package_install_context(package_id, registry, manifest)  # Universe B
```

### Bootstrap body

```python
if install_context.get("_universe") == "A":
    file_records = _build_local_file_records(...)
else:
    file_records = _build_remote_file_records(...)
```

---

## 6. Test Gate

| Test | Risultato |
|------|-----------|
| `test_local_context_returned_for_mcp_only_package` | ✅ PASS |
| `test_local_context_returns_none_when_no_local_manifest` | ✅ PASS |
| `test_local_context_returns_none_without_mcp_only` | ✅ PASS |
| `test_spark_base_real_manifest_qualifies_for_universe_a` | ✅ PASS |

**Suite completa** (escluso `test_integration_live.py`):

```
1 failed (pre-esistente: test_spark_base_manifest_no_longer_exports_operational_resources)
538 passed  (+4 vs baseline 534)
19 skipped  (invariato)
0 regressioni introdotte
```

---

## 7. Audit Checklist

| Voce | Stato |
|------|-------|
| `delivery_mode` routing verificato in `tools_bootstrap.py` | ✅ |
| Tutti i manifest `packages/*/package-manifest.json` dichiarano `delivery_mode` | ✅ |
| Nessuna scrittura su stdout (invariante transport stdio) | ✅ |
| Nessun breaking change manifest (SemVer preservato) | ✅ |
| Test suite +4p, 0 regressioni | ✅ |
| `docs/architecture.md` aggiornato con flusso decisionale ASCII | ✅ |
| `CHANGELOG.md [Unreleased]` aggiornato | ✅ |
| `README.md` contatore tools corretto (51) | ✅ |
| Nessuna modifica a `spark-framework-engine.py` (entry point protetto) | ✅ |

---

## 8. Divieti Rispettati

- ✅ No repo esterni per Universo A (risoluzione esclusivamente da `packages/` locali).
- ✅ No breaking manifest (SemVer e schema_version invariati).
- ✅ Nessun cambio a `spark-framework-engine.py`.

---

## 9. Prossime Azioni Consigliate

1. **Commit su branch** `workspace-slim-registry-sync-20260511`:
   ```
   git add spark/boot/tools_bootstrap.py packages/spark-base/package-manifest.json \
           tests/test_dual_universe_resolution.py docs/architecture.md \
           CHANGELOG.md README.md docs/reports/SPARK-REPORT-DualUniverse-v2.0.md
   git commit -m "feat: dual universe package resolution (A-local/B-remote)"
   ```
2. **Push** e proposta PR verso `main` (via `@Agent-Git`).
3. **scf-registry** — commit `registry.json` synced nel repo separato (via `@Agent-Git`).

---

*Generato da `@spark-engine-maintainer` — SPARK Framework Engine v3.4.0*
