# Analisi strategica: riorganizzazione componenti — spark-base

- **Data**: 15 aprile 2026
- **Autore**: Agent-Analyze (ciclo autonomo read-only)
- **Scope**: fattibilità, rischi e piano implementativo per spostare componenti
  general-purpose da `scf-master-codecrafter` a un nuovo pacchetto `spark-base`
- **Engine di riferimento**: spark-framework-engine v2.0.0

---

## EXECUTIVE SUMMARY

La migrazione è **tecnicamente fattibile** ma con un prerequisito operativo
aggiuntivo: prima dell'implementazione va introdotto un dry-run di installazione
(`scf_preview_install` o equivalente), oggi assente nel motore. Il nodo principale è l'assenza di un meccanismo
`scf_transfer_ownership`: la strategia obbliga a una sequenza
remove → install spark-base → reinstall master (ridotto). Il rischio globale è
**BASSO** dato l'utente unico e l'assenza di backward compat da preservare.

**Raccomandazione: GO CON PRECHECK** — con `scf_verify_workspace` pulito,
dry-run del manifest spark-base, esecuzione in sessione singola e gate di
verifica post-migrazione.

---

## INVENTARIO CLASSIFICATO

### Agenti (14 in scf-master-codecrafter)

- `Agent-Analyze.md` — dispatcher analisi read-only — **BASE**
- `Agent-Plan.md` — dispatcher breakdown/checklist — **BASE**
- `Agent-Docs.md` — dispatcher sincronizzazione docs — **BASE**
- `Agent-Helper.md` — executor consultivo read-only — **BASE**
- `Agent-Research.md` — support interno, fallback ricerca — **BASE**
- `Agent-Welcome.md` — executor setup profilo progetto — **BASE**
- `Agent-FrameworkDocs.md` — executor docs framework `.github/` — **BASE**
- `Agent-Git.md` — executor operazioni git autorizzate — **BASE**
- `Agent-Orchestrator.md` — executor ciclo E2E autonomo — **BORDERLINE → BASE**
  - Ragionamento: orchestra qualsiasi tipo di progetto, non solo coding.
    Referenzia skill cross-package via capability dinamica, non per path.
- `Agent-Release.md` — executor versioning/release — **BORDERLINE → BASE**
  - Ragionamento: release management è trasversale. Richiede semver-bump e
    changelog-entry (entrambe riclassificate BASE).
- `Agent-Validate.md` — dispatcher test/lint/validate — **BORDERLINE → BASE**
  - Ragionamento: dispatcher puro, delega a capabilities plugin. Nessun
    coupling a linguaggi specifici nel file.
- `Agent-Design.md` — dispatcher architettura software — **CORE-CRAFT**
- `Agent-CodeRouter.md` — dispatcher routing code — **CORE-CRAFT**
- `Agent-CodeUI.md` — dispatcher UI/accessibilità code — **CORE-CRAFT**

### Instruction (7 totali)

- `framework-guard.instructions.md` — protezione file `.github/` — **BASE**
- `model-policy.instructions.md` — regole operative modello — **BASE**
- `personality.instructions.md` — postura comunicativa — **BASE**
- `verbosity.instructions.md` — livelli di verbosità — **BASE**
- `workflow-standard.instructions.md` — sequenza workflow 7 fasi — **BASE**
- `git-policy.instructions.md` — policy git + Conventional Commits — **BORDERLINE → BASE**
  - Ragionamento: Conventional Commits è uno standard applicabile a qualsiasi
    progetto, non solo coding.
- `mcp-context.instructions.md` — specifico runtime FastMCP — **CORE-CRAFT**

### Skill (26 totali)

