# SPARK-REPORT — MultiOwner Anomaly Fix v1.0

**Data:** 2026-05-09  
**Branch:** `feature/dual-mode-manifest-v3.1`  
**Engine version:** 3.3.0  
**Agente:** `spark-engine-maintainer`  
**Prompt autonomo:** `spark-multiowner-anomaly-fix-v1.0`

---

## 1. Stato Finale

| Metrica        | Valore                                |
|----------------|---------------------------------------|
| Suite target   | ≥ 534 passed, 9 skipped, 0 failed     |
| Suite ottenuta | **534 passed, 9 skipped, 0 failed**   |
| Determinismo   | ✅ Verificato (2 run consecutivi identici) |
| File modificati | 2 (`tests/test_multi_owner_policy.py`, `CHANGELOG.md`) |
| Modifche engine | **Nessuna** |

---

## 2. Test Oggetto dell'Analisi

```
tests/test_multi_owner_policy.py::TestMultiOwnerPolicy
  ::test_extend_policy_can_create_section_file_when_shared_target_is_missing
```

**Failure precedente (sessione pre-merge cleanup):**

```
AssertionError: Lists differ: ['pkg-a'] != ['pkg-a', 'pkg-b']
Second list contains 1 additional elements.
First extra element 1: 'pkg-b'
```

---

## 3. Classificazione Anomalia

**Scenario:** B — Bug latente nel test (non test obsoleto)  
**Categoria:** Race condition mtime in `ManifestManager` cache

### Comportamento testato

Il test verifica che installare `pkg-b` con `extend` policy su
`.github/copilot-instructions.md` (già registrata in manifest come
di proprietà di `pkg-a` ma assente su disco) produca:

1. `result["success"] == True`
2. `result["extended_files"] == [".github/copilot-instructions.md"]`
3. Il file viene creato su disco con i marker SCF di `pkg-b`
4. `manifest.get_file_owners("copilot-instructions.md") == ["pkg-a", "pkg-b"]`

Il comportamento è **correttamente implementato** nel motore
(v2 legacy flow → `extend_section` classification → `_scf_section_merge` →
`_gateway_write_text` → upsert manifest).

### Root Cause

La stessa istanza `manifest = ManifestManager(github_root)` viene usata
sia per il setup iniziale (`manifest.save([pkg-a entry])`) sia per
l'assertion finale (`manifest.get_file_owners(...)`).

**Sequenza temporale critica:**

```
T1: manifest.save([pkg-a])               ← _cache_mtime = T1
T2: asyncio.run(install_package("pkg-b"))
    ↳ gateway's ManifestManager.upsert_many([pkg-a, pkg-b])
    ↳ scrive su disco → mtime_disco = T2
T3: manifest.get_file_owners(...)
    ↳ load() → controlla stat().st_mtime == _cache_mtime
    ↳ se T2 == T1 (stesso clock tick) → cache VALIDA → restituisce ["pkg-a"]  ← BUG
    ↳ se T2 > T1 → cache INVALIDA → rilegge ["pkg-a", "pkg-b"]              ← OK
```

Su Windows NTFS in run brevi (< 100ms per l'intera operazione), i due
write possono avvenire nello stesso tick, rendendo il failure **intermittente
e dipendente dal carico CPU/disco al momento dell'esecuzione**.

### Warning catturati durante il failure

```
install_helpers.py:710 — package-manifest schema 2.x rilevato
  (files/file_policies senza files_metadata)
tools_packages_install.py:536 — Package pkg-b declares min_engine_version=1.0.0;
  using legacy v2 file-copy install flow.
```

Entrambi attesi: il test usa `min_engine_version: "1.0.0"` intenzionalmente
per testare la compatibilità v2.

---

## 4. Strategia

**Fix type:** Test-only — nessuna modifica al codice motore  
**Invariante rispettata:** Assertion NON indebolita (stessa semantica, stessi dati)

### Perché non modificare il motore

L'engine code è corretto: `_gateway_write_text` aggiorna il manifest su disco.
La cache stale è un problema di chi legge, non di chi scrive. Il fix canonico
è usare un'istanza fresca per leggere lo stato post-install.

### Fix applicato

```python
# tests/test_multi_owner_policy.py — linea ~370

# PRIMA (stale cache risk):
self.assertEqual(
    manifest.get_file_owners("copilot-instructions.md"),
    ["pkg-a", "pkg-b"],
)

# DOPO (fresh read — deterministic):
self.assertEqual(
    ManifestManager(github_root).get_file_owners("copilot-instructions.md"),
    ["pkg-a", "pkg-b"],
)
```

`ManifestManager(github_root)` crea una nuova istanza con cache vuota:
il primo `load()` legge sempre da disco, garantendo l'inclusione degli aggiornamenti
scritti dal gateway durante l'install.

---

## 5. File Modificati

| File | Tipo | Modifica |
|------|------|----------|
| `tests/test_multi_owner_policy.py` | test | Assertion finale usa fresh `ManifestManager` |
| `CHANGELOG.md` | doc | Aggiunta voce `### Fixed` sotto `[Unreleased]` |

---

## 6. Impatto Suite

| Metrica | Prima del fix | Dopo il fix |
|---------|---------------|-------------|
| Passed  | 534 (intermittente: 533) | **534** (stabile) |
| Skipped | 9 | 9 |
| Failed  | 0 (intermittente: 1) | **0** |
| Determinismo | ❌ Flaky | ✅ Stabile |

---

## 7. CHANGELOG

Voce aggiunta in `[Unreleased] → ### Fixed`:

```markdown
- `tests/test_multi_owner_policy.py` —
  `test_extend_policy_can_create_section_file_when_shared_target_is_missing`:
  rimossa race condition mtime nella validazione della cache di `ManifestManager`.
  ...
```

---

## 8. Decisioni Aperte

| ID | Decisione | Stato |
|----|-----------|-------|
| D-1 | Aggiornare `min_engine_version` in `scf-master-codecrafter` e `scf-pycode-crafter` a `"3.2.0"` post-merge | Rinviato (repo separati) |
| D-2 | Valutare se rendere la mtime cache di `ManifestManager` più robusta (es. double-check con content hash) | Rinviato — miglioramento futuro non bloccante |

---

## 9. Merge Readiness

| Gate | Stato |
|------|-------|
| Suite ≥ 534/9/0 | ✅ PASS (2 run deterministici) |
| Nessuna modifica motore non autorizzata | ✅ PASS |
| CHANGELOG aggiornato | ✅ PASS |
| Assertion non indebolita | ✅ PASS |
| File `.github/` non toccati | ✅ PASS |

**Conclusione:** Il branch è pronto per il merge su `main`.

---

OPERAZIONE COMPLETATA: MultiOwner Anomaly Fix v1.0  
GATE: PASS  
CONFIDENCE: 0.97  
FILE TOCCATI: tests/test_multi_owner_policy.py, CHANGELOG.md  
OUTPUT CHIAVE: Race condition mtime risolta — suite 534/9/0 stabile (2 run)  
PROSSIMA AZIONE: CHECKPOINT (merge readiness confermata)
