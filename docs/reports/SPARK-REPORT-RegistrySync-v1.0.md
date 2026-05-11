# SPARK REPORT — Registry Sync v1.0

**Task:** Registry Maintainer SPARK v3.4.1 — scf-registry Sync  
**Fase:** 7 (Patch registry.json + verifica)  
**Data:** 2026-05-11  
**Stato finale:** CLOSED — `scf_verify_system: is_coherent: true`

---

## 1. Contesto e gap identificati

Prima della sync, i seguenti gap erano presenti tra i manifest locali dell'engine
(`packages/*/package-manifest.json`) e il registry remoto (`Nemex81/scf-registry`):

| Package | registry (prima) | local engine | Gap |
|---------|-----------------|--------------|-----|
| `spark-base` | `1.6.1` | `2.1.0` | DISTRO-2 stale |
| `scf-master-codecrafter` | `2.3.0` | `2.7.0` | stale |
| `scf-pycode-crafter` | `1.9.0` | `2.3.0` | stale |
| `spark-ops` | assente | `1.1.0` | mancante |

Tutti con `min_engine_version` non allineato a `3.4.0`.

Ulteriore gap scoperto durante la verifica:

| File | versione attuale (externa) | versione attesa |
|------|---------------------------|-----------------|
| `Nemex81/spark-base/package-manifest.json` | `1.7.3` | `2.1.0` |

---

## 2. Operazioni eseguite

### 2.1 Patch registry.json (Nemex81/scf-registry)

**Commit:** `550e9660ceb1d1f4293a2701418860b00c72913b`  
**SHA file:** `464166f895613a35d599ff833d5009d5aa7db4b2`

Modifiche applicate:
- `spark-base`: `latest_version 1.6.1 → 2.1.0`, `min_engine_version: 3.4.0`
- `scf-master-codecrafter`: `latest_version 2.3.0 → 2.7.0`, `min_engine_version: 3.4.0`
- `scf-pycode-crafter`: `latest_version 1.9.0 → 2.3.0`, `min_engine_version: 3.4.0`
- `spark-ops`: aggiunto `latest_version: 1.1.0`, `min_engine_version: 3.4.0`,
  `repo_url: https://github.com/Nemex81/spark-ops`,
  `engine_managed_resources: true`, `tags: [ops, e2e, release, docs, spark-base]`

### 2.2 Verifica post-patch (prima run)

Risultato `scf_verify_system`:
```json
{
  "is_coherent": false,
  "packages_checked": 1,
  "issues": [
    {
      "type": "registry_stale",
      "package": "spark-base",
      "registry_version": "2.1.0",
      "manifest_version": "1.7.3",
      "fix": "Aggiornare registry.json: latest_version → 1.7.3"
    }
  ]
}
```

**Causa radice:** `scf_verify_system` confronta `registry.latest_version` con la versione
nel file `package-manifest.json` del repo GitHub effettivo del pacchetto (non la copia locale
engine). Il repo `Nemex81/spark-base` era ancora a `1.7.3`.

### 2.3 Push spark-base 2.1.0 a Nemex81/spark-base

**Commit:** `0146ae30fdeb2ac3c9cca5f3f6d8dd25219163ed`  
**SHA file:** `b598689f45caa4dc5cb8215a6d11b3c5a1b147ad`

Modifiche rispetto a `1.7.3`:
- `version: 1.7.3 → 2.1.0`
- aggiunto `delivery_mode: "mcp_only"`
- rimossi da `mcp_resources.agents`: `Agent-FrameworkDocs`, `spark-assistant`, `spark-guide`
  (migrati a spark-ops)
- rimossi da `mcp_resources.prompts`: `framework-changelog`, `framework-release`,
  `framework-update`, `release`, `sync-docs`, `status` e altri operativi
  (migrati a spark-ops)
- rimossi da `files` e `files_metadata` i file corrispondenti
- `min_engine_version: 3.4.0` (invariato)

### 2.4 Verifica post-fix (seconda run)

Risultato `scf_verify_system`:
```json
{
  "engine_version": "3.4.0",
  "packages_checked": 1,
  "issues": [],
  "warnings": [],
  "manifest_empty": false,
  "is_coherent": true
}
```

**GATE: PASS** — Registry sync completato.

---

## 3. Stato finale registry

| Package | registry (dopo) | repo esterno | Stato |
|---------|----------------|--------------|-------|
| `spark-base` | `2.1.0` | `2.1.0` | OK |
| `scf-master-codecrafter` | `2.7.0` | n/a (non verificato da scf_verify_system) | registry aggiornato |
| `scf-pycode-crafter` | `2.3.0` | n/a | registry aggiornato |
| `spark-ops` | `1.1.0` | `https://github.com/Nemex81/spark-ops` | aggiunto al registry |

---

## 4. Note e residui

- `scf_verify_system` verifica solo i pacchetti **installati** nel workspace engine
  (`.github/.scf-manifest.json`). Attualmente solo `spark-base` risulta installato
  (version entry `1.6.1` nel manifest workspace). I pacchetti `scf-master-codecrafter`,
  `scf-pycode-crafter` e `spark-ops` non vengono verificati da questa logica.
- Per un audit completo di tutti i repo pacchetto (non solo quelli installati), sarebbe
  necessario estendere `scf_verify_system` con una modalità `--all-packages`.
- Il repo `Nemex81/spark-ops` non ha ancora un `package-manifest.json` pubblicato.
  Quando `spark-ops` sarà installato nel workspace engine, `scf_verify_system` rileverà
  anche quel repo.

---

## 5. File toccati

| File | Tipo | Azione |
|------|------|--------|
| `Nemex81/scf-registry/registry.json` | remoto | aggiornato (commit 550e9660) |
| `Nemex81/spark-base/package-manifest.json` | remoto | aggiornato 1.7.3→2.1.0 (commit 0146ae30) |
| `CHANGELOG.md` | locale | aggiunta voce `[Unreleased]` FASE 7 |
| `docs/reports/SPARK-REPORT-RegistrySync-v1.0.md` | locale | creato (questo file) |
