---
title: "SPARK-REPORT-Engine-v3.4.0-External-Alignment-v1.1"
date: "2026-05-10"
author: "spark-engine-maintainer"
status: "AUDIT-REPORT"
scope: "External repo .github/ workspace only (NO packages/ motore)"
engine_version: "3.4.0"
audit_version: "1.1.0"
---

# SPARK Engine v3.4.0 — External Repo Alignment Audit (v1.1)

**Scope Correction**: v1.0 audited mixed packages/ + external repos; v1.1 focuses ONLY external .github/ workspace manifests.

---

## FASE 0 — Perimeter Definition

### Repo Target Identificati

| Repo | Percorso locale | Tipo | Stato |
|------|-----------------|------|-------|
| **scf-master-codecrafter** | `../scf-master-codecrafter/` | External workspace | ✅ Identificato |
| **scf-pycode-crafter** | `../scf-pycode-crafter/` | External workspace | ✅ Identificato |
| **spark-base** | `../spark-base/` | External workspace | ✅ Identificato |
| **scf-registry** | `../scf-registry/` | External workspace | Registry only |

**Total repo scanned**: 3 (active packages) + registry

---

## FASE 1 — Scansione Manifest

### File scanionati

```
✅ ../scf-master-codecrafter/package-manifest.json (schema v3.1)
✅ ../scf-pycode-crafter/package-manifest.json (schema v3.1)
✅ ../spark-base/package-manifest.json (schema v3.0)
✅ ../scf-registry/registry.json (schema v2.0)
```

**Esclusioni applicate**:
- ❌ `packages/spark-base/package-manifest.json` (embedded motore, già audited in v1.0)
- ❌ `packages/spark-ops/package-manifest.json` (embedded motore)
- ❌ `packages/scf-master-codecrafter/package-manifest.json` (embedded motore)
- ❌ `packages/scf-pycode-crafter/package-manifest.json` (embedded motore)

---

## FASE 2 — Tabella Compatibilità Externa

| Repo esterno | Versione locale | min_engine_version locale | vs. v3.4.0 | Status | Action |
|---|---|---|---|---|---|
| **scf-master-codecrafter** | 2.6.1 | 3.1.0 | OBSOLETE | ❌ | Update required |
| **scf-pycode-crafter** | 2.2.2 | 3.1.0 | OBSOLETE | ❌ | Update required |
| **spark-base** | 1.7.3 | 3.1.0 | OBSOLETE | ❌ | Update required |

### Summary

```
Total repo esterni: 3
Allineati a 3.4.0: 0
Obsoleti (min < 3.4.0): 3
Tasso allineamento: 0/3 (0%)
```

---

## FASE 3 — Registry Status

### Remote Registry Snapshot

File scanned: `../scf-registry/registry.json` (updated: 2026-05-04)

| Pacchetto | latest_version registry | min_engine registry | vs. local | Status |
|---|---|---|---|---|
| **spark-base** | 1.6.1 | 3.1.0 | LOCAL 1.7.3 > REGISTRY 1.6.1 | ⚠️ STALE |
| **scf-master-codecrafter** | 2.5.1 | 3.1.0 | LOCAL 2.6.1 > REGISTRY 2.5.1 | ⚠️ STALE |
| **scf-pycode-crafter** | 2.2.1 | 3.1.0 | LOCAL 2.2.2 > REGISTRY 2.2.1 | ⚠️ STALE |

### Conclusions

1. **Registry is STALE**: All `latest_version` fields show older versions than current local manifests
2. **min_engine_version uniformly 3.1.0**: NO remote package has been updated to 3.4.0
3. **Update required locally AND remotely**: Bump min_engine_version in both local manifests + registry

---

## FASE 4 — Update Strategy (Iterative)

### Alignment Plan v1.0

**Step 1: Update local manifests (EXTERNAL repos)**

```bash
# Update min_engine_version from 3.1.0 → 3.4.0 in each external repo:
scf_update scf-master-codecrafter --min-engine-version 3.4.0
scf_update scf-pycode-crafter --min-engine-version 3.4.0
scf_update spark-base --min-engine-version 3.4.0
```

**Step 2: Verify system**

```bash
scf_verify_system --remote
```

**Step 3: Check registry updates**

```bash
scf_list_available | grep -E "(scf-|spark-base)"
```

**Step 4: Sync registry** (if registry still stale)

```bash
# Manual registry.json update or registry-sync script
cd ../scf-registry && \
  git pull origin main && \
  python scripts/sync-from-packages.py && \
  git add registry.json && \
  git commit -m "sync: bump min_engine_version to 3.4.0 for all packages" && \
  git push origin main
cd ../spark-framework-engine
```

### Iterative Validation

**VERDETTO condition**:
```
PASS if:
  ✅ All 3 repo min_engine_version == 3.4.0
  ✅ scf_verify_system --remote exits with 0
  ✅ registry.json latest_version reflects current local versions
```

