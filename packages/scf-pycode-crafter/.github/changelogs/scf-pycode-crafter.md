---
spark: true
scf_file_role: "config"
scf_version: "2.0.1"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_merge_priority: 30
---
<!-- markdownlint-disable MD024 -->

# CHANGELOG — scf-pycode-crafter

## [Unreleased]

### Changed

- Manifest aggiornato a `2.3.0`: la dipendenza minima da
  `scf-master-codecrafter` passa a `2.7.0`, ereditando il nuovo layer operativo
  `spark-ops`.

## [2.2.1] — 2026-04-28

### Changed

- Bump patch di compatibilita: `min_engine_version` aggiornata a `3.1.0` senza
  cambiamenti funzionali agli agenti/tool Python del pacchetto.

## [2.0.1] — 2026-04-15

### Changed

- `min_engine_version` del pacchetto aggiornata a `2.4.0` per allinearla al layer `scf-master-codecrafter` e al registry corrente.
- Frontmatter version dei componenti Python gestiti dal pacchetto riallineati a `2.0.1`.
- README del pacchetto aggiornato alla compatibilita reale con `spark-framework-engine >= 2.4.0`.

---

## [2.0.0] — 2026-04-10

### Added

- Creato `.github/AGENTS-python.md` come indice plugin-specifico degli agenti Python.
- Creato `.github/python.profile.md` come profilo tecnico del plugin Python.
- Aggiunti `plugin`, `capabilities` e `languages` al frontmatter degli agenti Python mantenuti.

### Changed

- Il pacchetto ora dipende da `scf-master-codecrafter`.
- `min_engine_version` aggiornato a `1.9.0`.
- Il perimetro del pacchetto viene ridotto ai soli componenti Python-specifici.

### Removed

- Rimossi agenti, skill, instruction e file root trasversali migrati nel layer master.

---

## [1.2.1] — 2026-04-02

### Added

- Campo `spark: true` nel frontmatter YAML di tutti i componenti gestiti dal pacchetto
  (agenti, skill, instruction) per consentire al motore la classificazione tripartita
  dei file non tracciati (`managed` / `user` / `untagged`).
- Campo `name:` aggiunto al frontmatter delle instruction (dove mancante), coerente
  con la convenzione già presente in agenti e skill.

### Changed

- Campo `version` nel frontmatter di tutti i componenti aggiornato a `1.2.1`
  (versione pacchetto al momento dell'ultima modifica).

---

## [1.2.0] — 2026-04-02

### Added

- Migrazione 7 skill al formato cartella Agent Skills standard con asset bundlati:
  `docs-manager`, `clean-architecture` (ex `clean-architecture-rules`),
  `error-recovery`, `changelog-entry`, `validate-accessibility`,
  `project-doc-bootstrap`, `framework-query`.
- Ogni skill migrata include template, reference o checklist bundlati
  come asset separati nella propria cartella.
- `framework-query` ora include `reference/mcp-tool-index.md`:
  indice completo dei tool MCP e della struttura workspace.
- Checklist NVDA e navigazione da tastiera come asset dedicati
  in `validate-accessibility/checklists/`.

### Changed

- `framework-scope-guard` rinominata `task-scope-guard` per correttezza semantica:
  la skill riguarda lo scope generale dei task, non specificamente SCF.
- `framework-index` fusa in `framework-query`: il contenuto dell'indice
  navigabile è ora in `framework-query/reference/mcp-tool-index.md`.
- `clean-architecture-rules` rinominata `clean-architecture` (nome più conciso).
- `min_engine_version` aggiornata a `1.3.0`.

### Removed

- `framework-index.skill.md` — contenuto assorbito da `framework-query/`.
- `framework-scope-guard.skill.md` — sostituita da `task-scope-guard.skill.md`.
- `clean-architecture-rules.skill.md` — sostituita da `clean-architecture/`.

<!-- markdownlint-enable MD024 -->

---

## [1.1.0] — 2026-04-01

### Breaking Changes

- Tutti gli agenti rinominati con prefisso `py-` per namespace plugin in ecosistemi SCF multi-plugin.
  Riferimenti a `Agent-Code`, `Agent-Plan`, `Agent-Validate`, ecc. vanno aggiornati a
  `py-Agent-Code`, `py-Agent-Plan`, `py-Agent-Validate`, ecc.

### Modificato

- Rinominati 11 file agente da `Agent-Xxx.md` a `py-Agent-Xxx.md`
- Aggiornato campo `name:` nel frontmatter di ciascun agente
- Aggiornato `AGENTS.md` con i nuovi nomi nella tabella indice
- Aggiornate skill `agent-selector`, `code-routing`, `framework-index`, `validate-accessibility`
- Aggiornato `package-manifest.json` con i nuovi path agenti

---

## [1.0.1] — 2026-03-31

### Manutenzione

- Rimosso `.github/FRAMEWORK_CHANGELOG.md` (legacy redirect).
  Il changelog canonico e esclusivamente questo file.
  Richiede spark-framework-engine >= 1.2.1.

### Infrastruttura

- Aggiunto `.github/workflows/sync-registry.yml`: workflow GitHub Actions che sincronizza
  automaticamente `scf-registry/registry.json` ad ogni push su `main` che modifica
  `package-manifest.json`. Apre una PR automatica sul registry con `latest_version` e
  `engine_min_version` aggiornati dai valori del manifest (fonte canonica).
  Prerequisito operativo: secret `REGISTRY_WRITE_TOKEN` configurato nel repo.

## [1.0.0] — 2026-03-30

### Prima release pubblica

- Pacchetto SCF iniziale per progetti Python.
- 11 agenti specializzati: Analyze, Code, CodeRouter, Design, Docs, Git, Helper, Orchestrator, Plan, Release, Validate.
- 26 skill operative: accessibilità, architettura pulita, changelog, commit convenzionali, documentazione, error recovery, framework guard, git, profilo progetto, rollback, semantic gate, semver, stile, test, verbosità.
- 10 instruction files: framework-guard, git-policy, model-policy, personality, project-reset, python, tests, verbosity, workflow-standard.
- Compatibile con spark-framework-engine >= 1.2.0.
