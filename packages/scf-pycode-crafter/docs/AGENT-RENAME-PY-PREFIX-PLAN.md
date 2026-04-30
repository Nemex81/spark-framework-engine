# SCF — Piano Implementativo: Rinomina Agenti con Prefisso `py-`

> ✅ **COMPLETATO** — Implementato il 2026-04-01 — commit `c3125c4` su `scf-pycode-crafter/main`

**Data redazione:** 2026-04-01
**Stato:** ✅ completato
**Versione documento:** 1.0
**Repository target:** `scf-pycode-crafter`
**Tipo modifica:** refactor — breaking change nei nomi pubblici degli agenti

---

## Contesto e motivazione

I nomi degli agenti attuali (`Agent-Code`, `Agent-Plan`, `Agent-Validate`, ecc.) sono generici.
In un ecosistema SCF multi-plugin, altri pacchetti potrebbero dichiarare agenti con gli stessi nomi,
causando conflitti rilevati da `file_ownership_policy: error` nel manifest.

Il namespace `py-` segnala esplicitamente che questi agenti appartengono al plugin Python.
La convenzione è coerente con pratiche comuni negli ecosistemi di pacchetti (npm scopes, pip namespacing).

---

## Decisione sul formato

Opzioni valutate:

| Formato | Esempio | Pro | Contro |
|---|---|---|---|
| `py-Agent-Xxx` (**scelto**) | `py-Agent-Code` | Coerente con scoping kebab-case | Mix maiuscolo/minuscolo |
| `Agent-Py-Xxx` | `Agent-Py-Code` | Mantiene `Agent-` come prefisso costante | Meno immediato come namespace |

**Formato adottato: `py-Agent-Xxx`** — l'utente ha scelto esplicitamente questo formato.

---

## Analisi scope: quali repo sono coinvolti

| Repository | Riferimenti ai nomi agenti | Modifiche richieste |
|---|---|---|
| `scf-pycode-crafter` | ✅ Sì — 18 file | **SÌ** |
| `spark-framework-engine` | ❌ Nessuno | NO |
| `scf-registry` | ❌ Nessuno (solo metadati pacchetto) | NO |

**Impatto: interamente contenuto in `scf-pycode-crafter`.**

---

## Inventario completo delle modifiche

### Gruppo 1 — File agenti da rinominare + aggiornare (11 file)

Ogni file richiede: rename del file, aggiornamento del campo `name:` nel frontmatter, aggiornamento dell'heading `# Agent-Xxx`.

| File attuale | File nuovo | `name:` nuovo |
|---|---|---|
| `Agent-Analyze.md` | `py-Agent-Analyze.md` | `py-Agent-Analyze` |
| `Agent-Code.md` | `py-Agent-Code.md` | `py-Agent-Code` |
| `Agent-CodeRouter.md` | `py-Agent-CodeRouter.md` | `py-Agent-CodeRouter` |
| `Agent-Design.md` | `py-Agent-Design.md` | `py-Agent-Design` |
| `Agent-Docs.md` | `py-Agent-Docs.md` | `py-Agent-Docs` |
| `Agent-Git.md` | `py-Agent-Git.md` | `py-Agent-Git` |
| `Agent-Helper.md` | `py-Agent-Helper.md` | `py-Agent-Helper` |
| `Agent-Orchestrator.md` | `py-Agent-Orchestrator.md` | `py-Agent-Orchestrator` |
| `Agent-Plan.md` | `py-Agent-Plan.md` | `py-Agent-Plan` |
| `Agent-Release.md` | `py-Agent-Release.md` | `py-Agent-Release` |
| `Agent-Validate.md` | `py-Agent-Validate.md` | `py-Agent-Validate` |

**Nota su `py-Agent-Orchestrator.md`:** il corpo del file contiene sequenze cross-agente
(`Agent-Plan → Agent-Design → ...`) che vanno aggiornate con i nuovi nomi.

### Gruppo 2 — File con riferimenti a nomi agenti nel contenuto (6 file)

Tutti in `.github/` di `scf-pycode-crafter`. Solo aggiornamenti testuali, nessun rename.

| File | Riferimenti da aggiornare |
|---|---|
| `AGENTS.md` | Tabella indice: tutti e 11 i nomi nella colonna "Agente" |
| `skills/agent-selector.skill.md` | Intestazioni sezione (`## Pattern → Agent-Xxx`) e testo descrittivo |
| `skills/code-routing.skill.md` | Intestazioni sezione (`### Agent-Code`, `### Agent-Design`, `### Agent-Validate`) e testo |
| `skills/framework-index.skill.md` | Riga: *"Usata da Agent-Helper"* |
| `skills/validate-accessibility.skill.md` | Frontmatter `description`: *"Richiamabile da Agent-Validate e Agent-Code"* |
| `skills/accessibility-output.skill.md` | ⚠️ Solo placeholder generici `<Agent-Name>` — **nessuna modifica necessaria** |

### Gruppo 3 — Manifest pacchetto (1 file)

| File | Modifica |
|---|---|
| `package-manifest.json` | Aggiornare i 11 path nella lista `files[]` con i nuovi nomi file |

---

## Considerazioni semver