General-purpose confermato (**BASE** — 22 file):
- `accessibility-output.skill.md`
- `agent-selector.skill.md`
- `document-template.skill.md`
- `error-recovery/SKILL.md` + `reference/errors-git.md`
- `file-deletion-guard.skill.md`
- `framework-guard.skill.md`
- `framework-index/SKILL.md`
- `framework-query/SKILL.md` + `reference/mcp-tool-index.md`
- `framework-scope-guard.skill.md`
- `personality.skill.md`
- `project-doc-bootstrap/SKILL.md` + `templates/doc-structure.md`
- `project-profile.skill.md`
- `project-reset.skill.md`
- `semantic-gate.skill.md`
- `style-setup.skill.md`
- `task-scope-guard.skill.md`
- `validate-accessibility/SKILL.md` + `checklists/nvda-checklist.md` + `checklists/keyboard-nav-checklist.md`
- `verbosity.skill.md`

Riclassificato da coding → **BASE** (6 file):
- `conventional-commit.skill.md` — usata da Agent-Git (BASE)
- `git-execution.skill.md` — usata da Agent-Git (BASE)
- `rollback-procedure.skill.md` — usata da Agent-Release e Agent-Git (entrambi BASE)
- `semver-bump.skill.md` — usata da Agent-Release (BASE)
- `changelog-entry/SKILL.md` + `templates/entry-template.md` — usata da Agent-Release (BASE)

**CORE-CRAFT** (5 file):
- `clean-architecture/SKILL.md` + `templates/project-structure.md` — design software
- `code-routing.skill.md` — routing agenti coding
- `docs-manager/SKILL.md` + `templates/readme-template.md` + `templates/adr-template.md` — template ADR/README coding-oriented

### Prompt (18 totali + README)

Tutti classificati **BASE** — nessun prompt contiene logica coding-specific.
I 18 prompt + README.md migrano integralmente a spark-base.

### File infrastrutturali

- `.github/AGENTS.md` — **BASE** (con riscrittura: lista soli agenti base)
- `.github/copilot-instructions.md` — **BASE** (con edit: rimuovere riferimenti plugin-specific)
- `.github/project-profile.md` — **BASE** (verifica contenuto prima di migrare)
- `.github/changelogs/scf-master-codecrafter.md` — **CORE-CRAFT** (resta nel pacchetto originale)
- `.github/runtime/` — **non tracciata nel manifest attuale**
  - Verifica eseguita su `package-manifest.json`: nessun path sotto `.github/runtime/`
    compare nella lista `files`. Non entra quindi né in VERDE né in ROSSA e
    non partecipa alla migrazione di ownership.

---

## ANALISI DIPENDENZE

### D1 — Dipendenze dichiarate (cross-reference interne)

Nessun file candidato BASE contiene campi espliciti `requires:`, `uses:` o
`depends_on:` nel frontmatter. Le dipendenze sono solo testuali:

- `file-deletion-guard.skill.md` referenzia `framework-guard` → entrambi migrano
  insieme a spark-base ✅
- `agent-selector.skill.md` referenzia Agent-Welcome, Agent-Orchestrator,
  Agent-Git, Agent-FrameworkDocs, Agent-Research → tutti migrano insieme ✅
- `git-commit.prompt.md` e `git-merge.prompt.md` referenziano Agent-Git +
  `git-policy.instructions.md` + `git-execution.skill.md` → tutti migrano ✅

**Risultato**: nessuna dipendenza spezzata dalla migrazione.

### D2 — Dipendenze inverse (CORE-CRAFT → BASE)

- `Agent-Design.md` (CORE-CRAFT) usa skill di spark-base (semantic-gate,
  framework-query) via capability dinamica → funziona cross-package ✅
- `Agent-CodeRouter.md` (CORE-CRAFT) usa `code-routing.skill.md` (CORE-CRAFT)
  + `.github/project-profile.md` (BASE) → project-profile disponibile via
  spark-base come dependency ✅
- `mcp-context.instructions.md` (CORE-CRAFT) non referenzia componenti BASE.

La relazione diventa: `master-codecrafter.dependencies = ["spark-base"]`.
Nessuna dipendenza circolare. Catena lineare:
`spark-base → master-codecrafter(ridotto) → pycode-crafter`.

### D3 — Impatto sul ManifestManager

**Il sistema NON supporta trasferimento di ownership**. Dettaglio:

