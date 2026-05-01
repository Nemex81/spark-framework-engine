# Piano Implementativo — spark-base

- **Data**: 15 aprile 2026
- **Autore**: Agent-Analyze (analisi ecosistema completa)
- **Scope**: Creare `spark-base`, ridurre `scf-master-codecrafter` a v2.0.0 CORE-CRAFT,
  migrare il workspace utente.
- **Prerequisito soddisfatto**: engine v2.0.0, `scf_plan_install` in produzione da v1.9.0.
- **File di analisi originale**: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md)

---

## VALIDAZIONE STRATEGIA — Esito

Tre condizioni di pre-validazione verificate:

| # | Condizione | Esito |
|---|-----------|-------|
| C1 | `scf_preview_install` assente → usare `scf_plan_install` | ✅ `scf_plan_install` presente da v1.9.0. Non richiede modifiche engine. |
| C2 | G12 (`project-profile.md`) potrebbe richiedere edit se referenzia `scf-master-codecrafter` | ✅ File è template puro (`initialized: false`, `active_plugins: []`). Zero modifiche al contenuto. Migra a spark-base invariato. |
| C3 | Non avviare migrazione workspace (Step 5) finché `scf_bootstrap_workspace` non è implementato e i relativi test non passano | ✅ Implementato a riga 3606. 5 test completi in `test_bootstrap_workspace.py`. |

**Verdetto: PASS — Procedere con implementazione.**

---

## NUMERI CHIAVE

| Elemento | Stato attuale | Dopo migrazione |
|----------|--------------|-----------------|
| `scf-master-codecrafter` versione | 1.0.0 | 2.0.0 |
| `scf-master-codecrafter` file in manifest | 60 | 12 |
| `spark-base` versione | — (non esiste) | 1.0.0 |
| `spark-base` file stimati | — | ~69 (*) |
| `scf-pycode-crafter` | 2.0.0 / 12 file | invariato |
| `scf-registry` schema | 2.0, 2 pacchetti | 2.0, 3 pacchetti |

(*) 60 manifest-tracked da master (−11 ROSSA) = 49 + ~19 prompt (attualmente non in manifest,
saranno tracciati per la prima volta da spark-base) ≈ 68–69. Conteggio esatto verificabile al
Step 3 con `scf_plan_install`.

**Catena dipendenze post-migrazione**:
```
spark-base@1.0.0 → scf-master-codecrafter@2.0.0 → scf-pycode-crafter@2.0.0
```

**Dipendenze flat (non transitive)** — comportamento engine verificato nel codice. Un utente
che installa `scf-pycode-crafter` senza `spark-base` riceve errore
`missing: scf-master-codecrafter`; il requisito `spark-base` emerge al passo successivo.

---

## CLASSIFICAZIONE FILE

### Lista Rossa — Restano in master v2.0.0 (11 file attuali + 1 nuovo)

File che restano in `scf-master-codecrafter`:

| File | Categoria |
|------|-----------|
| `agents/Agent-Design.md` | CORE-CRAFT |
| `agents/Agent-CodeRouter.md` | CORE-CRAFT |
| `agents/Agent-CodeUI.md` | CORE-CRAFT |
| `instructions/mcp-context.instructions.md` | CORE-CRAFT |
| `skills/clean-architecture/SKILL.md` | CORE-CRAFT |
| `skills/clean-architecture/templates/project-structure.md` | CORE-CRAFT |
| `skills/code-routing.skill.md` | CORE-CRAFT |
| `skills/docs-manager/SKILL.md` | CORE-CRAFT |
| `skills/docs-manager/templates/readme-template.md` | CORE-CRAFT |
| `skills/docs-manager/templates/adr-template.md` | CORE-CRAFT |
| `changelogs/scf-master-codecrafter.md` | changelog pacchetto |
| `AGENTS-master.md` | **NUOVO** — aggiunto in v2.0.0 |

### Lista Verde e Gialla → spark-base (vedere ANALISI per dettaglio completo)

Tutti gli altri file (agenti base, instruction base, skill GP, prompt, AGENTS.md,
copilot-instructions.md, project-profile.md) migrano a spark-base.

Interventi richiesti su GIALLA:
- **G10** `AGENTS.md`: riscrivere per elencare solo i 11 agenti base di spark-base.
- **G11** `copilot-instructions.md`: cambiare descrizione da "layer master" a "layer fondazionale";
  rimuovere riferimenti a instruction plugin-specific.
- **G12** `project-profile.md`: zero modifiche al contenuto (template generico invariato).

---

