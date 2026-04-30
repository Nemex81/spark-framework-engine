# TODO — Implementazione scf-master-codecrafter

## Stato generale

- [x] Analisi preliminare dei repository coinvolti completata
- [x] Validazione del piano completata
- [x] Piano aggiornato con strategia correttiva
- [x] Fase A completata e validata
- [x] Fase B completata e validata
- [x] Fase C completata e validata
- [x] Fase D completata e validata
- [x] Validazione finale cross-repo completata

## Fase A — spark-framework-engine → 1.5.0

- [x] A1 Bump `ENGINE_VERSION` a `1.5.0`
- [x] A2 Aggiunti `list_agents_indexes()`, `get_orchestrator_state()`, `set_orchestrator_state()`
- [x] A3 Aggiornata resource `scf://agents-index`
- [x] A4 Aggiunti tool `scf_get_runtime_state()` e `scf_update_runtime_state()`
- [x] A5 Aggiunta resource `scf://runtime-state`
- [x] A6 Aggiornato log resources a 15
- [x] A7 Aggiornato docstring tools a 25
- [x] A8 Aggiornato `CHANGELOG.md`
- [x] Validazione Fase A completata

## Fase B — bootstrap scf-master-codecrafter

- [x] Creata struttura `.github/` del master
- [x] Creati file root (`AGENTS.md`, `copilot-instructions.md`, `project-profile.md`, changelog)
- [x] Creati agenti esecutori
- [x] Creati agenti dispatcher
- [x] Create instructions trasversali
- [x] Create skill e asset richiesti dal manifest
- [x] Creato runtime state default
- [x] Verificato allineamento con `package-manifest.json`
- [x] Validazione Fase B completata

## Fase C — scf-pycode-crafter → 2.0.0

- [x] Creato `.github/AGENTS-python.md`
- [x] Creato `.github/python.profile.md`
- [x] Aggiornato frontmatter dei `py-Agent-*`
- [x] Rimossi i file migrati al master
- [x] Aggiornato `package-manifest.json`
- [x] Aggiornato changelog del pacchetto
- [x] Preservato `.github/workflows/notify-engine.yml`
- [x] Validazione Fase C completata

## Fase D — scf-registry

- [x] Aggiunta entry `scf-master-codecrafter`
- [x] Aggiornata entry `scf-pycode-crafter` a `2.0.0`
- [x] Aggiornato `engine_min_version` a `1.5.0`
- [x] Validazione JSON completata
- [x] Validazione Fase D completata

## Validazione finale

- [x] Verificati contatori tool/resource del motore
- [x] Verificata esistenza di tutti i file del manifest master
- [x] Verificata assenza dei file migrati in `scf-pycode-crafter`
- [x] Verificato registry coerente con master e plugin Python
- [x] Verificato che non ci siano modifiche in `tabboz-simulator-202`

## Nuovo ciclo correttivo ecosistema - 2026-04-10

- [x] Audit completo cross-repo completato
- [x] Strategia correttiva formalizzata
- [x] Piano tecnico salvato in `docs/PIANO-CORRETTIVO-ECOSISTEMA-2026-04-10.md`
- [x] R0 Contratto registry riallineato
- [x] R1 Documentazione pubblica riallineata
- [x] R2 Update package dependency-aware implementato
- [x] R3 Test ecosistema estesi
- [x] R4 Prompt e UX MCP aggiornati
- [x] R5 Release readiness cross-repo verificata

## Correzione split spark-base/master - 2026-04-15

- [x] Audit completo di engine, registry, base, master e plugin Python
- [x] Verificata la regressione di `code-Agent-Code` nel layer master
- [x] Verificata l'assenza di `spark-guide` nel package `spark-base`
- [x] Reintrodurre `code-Agent-Code` come executor generico del master
- [x] Promuovere `spark-guide` a file gestito da `spark-base`
- [x] Allineare motore, manifest e registry per ownership e versioni

## Task attivi

- [ ] Razionalizzazione SPARK 2026-04-23
  - Piano: `docs/PIANO-RAZIONALIZZAZIONE-SPARK-OWNERSHIP-CLEANUP-2026-04-23.md`
  - TODO: `docs/todolist/TODO-RAZIONALIZZAZIONE-SPARK-OWNERSHIP-CLEANUP-2026-04-23.md`
  - Stato: audit completato, esecuzione bloccata da `framework_edit_mode: false` su `.github/**` e dalle conferme git per push/tag
- [ ] Razionalizzazione agenti comuni 2026-04-23
  - Piano: `docs/PIANO-RAZIONALIZZAZIONE-AGENTI-COMUNI-2026-04-23.md`
  - TODO: `docs/todolist/TODO-RAZIONALIZZAZIONE-AGENTI-COMUNI-2026-04-23.md`
  - Stato: Fase A e Fase B completate localmente; restano solo eventuale commit locale via Agent-Git e nessun push senza conferma `PUSH`