- `ManifestManager` traccia entries `{file, package, package_version, sha256}`.
- `get_file_owners(file_rel)` ritorna la lista di package proprietari.
- `scf_install_package` con policy `"error"` (default) BLOCCA se un file è
  già owned da un altro pacchetto (classificazione `conflict_cross_owner`).
- Non esiste `transfer_ownership()`, `change_owner()`, né nessun `conflict_mode`
  che permetta il trasferimento.
- Le uniche eccezioni sono `extend_section` e `delegate_skip`.

**Cosa succede se un file è owned da master-codecrafter e si installa spark-base?**
→ `conflict_cross_owner` → installazione bloccata.

**Strategia obbligatoria**: remove master v1.0.0 → install spark-base → install
master v2.0.0 (ridotto). Sequenza atomica in una sessione.

**Serve `scf_transfer_ownership`?**
No per questa migrazione one-shot su utente unico. La modifica manuale del
manifest JSON è più rapida e ugualmente sicura (il file è un JSON di ~2KB,
verificabile con `scf_verify_workspace`). Un tool dedicato avrebbe senso solo
se il caso si ripresentasse con frequenza.

### D4 — Sentinella bootstrap

Il bootstrap (`scf_bootstrap_workspace`) installa:
- `prompts/scf-*.prompt.md`
- `agents/spark-assistant.agent.md`
- `agents/spark-guide.agent.md`
- `instructions/spark-assistant-guide.instructions.md`

Tutti registrati con owner `scf-engine-bootstrap`. **Nessuna sovrapposizione**
con i file candidati alla migrazione. I prompt di spark-base hanno path diversi
dai prompt bootstrap (`framework-*.prompt.md` vs `scf-*.prompt.md`).

**Conclusione**: il bootstrap non va modificato. spark-base è un pacchetto
installabile separatamente, non parte del bootstrap engine.

### D5 — Impatto su scf-pycode-crafter

- pycode-crafter dichiara `dependencies: ["scf-master-codecrafter"]`.
- master-codecrafter v2.0.0 dichiarerà `dependencies: ["spark-base"]`.
- La catena di installazione diventa:
  `spark-base` → `master-codecrafter@2.0.0` → `pycode-crafter@2.0.0`.
- pycode-crafter **non va modificato**: la sua dipendenza diretta resta
  `scf-master-codecrafter`, che a sua volta richiede `spark-base`.

**Dato verificato dal codice**: la dependency check dell'engine è **flat,
non transitiva**. In `scf_install_package`, `missing_dependencies` è calcolato
come differenza diretta tra `pkg_manifest["dependencies"]` e
`manifest.get_installed_versions()`, senza ricorsione sulle dipendenze delle
dipendenze. Lo stesso schema è riusato nel planner update. Se un utente
installa solo `scf-pycode-crafter` senza spark-base, riceve prima errore
`missing: scf-master-codecrafter`; il requisito `spark-base` emerge al passo
successivo quando si installa `scf-master-codecrafter`.

---

## LISTA VERDE — Spostamento immediato, zero rischio

55 file. Zero modifiche al contenuto. Path identici nel pacchetto destinazione.

**Agenti (8)**:
1. `.github/agents/Agent-Analyze.md`
2. `.github/agents/Agent-Plan.md`
3. `.github/agents/Agent-Docs.md`
4. `.github/agents/Agent-Helper.md`
5. `.github/agents/Agent-Research.md`
6. `.github/agents/Agent-Welcome.md`
7. `.github/agents/Agent-FrameworkDocs.md`
8. `.github/agents/Agent-Git.md`

**Instruction (5)**:
9. `.github/instructions/framework-guard.instructions.md`
10. `.github/instructions/model-policy.instructions.md`
11. `.github/instructions/personality.instructions.md`
12. `.github/instructions/verbosity.instructions.md`
13. `.github/instructions/workflow-standard.instructions.md`