## PIANO OPERATIVO

### Step 0 — Preflight workspace (non distruttivo)

`scf_verify_workspace` → richiede `is_clean: true`, `modified: []`.
Se il workspace non è pulito: **blocco totale**. Risolvere mismatch prima di procedere.

**File di lavoro**: [todo-fase-SB-0-preflight.md](todolist/todo-fase-SB-0-preflight.md)

---

### Step 1 — Creazione repository spark-base

1.1. Crea repo GitHub `Nemex81/spark-base` (pubblico, branch `main`).

1.2. Crea `package-manifest.json` con:
- `package: "spark-base"`, `version: "1.0.0"`
- `dependencies: []`, `min_engine_version: "1.9.0"`
- `files`: lista ~69 file (55 VERDE + 14 GIALLA, inclusi prompt)
- `file_ownership_policy: "error"`
- `changelog_path: ".github/changelogs/spark-base.md"`

1.3. Popola i file:
- 55 file VERDE: copia da master senza modifiche
- G1-G9 GIALLA skills/agents/instructions: copia da master senza modifiche
- G10 `AGENTS.md`: nuova versione con lista 11 agenti base
- G11 `copilot-instructions.md`: edit descrizione + rimozione riferimenti plugin
- G12 `project-profile.md`: copia da master invariato
- `.github/changelogs/spark-base.md`: voce `[1.0.0]` iniziale

**File di lavoro**: [todo-fase-SB-1-repo.md](todolist/todo-fase-SB-1-repo.md)

---

### Step 2 — Riduzione scf-master-codecrafter → v2.0.0

2.1. Aggiorna `package-manifest.json`:
- `version: "2.0.0"`
- `dependencies: ["spark-base"]`
- `description`: "Plugin CORE-CRAFT per master-layer SCF — agenti design, routing, mcp-context"
- `files`: ridotto a 12 file esatti (vedi Lista Rossa sopra)

2.2. Crea `.github/AGENTS-master.md` con lista 3 agenti CORE-CRAFT:
```
Agent-Design, Agent-CodeRouter, Agent-CodeUI
```

2.3. Aggiorna `.github/changelogs/scf-master-codecrafter.md` con voce `[2.0.0]`.

2.4. SemVer previsto:

| Pacchetto | Prima | Dopo | Bump | Motivazione |
|-----------|-------|------|------|-------------|
| spark-base | — | 1.0.0 | NEW | Nuovo pacchetto |
| scf-master-codecrafter | 1.0.0 | 2.0.0 | MAJOR | Perde 48+ file, nuova dependency |
| scf-pycode-crafter | 2.0.0 | 2.0.0 | — | Invariato |

**File di lavoro**: [todo-fase-SB-2-master-v2.md](todolist/todo-fase-SB-2-master-v2.md)

---

### Step 3 — Dry-run manifest spark-base con `scf_plan_install`

3.1. Aggiorna `registry.json` in staging con entry spark-base temporanea (o testa offline).

3.2. Esegui `scf_plan_install("spark-base")`:
- Verifica `can_install: true`
- Verifica `conflict_plan: []` — se ci sono `conflict_untracked_existing`, annotare i file
  e aggiungere `conflict_mode="replace"` alla chiamata `scf_install_package` in Step 5
- Verifica `write_plan` corrisponde ai file attesi

3.3. Se `dependency_issues` non è vuoto: risolvere prima di procedere.

> **Nota**: questo step è raccomandato, non bloccante. **SB-4 deve precedere SB-3**: senza
> l'entry registry di spark-base, `scf_plan_install` non riesce a localizzare il manifest
> remoto e restituisce errore.

**File di lavoro**: [todo-fase-SB-3-dry-run.md](todolist/todo-fase-SB-3-dry-run.md)

---

### Step 4 — Aggiornamento registry

4.1. Modifica `scf-registry/registry.json`:
- Aggiungi entry spark-base:
  ```json
  {
    "id": "spark-base",
    "display_name": "SPARK Base Layer",
    "description": "Layer fondazionale del framework SCF...",
    "repo_url": "https://github.com/Nemex81/spark-base",
    "latest_version": "1.0.0",
    "min_engine_version": "1.9.0",
    "status": "stable",
    "tags": ["base", "foundation", "agents", "skills", "prompts"]
  }
  ```
- Aggiorna entry `scf-master-codecrafter`:
  - `latest_version: "2.0.0"`
  - Aggiorna `description` e `tags`

4.2. Verifica che `scf_list_available_packages` restituisca i 3 pacchetti corretti.