Il rename dei nomi pubblici degli agenti è una **breaking change** per qualsiasi workspace
che faccia riferimento esplicito a `Agent-Code`, `Agent-Plan`, ecc.

Poiché l'ecosistema è ancora in fase iniziale e nessun plugin esterno ha dipendenze dichiarate
da questi nomi, la modifica può essere rilasciata come **minor bump**:

- Versione attuale: `1.0.1`
- Versione post-rename: `1.1.0`

Il CHANGELOG deve documentare la breaking change con nota di migrazione.

---

## Sequenza di implementazione

L'ordine garantisce coerenza ad ogni step intermedio.

**Step 1 — Rinomina i file agente** (git mv)
```
git mv .github/agents/Agent-Analyze.md    .github/agents/py-Agent-Analyze.md
git mv .github/agents/Agent-Code.md       .github/agents/py-Agent-Code.md
git mv .github/agents/Agent-CodeRouter.md .github/agents/py-Agent-CodeRouter.md
git mv .github/agents/Agent-Design.md     .github/agents/py-Agent-Design.md
git mv .github/agents/Agent-Docs.md       .github/agents/py-Agent-Docs.md
git mv .github/agents/Agent-Git.md        .github/agents/py-Agent-Git.md
git mv .github/agents/Agent-Helper.md     .github/agents/py-Agent-Helper.md
git mv .github/agents/Agent-Orchestrator.md .github/agents/py-Agent-Orchestrator.md
git mv .github/agents/Agent-Plan.md       .github/agents/py-Agent-Plan.md
git mv .github/agents/Agent-Release.md    .github/agents/py-Agent-Release.md
git mv .github/agents/Agent-Validate.md   .github/agents/py-Agent-Validate.md
```

**Step 2 — Aggiorna frontmatter `name:` e heading nei file agente** (11 file)

Pattern di sostituzione uniforme in ogni file:
- `name: Agent-Xxx` → `name: py-Agent-Xxx`
- `# Agent-Xxx` → `# py-Agent-Xxx`
- Qualsiasi altra occorrenza di `Agent-Xxx` nel corpo → `py-Agent-Xxx`

**Step 3 — Aggiorna `AGENTS.md`**

Tutti gli 11 nomi nella colonna "Agente" della tabella.

**Step 4 — Aggiorna le skill** (4 file con modifiche reali)

- `agent-selector.skill.md`: 8 occorrenze (`→ Agent-Xxx` nelle sezioni)
- `code-routing.skill.md`: 3 occorrenze (`### Agent-Code`, `### Agent-Design`, `### Agent-Validate` + testo)
- `framework-index.skill.md`: 1 occorrenza (`Agent-Helper`)
- `validate-accessibility.skill.md`: 2 occorrenze nel frontmatter `description`

**Step 5 — Aggiorna `package-manifest.json`**

Sostituire i 11 path nella lista `files[]` e aggiornare `"version": "1.1.0"`.

**Step 6 — Aggiorna il CHANGELOG**

Aggiungere entry `## [1.1.0]` con sezione `### Breaking Changes`.

**Step 7 — Commit atomico**

```
refactor(agents): rinomina agenti con prefisso py- per namespace plugin

Tutti gli agenti passano da Agent-Xxx a py-Agent-Xxx per evitare
conflitti di nome in ecosistemi SCF multi-plugin.

File rinominati: 11 (git mv)
File aggiornati: 7 (contenuto)
Versione pacchetto: 1.0.1 → 1.1.0

BREAKING CHANGE: i nomi pubblici degli agenti sono cambiati.
Riferimenti a Agent-Code, Agent-Plan, ecc. vanno aggiornati a
py-Agent-Code, py-Agent-Plan, ecc.
```

---

## Criteri di accettazione

- [ ] Tutti i file `.github/agents/Agent-*.md` sono stati rinominati in `py-Agent-*.md`
- [ ] Il campo `name:` nel frontmatter di ciascun agente inizia con `py-`
- [ ] `AGENTS.md` riflette i nuovi nomi nella tabella indice
- [ ] `agent-selector.skill.md` instrada verso `py-Agent-Xxx` in ogni sezione
- [ ] `code-routing.skill.md` usa `py-Agent-Xxx` nelle intestazioni e nel testo
- [ ] `package-manifest.json` lista i nuovi path e versione `1.1.0`
- [ ] CHANGELOG aggiornato con entry `1.1.0` e nota BREAKING CHANGE
- [ ] Nessun file contiene ancora riferimenti `Agent-Xxx` (senza prefisso `py-`)
  — verifica: `grep -r "Agent-" .github/ --include="*.md"` deve tornare solo nomi `py-Agent-*`
- [ ] `package-manifest.json` versione aggiornata a `1.1.0`

---

## Note per l'implementatore

- Usa `git mv` (non semplice rename) per preservare la storia git dei file agente
- Lo step di verifica finale con grep è critico: un singolo riferimento vecchio farebbe fallire
  la coerenza del pacchetto dopo l'installazione su un nuovo workspace
- Il test pratico del sistema spark va eseguito **dopo** il push di questo commit su `main`,
  poiché `notify-engine.yml` si attiva solo su push a `main` con modifiche a `package-manifest.json`

*Documento redatto il 2026-04-01 — v1.0*