**Skill GP (22 file)**:
14. `.github/skills/accessibility-output.skill.md`
15. `.github/skills/agent-selector.skill.md`
16. `.github/skills/document-template.skill.md`
17. `.github/skills/error-recovery/SKILL.md`
18. `.github/skills/error-recovery/reference/errors-git.md`
19. `.github/skills/file-deletion-guard.skill.md`
20. `.github/skills/framework-guard.skill.md`
21. `.github/skills/framework-index/SKILL.md`
22. `.github/skills/framework-query/SKILL.md`
23. `.github/skills/framework-query/reference/mcp-tool-index.md`
24. `.github/skills/framework-scope-guard.skill.md`
25. `.github/skills/personality.skill.md`
26. `.github/skills/project-doc-bootstrap/SKILL.md`
27. `.github/skills/project-doc-bootstrap/templates/doc-structure.md`
28. `.github/skills/project-profile.skill.md`
29. `.github/skills/project-reset.skill.md`
30. `.github/skills/semantic-gate.skill.md`
31. `.github/skills/style-setup.skill.md`
32. `.github/skills/task-scope-guard.skill.md`
33. `.github/skills/validate-accessibility/SKILL.md`
34. `.github/skills/validate-accessibility/checklists/nvda-checklist.md`
35. `.github/skills/validate-accessibility/checklists/keyboard-nav-checklist.md`
36. `.github/skills/verbosity.skill.md`

**Prompt (19 file)**:
37–55. Tutti i 18 `.prompt.md` + `README.md` in `.github/prompts/`

---

## LISTA GIALLA — Spostamento dopo intervento minore

14 file totali. Di questi, 3 richiedono edit al contenuto.

- **G1** `.github/agents/Agent-Orchestrator.md`
  - Intervento: audit per assenza di path hardcoded a skill CORE-CRAFT.
    Nessuna modifica prevista al contenuto; le skill sono risolte via capability.

- **G2** `.github/agents/Agent-Release.md`
  - Intervento: nessuna modifica. Deve migrare insieme a semver-bump e
    changelog-entry (G8, G9).

- **G3** `.github/agents/Agent-Validate.md`
  - Intervento: nessuna modifica. Dispatcher puro via capabilities.

- **G4** `.github/instructions/git-policy.instructions.md`
  - Intervento: nessuna modifica. Riclassificazione da BORDERLINE a BASE.

- **G5** `.github/skills/git-execution.skill.md`
  - Intervento: riclassificazione. Agent-Git (BASE) la usa come skill primaria.

- **G6** `.github/skills/conventional-commit.skill.md`
  - Intervento: riclassificazione. Agent-Git e Agent-Release la usano.

- **G7** `.github/skills/rollback-procedure.skill.md`
  - Intervento: riclassificazione. Agent-Release e Agent-Git la usano.

- **G8** `.github/skills/semver-bump.skill.md`
  - Intervento: riclassificazione. Agent-Release la richiede.

- **G9** `.github/skills/changelog-entry/SKILL.md` + `templates/entry-template.md`
  - Intervento: riclassificazione. Agent-Release la richiede. (2 file)

- **G10** `.github/AGENTS.md` — **richiede riscrittura**
  - Intervento: spark-base installa AGENTS.md con lista dei soli 11 agenti base.
    master-codecrafter v2.0.0 crea nuovo `.github/AGENTS-master.md` con i
    3 agenti CORE-CRAFT. Il motore risolve `scf://agents-index` via pattern
    `AGENTS*.md` (meccanismo già operativo con `AGENTS-python.md`).

- **G11** `.github/copilot-instructions.md` — **richiede edit**
  - Intervento: cambiare descrizione da "layer master" a "layer fondazionale".
    Rimuovere riferimenti a `python.instructions.md`, `tests.instructions.md`,
    `mcp-context.instructions.md` (specifici di plugin).

- **G12** `.github/project-profile.md` — **verifica + eventuale edit**
  - Intervento: leggere il contenuto. Se contiene riferimenti espliciti a
    `scf-master-codecrafter`, sostituire con `spark-base`. Altrimenti: zero
    modifiche (è già un template generico).
  - **Nota conteggio**: se G12 non migra, il totale file spark-base scende da 69 a 68.