**File di lavoro**: [todo-fase-SB-4-registry.md](todolist/todo-fase-SB-4-registry.md)

---

### Step 5 — Migrazione workspace utente

> ⚠ Operazione con side-effect. Eseguire l'intera sequenza 5.1–5.5 in sessione singola.
> Non aprire Agent mode Copilot durante la transizione.

5.1. **Backup pre-migrazione**:
- `git status` — nessun file non committed
- `scf_verify_workspace` → must be `is_clean: true`

5.2. `scf_remove_package("scf-master-codecrafter")`:
- Rimuove 60 file tracciati
- I prompt non tracciati restano su disco (non toccati)
- Rischio: file user-modified → preservati con avviso

5.3. `scf_install_package("spark-base")` (usare `conflict_mode="replace"` se step 3 ha rilevato file untracked nei path target):
- Installa ~69 file base
- Traccia i prompt per la prima volta nel manifest
- Verifica output: `installed` count = atteso, `conflicts_detected: []`

5.4. `scf_install_package("scf-master-codecrafter")`:
- `dependencies: ["spark-base"]` → già installata ✅
- Installa 12 file CORE-CRAFT
- Crea `AGENTS-master.md`

5.5. `scf_verify_workspace` → `is_clean: true`.

**Finestra di broken window attesa**: ~10–30 secondi tra 5.2 e 5.4.

**File di lavoro**: [todo-fase-SB-5-migrazione.md](todolist/todo-fase-SB-5-migrazione.md)

---

### Step 6 — Gate di verifica post-migrazione

Tutti i check devono passare prima di chiudere il piano:

| Gate | Check | Atteso |
|------|-------|--------|
| V1 | `scf_list_installed_packages` | 3 pacchetti: spark-base@1.0.0, scf-master-codecrafter@2.0.0, scf-pycode-crafter@2.0.0 |
| V2 | `scf_verify_workspace` | `is_clean: true`, `modified: []` |
| V3 | Agenti presenti | 11 BASE (spark-base) + 3 CORE-CRAFT (master) + 5 python (pycode) = 19 totali |
| V4 | Skill presenti | 22 GP + 6 riclassificate (BASE) + 5 CORE-CRAFT = 33 skill |
| V5 | Instruction presenti | 6 da spark-base + 1 mcp-context da master + 1 python + 1 tests = 9 |
| V6 | Prompt presenti | 18 framework prompt da spark-base |
| V7 | `Agent-Design` risolto | ✅ da master-codecrafter |
| V8 | `Agent-Git` risolto | ✅ da spark-base |
| V9 | `clean-architecture` skill presente | ✅ da master-codecrafter |
| V10 | `semver-bump` skill presente | ✅ da spark-base |
| V11 | `AGENTS-master.md` presente | ✅ da master v2.0.0 |
| V12 | `scf://agents-index` restituisce tutti gli AGENTS*.md | ✅ pattern multi-file già operativo |

**File di lavoro**: [todo-fase-SB-6-gate.md](todolist/todo-fase-SB-6-gate.md)

---

## RISCHI RESIDUI

### R-HIGH — Broken window 10–30 secondi (Step 5.2–5.4)

Workspace privo di AGENTS.md e agenti tra remove e install. Mitigazione: eseguire senza interruzioni.

### R-MEDIUM — File untracked nei path target di spark-base

I prompt in `.github/prompts/*.prompt.md` non sono tracciati nel manifest master. Dopo
`scf_remove_package`, restano su disco. `scf_install_package("spark-base")` li vede come
`conflict_untracked_existing`. Mitigazione: il dry-run al Step 3 rileva questo prima. Usare
`conflict_mode="replace"` se necessario.

### R-LOW — File user-modified durante il remove

Se `scf_verify_workspace` è `is_clean: true` al momento del remove, questo non accade.

---

## ORDINE ESECUZIONE E DIPENDENZE

```
SB-0 (preflight)
  ├─> SB-1 (crea repo spark-base)    ┐
  └─> SB-2 (aggiorna master v2.0.0)  ├─ paralleli
                                      ┘
                                        └─> SB-4 (aggiorna registry, richiede SB-1 + SB-2)
                                              └─> SB-3 (dry-run, richiede SB-4)
                                                    └─> SB-5 (migrazione workspace)
                                                          └─> SB-6 (gate verifica)
```

SB-1 e SB-2 sono parallelizzabili (operazioni su repo diversi).
**SB-4 deve precedere SB-3** in modo fisso: `scf_plan_install` richiede che l'entry
registry di spark-base esista per localizzare il manifest remoto.
