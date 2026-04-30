---
task: razionalizzazione-spark-ownership-cleanup
agent: Agent-Orchestrator
status: DRAFT
date: 2026-04-23
repositories:
  - spark-base
  - scf-master-codecrafter
  - scf-registry
  - spark-framework-engine
---

# Piano Tecnico — Razionalizzazione SPARK 2026-04-23

## Executive Summary

Il piano operativo proposto dall'utente non e validabile senza correzioni.
Lo stato reale dei repository mostra che la pulizia ownership di
`scf-master-codecrafter` e gia in larga parte completata, mentre le modifiche
residue richieste ricadono quasi interamente sotto `.github/**` nei repository
`spark-base` e `scf-master-codecrafter`, attualmente protetti da
`framework_edit_mode: false`.

Questo piano sostituisce quindi la sequenza originale con una strategia
correttiva a due livelli:

1. eseguire subito audit, coordinamento, pianificazione e validazione del delta reale;
2. rinviare le scritture su `.github/**`, i changelog sotto `.github/` e qualsiasi push/tag
   ai gate espliciti richiesti dalle policy (`#framework-unlock`, `PUSH`).

## Validazione del piano originale

### Esito

FAIL

### Motivi bloccanti

1. `scf-master-codecrafter/package-manifest.json` e gia a `2.2.0`, con
   `dependencies: ["spark-base"]`, `min_engine_version: "2.4.0"` e file list
   limitata alle componenti esclusive del layer master.
2. In `scf-master-codecrafter/.github/skills/` non risultano duplicati top-level
   da rimuovere come previsto dal piano originario; risultano invece componenti
   esclusivi o ibridi gia divergenti.
3. In entrambi i repository framework coinvolti, i file protetti sotto `.github/**`
   risultano bloccati da `framework_edit_mode: false` nei rispettivi
   `.github/project-profile.md`.
4. Le operazioni di push e tag richiedono conferma esplicita secondo la policy git;
   non sono eseguibili in autonomia in questa sessione senza gate testuale dedicato.

## Audit sintetico confermato

### spark-base

- `package-manifest.json` e gia a `1.4.0`
- `min_engine_version` e gia `2.4.0`
- il set skill locale contiene 24 file/asset
- restano riferimenti cross-package o rotti nei body importati sotto `.github/agents/`

### scf-master-codecrafter

- `package-manifest.json` e gia a `2.2.0`
- `file_ownership_policy` e `error`
- `dependencies` contiene gia `spark-base`
- skill esclusive confermate:
  - `.github/skills/clean-architecture/SKILL.md`
  - `.github/skills/docs-manager/SKILL.md`
  - `.github/skills/code-routing.skill.md`
- instruction esclusiva confermata:
  - `.github/instructions/mcp-context.instructions.md`

### Cross-package refs in spark-base

Riferimenti errati confermati verso:

- `.github/skills/clean-architecture-rules.skill.md`
- `.github/skills/docs_manager.skill.md`
- `.github/skills/framework-index.skill.md`
- `.github/skills/framework-query.skill.md`
- `.github/skills/changelog-entry.skill.md`
- `.github/skills/validate-accessibility.skill.md`
- `.github/skills/project-doc-bootstrap.skill.md`

Riferimenti rotti o non posseduti localmente confermati verso:

- `.github/instructions/tests.instructions.md`
- `.github/instructions/project.instructions.md`

## Strategia correttiva approvabile

### Fase A — Coordinamento documentale

- creare piano tecnico e TODO per-task
- aggiornare `docs/TODO.md` come coordinatore
- segnare esplicitamente i gate bloccanti

### Fase B — Delta eseguibile senza unlock

- nessuna rimozione ulteriore in `scf-master-codecrafter` finche non emerge un nuovo duplicato reale
- nessun update a `package-manifest.json` in `scf-master-codecrafter`: lo stato corrente e gia coerente con l'obiettivo dichiarato
- nessun update a `scf-registry/registry.json`: le versioni correnti risultano gia allineate

### Fase C — Delta bloccato da framework guard

Richiede `#framework-unlock` prima di toccare:

- `spark-base/.github/agents/*.md`
- `spark-base/.github/changelogs/spark-base.md`
- `scf-master-codecrafter/.github/changelogs/scf-master-codecrafter.md`

### Fase D — Delta bloccato da policy git

Richiede conferme esplicite prima di eseguire:

- commit via Agent-Git, se richiesto con conferma messaggio
- push di qualunque repository con `PUSH`
- tag `v1.4.0` su `spark-base` con conferma esplicita

## Piano di implementazione corretto

1. Documentare il delta reale e i blocchi correnti.
2. Mantenere invariati manifest e registry, gia coerenti con l'obiettivo finale.
3. Preparare la lista precisa delle sostituzioni nei file `spark-base` per un batch unico post-unlock.
4. Dopo unlock:
   - correggere i path cross-package
   - rimuovere i riferimenti rotti a `project.instructions.md` e `tests.instructions.md`
   - aggiungere le note di dipendenza plugin per le skill fornite da `scf-master-codecrafter`
   - aggiornare i changelog di `spark-base` e `scf-master-codecrafter`
5. Dopo commit locali, eseguire push e tag solo con conferme policy-compliant.

## Gate di uscita

### Gate 1 — Pass

- audit multi-repo coerente e documentato
- piano tecnico correttivo salvato
- TODO per-task creato
- coordinatore `docs/TODO.md` aggiornato

### Gate 2 — Bloccato in attesa di unlock

- scrittura su `.github/**` in `spark-base`
- scrittura su `.github/**` in `scf-master-codecrafter`

### Gate 3 — Bloccato in attesa di conferma git

- push repository
- tag `spark-base v1.4.0`

## Output atteso alla ripresa operativa

Alla ripresa, il batch minimo di modifica dovra produrre:

- fix dei path cross-package nei file agenti di `spark-base`
- rimozione dei riferimenti rotti a instruction non distribuite
- annotazioni di dipendenza per skill fornite da `scf-master-codecrafter`
- changelog aggiornati nei due pacchetti
- eventuali commit/push/tag eseguiti via Agent-Git con conferme esplicite