---

## LISTA ROSSA — NON spostare

11 file. Restano in scf-master-codecrafter v2.0.0 (ridotto).

- **R1** `.github/agents/Agent-Design.md` — CORE-CRAFT.
  Dispatcher architetturale che delega a capabilities `[design]` di plugin
  linguaggio-specifici. Senza plugin coding installato non ha contesto operativo.

- **R2** `.github/agents/Agent-CodeRouter.md` — CORE-CRAFT.
  Classifica task in `code/code-ui/routing`. Nessun utilizzo in workspace
  non-coding.

- **R3** `.github/agents/Agent-CodeUI.md` — CORE-CRAFT.
  Dispatcher per capabilities `[code-ui, ui]`. Specifico interfacce/coding.

- **R4** `.github/instructions/mcp-context.instructions.md` — CORE-CRAFT.
  Regole su `stdout/stderr`, `@mcp.tool()`, `mcp.run()`. Applicabile solo
  in contesto sviluppo MCP.

- **R5** `.github/skills/clean-architecture/SKILL.md` +
  `templates/project-structure.md` — CORE-CRAFT.
  Design architetturale software. Usata da Agent-Design.

- **R6** `.github/skills/code-routing.skill.md` — CORE-CRAFT.
  Routing tra agenti coding. Usata da Agent-CodeRouter.

- **R7** `.github/skills/docs-manager/SKILL.md` + `templates/readme-template.md`
  + `templates/adr-template.md` — CORE-CRAFT.
  Template ADR e README coding-oriented. Pattern software.

- **R8** `.github/changelogs/scf-master-codecrafter.md` —
  Changelog package-specifico. Non migrabile: appartiene alla storia di
  scf-master-codecrafter.

---

## PIANO IMPLEMENTATIVO

### Prerequisiti engine

**Un prerequisito engine aggiuntivo è raccomandato prima dell'implementazione.**

- Non serve `scf_transfer_ownership` (migrazione one-shot, utente unico).
- Il sistema `AGENTS*.md` multi-file è già operativo.
- `min_engine_version: 1.9.0` è già soddisfatto.
- `scf_preview_install` **non esiste** nel motore attuale.
  Prima di procedere all'implementazione è consigliato aggiungere un tool di
  dry-run del manifest (`scf_preview_install` o equivalente) che validi:
  manifest raggiungibile, dipendenze dichiarate, conflitti ownership attesi e
  write plan senza scrivere nel workspace.

### Step 0 — Preflight obbligatorio workspace

0.0. Esegui `scf_verify_workspace`.
  - Esito richiesto: `is_clean: true`
  - Esito richiesto: `modified: []`
  - Se il workspace non è pulito, **il piano si blocca qui**. Nessuna rimozione,
    installazione o migrazione deve partire finché gli hash del manifest non
    tornano allineati.

### Step 1 — Creazione repository spark-base

1.1. Crea repo GitHub `Nemex81/spark-base` (pubblico, branch `main`).

1.2. Crea `package-manifest.json` con:
  - `package: "spark-base"`, `version: "1.0.0"`
  - `dependencies: []`, `min_engine_version: "1.9.0"`
  - `files`: 69 file (55 VERDE + 14 GIALLA)
  - `changelog_path: ".github/changelogs/spark-base.md"`

1.3. Popola i file:
  - Copia da master-codecrafter i 55 file VERDE (zero modifiche).
  - Copia i file GIALLA G1–G9 (zero modifiche al contenuto).
  - Crea `.github/AGENTS.md` versione spark-base (G10): lista 11 agenti base.
  - Edita `.github/copilot-instructions.md` (G11): descrizione "layer fondazionale",
    rimuovi riferimenti plugin-specific.
  - Verifica `.github/project-profile.md` (G12): modifica solo se necessario.
  - Crea `.github/changelogs/spark-base.md` con voce `[1.0.0]`.

