<!-- markdownlint-disable MD029 MD032 -->

# SPARK REPORT - Engine v3.4.0 Workspace Alignment

Data: 2026-05-10
Scope: audit read-only workspace-wide (nessuna modifica ai package)
Motore target: 3.4.0

## 1) Tabella packages completa (non troncata)

| Repo/Package | File manifest | Versione package | min_engine_version | Allineato >= 3.4.0 | Action proposta |
| --- | --- | ---: | ---: | --- | --- |
| spark-framework-engine / spark-base (embedded) | packages/spark-base/package-manifest.json | 2.1.0 | 3.4.0 | S | Nessuna |
| spark-framework-engine / spark-ops (embedded) | packages/spark-ops/package-manifest.json | 1.1.0 | 3.4.0 | S | Nessuna |
| spark-framework-engine / scf-master-codecrafter (embedded) | packages/scf-master-codecrafter/package-manifest.json | 2.7.0 | 3.4.0 | S | Nessuna |
| spark-framework-engine / scf-pycode-crafter (embedded) | packages/scf-pycode-crafter/package-manifest.json | 2.3.0 | 3.4.0 | S | Nessuna |
| spark-framework-engine / pkg-smoke (embedded) | packages/pkg-smoke/package-manifest.json | 3.1.0 | 3.0.0 | N | Valutare bump a 3.4.0 se pacchetto attivo |
| spark-framework-engine / pkg-smoke (alias index) | packages/package-manifest.json | 3.1.0 | 3.0.0 | N | Tenere coerente con pkg-smoke |
| scf-master-codecrafter / scf-master-codecrafter (repo sorgente) | ../scf-master-codecrafter/package-manifest.json | 2.6.1 | 3.1.0 | N | Bump min_engine_version a 3.4.0 |
| scf-pycode-crafter / scf-pycode-crafter (repo sorgente) | ../scf-pycode-crafter/package-manifest.json | 2.2.2 | 3.1.0 | N | Bump min_engine_version a 3.4.0 |
| spark-base / spark-base (repo sorgente) | ../spark-base/package-manifest.json | 1.7.3 | 3.1.0 | N | Bump min_engine_version a 3.4.0 |

## 2) Gap rilevati

Conteggi:
- Obsoleti (min_engine_version < 3.4.0): 5/9
- Obsoleti embedded nel repo motore: 2/9 (pkg-smoke + alias index)
- Obsoleti repo sorgente esterni: 3/9 (spark-base, scf-master-codecrafter, scf-pycode-crafter)

Riferimenti hardcoded engine in .github:
- Nessuna evidenza di hardcode a 3.3.0 nei file operativi .github dei repo esterni.
- Rilevata cache registry obsoleta: .github/.scf-registry-cache.json con min_engine_version 3.1.0 e versioni vecchie.

## 3) Verifiche scf_* richieste

scf_verify_system (PRE):
- is_coherent: false
- issue: registry_stale (spark-base: registry 1.6.1 vs manifest 1.7.3)
- engine_version riportata dal tool: 3.2.0 (stale rispetto al branch corrente)

scf_verify_system (POST):
- invariato (nessuna implementazione eseguita in questo audit)

scf_check_updates / scf_list_installed / scf_list_available:
- non eseguibili come comandi shell in questo ambiente (command not found).
- fallback usato: confronto manifest locali + scf-registry/registry.json + .github/.scf-registry-cache.json.

## 4) Verifica rischi

1) Plugin con engine_min 3.3.0 -> crash su 3.4.0?
- Non trovati package a 3.3.0.
- Trovati package a 3.1.0/3.0.0: rischio di policy mismatch e update non proponibili correttamente su runtime 3.4.0.

2) .github workspace sovrascrive bootstrap? [S/N]
- N nel perimetro di questo audit (nessun update/install eseguito).
- In caso di update reale: dipende da update_policy e ownership policy; preservazione governata dai gate SCF.

3) scf_list_available mostra aggiornamenti?
- Da registry.json attuale: catalogo stale (spark-base 1.6.1, scf-master 2.5.1, scf-py 2.2.1), quindi non rappresenta lo stato reale dei repo sorgente.

4) TODO.md cita versioni vecchie?
- Nessun match rilevante su TODO nel workspace per 3.3.0/3.4.0.

## 5) Strategia allineamento (iterativa, NO esecuzione)

Piano allineamento v1.0:
1. Allineare i 3 repo sorgente esterni (spark-base, scf-master-codecrafter, scf-pycode-crafter) portando min_engine_version a 3.4.0.
2. Allineare package di test pkg-smoke (manifest principale + alias index) a min_engine_version 3.4.0 oppure escluderlo formalmente dal perimetro runtime.
3. Aggiornare scf-registry/registry.json e .github/.scf-registry-cache.json per eliminare drift versione.
4. Rieseguire scf_verify_system e scf_check_updates in runtime allineato.

Criterio PASS:
- Tutti i package target con min_engine_version >= 3.4.0
- scf_verify_system -> is_coherent: true
- Catalogo registry coerente con manifest sorgente

## 6) Comandi pronti (copy-paste, NON eseguiti)

Per repository esterni (manuale):

```bash
# spark-base
# edit package-manifest.json: min_engine_version -> 3.4.0

# scf-master-codecrafter
# edit package-manifest.json: min_engine_version -> 3.4.0

# scf-pycode-crafter
# edit package-manifest.json: min_engine_version -> 3.4.0
```

Per registry (manuale):

```bash
# scf-registry/registry.json
# allineare latest_version e min_engine_version ai manifest correnti
```

Per runtime workspace (dopo sync registry):

```bash
scf_update_batch spark-base scf-master-codecrafter scf-pycode-crafter
scf_verify_system
scf_check_updates
```

Per controllo locale finale:

```bash
grep -R "\"min_engine_version\"" **/package-manifest.json
```

## 7) Verdetto

VERDETTO: NON ALLINEATO (audit-only)

Motivo:
- Perimetro embedded del repo motore quasi allineato (eccetto pkg-smoke),
- ma 3 repo sorgente workspace e il registry risultano ancora su baseline 3.1.0 / versioni stale.

Stato merge:
- Nessuna implementazione applicata in questo audit.
- Richiesto ciclo allineamento multi-repo + registry prima del claim "workspace fully aligned".