---

## FASE 5 — Commands Ready for Copy-Paste

### Batch update (LOCAL only, NO registry)

```bash
# Execute in spark-framework-engine root:
scf_update scf-master-codecrafter --min-engine-version 3.4.0
scf_update scf-pycode-crafter --min-engine-version 3.4.0
scf_update spark-base --min-engine-version 3.4.0
```

### Verification

```bash
# Verify system and list available (check if registry updated):
scf_verify_system --remote
scf_list_available | grep -E "(scf-|spark-base)" | sort
```

### Registry Sync (if necessary)

```bash
# If registry still stale after scf_update above:
cd ../scf-registry
git pull origin main

# Synchronize registry.json from packages (manual or script):
# Option A: If sync script exists
python scripts/sync-from-packages.py

# Option B: Manual edit (verify each package latest_version + min_engine):
# Update registry.json min_engine_version entries manually to 3.4.0

git add registry.json
git commit -m "sync: align registry min_engine_version to v3.4.0 post-engine-release"
git push origin main

cd ../spark-framework-engine
```

---

## FASE 6 — Gap Analysis & Risks

### Identified Gaps

1. **Local manifests gap**: All 3 external repos have min_engine_version 3.1.0, NOT 3.4.0
   - **Impact**: Tools declaring compatibility will mistakenly accept these packages with old engine
   - **Risk**: Silent failures when user installs scf-master-codecrafter 2.6.1 on engine 3.4.0

2. **Registry stale**: scf-registry/registry.json shows older latest_version values
   - **spark-base**: Registry 1.6.1 vs. actual local 1.7.3
   - **scf-master-codecrafter**: Registry 2.5.1 vs. actual local 2.6.1
   - **scf-pycode-crafter**: Registry 2.2.1 vs. actual local 2.2.2
   - **Impact**: Users installing from registry will get outdated versions
   - **Risk**: Cascading dependency failures if user installs old version that requires old engine

3. **Workflow hardcodes**: Check if any workflow files (.github/workflows/*.yml) reference engine 3.3.0
   - Target: `../scf-*/,../spark-base/.github/workflows/**/*.yml`
   - Command: `grep -r "spark-engine.*3\.3\|ENGINE_VERSION.*3\.3" ../scf-* ../spark-base/.github/workflows/`

### Validation Checklist

```
BEFORE EXECUTION:
  ☐ Verify all 3 repo branches are clean (git status clean)
  ☐ Verify local git credential is configured
  ☐ Confirm registry sync strategy (manual vs. automated)
  
DURING EXECUTION:
  ☐ Run scf_update batch for 3 repos
  ☐ Verify system (scf_verify_system --remote)
  ☐ Check registry status (scf_list_available)
  ☐ Verify workflow files if any hardcode 3.3.0
  
POST EXECUTION:
  ☐ Run full test suite: pytest -q --ignore=tests/test_integration_live.py
  ☐ Verify all 3 repo tags updated if applicable
  ☐ Confirm registry.json has been updated
  ☐ Update CHANGELOG.md with external alignment note
```

---

## FASE 7 — Verdetto

### Current State (2026-05-10 v3.4.0 release)

| Criteria | Status | Evidence |
|----------|--------|----------|
| **Engine released** | ✅ PASS | spark-framework-engine v3.4.0 (constants.py, ENGINE_VERSION) |
| **Internal packages aligned** | ✅ PASS | All 4 embedded packages min_engine_version 3.4.0 |
| **External repos aligned** | ❌ **FAIL** | scf-master-codecrafter, scf-pycode-crafter, spark-base still 3.1.0 |
| **Registry updated** | ❌ **FAIL** | scf-registry shows stale latest_version + old min_engine_version |

### Overall Alignment Status

```
VERDICT: NON-ALLINEATO (Not Aligned)
REASON: 3/3 external repos + registry obsolete vs. v3.4.0
BLOCKERS: Update min_engine_version in 3 local manifests + sync registry
READINESS: READY FOR IMPLEMENTATION after gap closure
```

---

## Report Metadata

```
Audit scope: External .github/ workspace only
Repos scanned: 3 (scf-master-codecrafter, scf-pycode-crafter, spark-base)
Registry scanned: scf-registry/registry.json
Manifest files verified: 3 local + 1 registry = 4 total
Engine version: 3.4.0
Audit date: 2026-05-10
Audit version: v1.1.0
Status: COMPLETE (read-only, NO implementation executed)
```

---

## Next Actions

1. **User decision**: Proceed with external repo alignment (Step 1-4 in FASE 4)?
2. **If YES**: Execute commands in FASE 5 (copy-paste ready, NO manual edits needed)
3. **If NO**: Archive this report for future reference when external repos need sync

---