### Step 2 — Aggiornamento scf-master-codecrafter → v2.0.0

2.1. Aggiorna `package-manifest.json`:
  - `version: "2.0.0"`
  - `dependencies: ["spark-base"]`
  - `description`: "Plugin CORE-CRAFT per master-layer SCF..."
  - `files`: ridotto a **12 file esatti**:
    - `.github/AGENTS-master.md`
    - `.github/changelogs/scf-master-codecrafter.md`
    - `.github/agents/Agent-Design.md`
    - `.github/agents/Agent-CodeRouter.md`
    - `.github/agents/Agent-CodeUI.md`
    - `.github/instructions/mcp-context.instructions.md`
    - `.github/skills/clean-architecture/SKILL.md`
    - `.github/skills/clean-architecture/templates/project-structure.md`
    - `.github/skills/code-routing.skill.md`
    - `.github/skills/docs-manager/SKILL.md`
    - `.github/skills/docs-manager/templates/readme-template.md`
    - `.github/skills/docs-manager/templates/adr-template.md`
  - Rimuovi tutti i 57 file migrati a spark-base

2.2. Crea `.github/AGENTS-master.md` — lista 3 agenti CORE-CRAFT.

2.3. Aggiorna changelog con voce `[2.0.0]`.

2.4. SemVer bump previsto:

| Pacchetto | Prima | Dopo | Bump | Motivazione |
|-----------|-------|------|------|-------------|
| spark-base | — | 1.0.0 | NEW | Nuovo pacchetto |
| scf-master-codecrafter | 1.0.0 | 2.0.0 | MAJOR | Perde 50+ file, nuova dependency |
| scf-pycode-crafter | 2.0.0 | 2.0.0 | nessuno | Nessuna modifica |

### Step 3 — Dry-run manifest spark-base

3.1. Valida `package-manifest.json` di spark-base prima del deploy.
  - Se esiste `scf_preview_install`, usarlo per verificare manifest,
    dipendenze, conflitti ownership e write plan.
  - Stato reale del motore: `scf_preview_install` **non esiste** oggi.
  - Questo step è raccomandato prima del deploy ma non bloccante: la migrazione
    può procedere con `scf_verify_workspace` come precheck sufficiente.

### Step 4 — Aggiornamento registry

4.1. Aggiungi entry `spark-base` a `registry.json`:
  - `id: "spark-base"`, `latest_version: "1.0.0"`, `status: "stable"`
  - `repo_url: "https://github.com/Nemex81/spark-base"`

4.2. Aggiorna entry `scf-master-codecrafter`:
  - `latest_version: "2.0.0"`
  - descrizione e tag aggiornati

### Step 5 — Migrazione workspace utente

> ⚠ Operazione con side-effect. Eseguire in sessione singola.

5.1. Backup: `git status` + `scf_verify_workspace`. Salva file `modified`.

5.2. `scf_remove_package("scf-master-codecrafter")` — rimuove 62+ file tracciati.

5.3. `scf_install_package("spark-base")` — installa 69 file base.

5.4. `scf_install_package("scf-master-codecrafter")` — installa 12 file CORE-CRAFT.
     Il motore verifica la dipendenza `spark-base` → già presente ✅

5.5. `scf_verify_workspace` — verifica `is_clean: true`.

### Step 6 — Gate di verifica post-migrazione

- V1: `scf_list_installed_packages` → 3 pacchetti con versioni corrette
- V2: `scf_verify_workspace` → `is_clean: true`, `modified: []`
- V3: Tutti e 14 gli agenti master + 5 agenti python presenti
- V4: Tutte le 26+ skill originali presenti (nessuna assente)
- V5: 7 instruction: 6 da spark-base + 1 da master-codecrafter
- V6: 18 prompt da spark-base
- V7: `Agent-Design` risolto da master-codecrafter ✅
- V8: `Agent-Git` risolto da spark-base ✅
- V9: `clean-architecture` risolta da master-codecrafter ✅
- V10: `semver-bump` risolta da spark-base ✅

---

## RISCHI RESIDUI

### R-HIGH — Broken window durante la migrazione workspace

- **Cosa**: tra `scf_remove_package` e `scf_install_package("spark-base")` il
  workspace è senza AGENTS.md, copilot-instructions.md e tutti gli agenti.
- **Probabilità**: certa (è la meccanica del remove+install)
- **Durata**: realistica **10-30 secondi** su rete lenta, perché include fetch
  remoto del manifest e dei file durante `scf_install_package`, non solo le
  scritture locali.
- **Mitigazione**: eseguire la sequenza step 5.2–5.4 in sessione singola senza
  interruzioni. **Non eseguire la migrazione con Copilot agent mode aperto**
  durante la transizione.

### R-MEDIUM — Dependency check flat (non transitiva)

- **Cosa**: il motore verifica solo le dipendenze dirette, non transitive.
  Se un utente installa `scf-pycode-crafter` senza `spark-base`, riceve
  `missing: scf-master-codecrafter` (corretto) ma non `missing: spark-base`.
  Quando poi installa master-codecrafter, riceve `missing: spark-base`.
- **Probabilità**: bassa (utente unico che conosce la catena)
- **Mitigazione**: documentare l'ordine di installazione nel README di ogni
  pacchetto. Il motore non richiede modifica per questo caso perché il
  comportamento flat è coerente e verificato nel codice attuale.

### R-LOW — File user-modified durante il remove

- **Cosa**: `scf_remove_package` preserva file con modifiche utente (hash
  mismatch). Questi restano su disco come "untracked". Il successivo
  `scf_install_package("spark-base")` li classifica come
  `conflict_untracked_existing` → blocca con default policy `"error"`.
- **Probabilità**: bassa (workspace appena verificato, file non modificati)
- **Mitigazione**: eseguire `scf_verify_workspace` prima del remove. Se
  `modified` non è vuoto, risolvere prima della migrazione. In alternativa,
  usare `conflict_mode="replace"` nell'installazione spark-base.

### R-LOW — Agent-Orchestrator cross-package skill resolution

- **Cosa**: Agent-Orchestrator (spark-base) referenzia per nome 20+ skill.
  Dopo la migrazione, alcune skill sono in spark-base e altre in
  master-codecrafter. Il motore risolve le skill per nome, non per package.
- **Probabilità**: nulla se il motore cerca skill in tutti i pacchetti installati.
- **Mitigazione**: verificare con `scf_get_skill("clean-architecture")` che la
  risoluzione cross-package funzioni correttamente nel gate V9.

### R-INFO — scf-pycode-crafter `errors-python.md` coesistenza

- **Cosa**: pycode-crafter installa
  `.github/skills/error-recovery/reference/errors-python.md`. spark-base
  installa `.github/skills/error-recovery/reference/errors-git.md`. I due
  file hanno path diversi nello stesso sotto-albero.
- **Probabilità**: nulla (path distinti, nessun conflitto ownership)
- **Mitigazione**: nessuna.

---

## CONTEGGI FINALI

| Metrica | Valore |
|---------|--------|
| File totali in spark-base | 69 |
| File ROSSA che restano in master-codecrafter | 11 |
| File totali in master-codecrafter v2.0.0 | 12 |
| File invariati in pycode-crafter | 12 |
| File che richiedono edit al contenuto | 3 (AGENTS.md, copilot-instructions.md, project-profile.md) |

> **Nota**: il conteggio 69 file spark-base è valido solo se G12 (`project-profile.md`)
> migra (con o senza edit). Se G12 non migra, il totale diventa 68.
| Nuovi file da creare | 2 (AGENTS-master.md, changelogs/spark-base.md) |
| Modifiche al motore engine | 1 prerequisito consigliato (`scf_preview_install` o equivalente) |
| Tool MCP nuovi richiesti | 1 prerequisito consigliato (`scf_preview_install` o equivalente) |
| Gate di verifica post-migrazione | 10 |
