# Piano di Implementazione — scf-master-codecrafter

> **Destinatario**: Copilot in Agent mode  
> **Data**: 2026-04-10  
> **Stato**: scaffold pronto, implementazione da completare  
> **Workspace multi-root richiesto**: `scf-master-codecrafter`, `spark-framework-engine`, `scf-pycode-crafter`, `tabboz-simulator-202` (sola lettura — temporaneo)

---

## Contesto Architetturale

Questo repo è il **layer base** del SPARK Code Framework. Ogni plugin linguaggio-specifico dichiara questo package come dipendenza. Il motore MCP (`spark-framework-engine`) deve essere aggiornato alla v1.5.0 prima che questo package sia installabile (vedi Fase A).

I repo coinvolti nel workspace:
- `spark-framework-engine` — motore MCP (da patchare a v1.5.0)
- `scf-master-codecrafter` — questo repo (da popolare)
- `scf-pycode-crafter` — plugin Python (da refactorare a v2.0.0)
- `tabboz-simulator-202` — **fonte temporanea di sola lettura** (vedi sezione sotto)

---

## Workspace Multi-Root — Ruolo di Ogni Repo

| Repo | Ruolo nel workspace | Permessi |
|---|---|---|
| `spark-framework-engine` | Motore MCP — da patchare a v1.5.0 | Lettura + Scrittura |
| `scf-master-codecrafter` | Layer base SCF — da popolare | Lettura + Scrittura |
| `scf-pycode-crafter` | Plugin Python — da refactorare a v2.0.0 | Lettura + Scrittura |
| `tabboz-simulator-202` | **Fonte temporanea di sola lettura.** Presente nel workspace SOLO per estrarre i componenti del framework nella versione più evoluta. **NON scrivere, NON committare, NON modificare nulla in questo repo.** Verrà rimosso dal workspace dopo il completamento di questo piano. | Solo lettura |

### Priorità delle Fonti per la Fase B

Per ogni file da creare nel master, la fonte si sceglie in questo ordine:

1. **Fonte primaria**: il file corrispondente in `tabboz-simulator-202/.github/` — è la versione più matura e battle-tested del framework (v1.11.0, 14 agenti, iterata sul campo)
2. **Fonte secondaria**: il file corrispondente in `scf-pycode-crafter/.github/` — usare solo se il file non esiste in tabboz
3. **Da zero**: solo per `Agent-Research.md`, `framework-index/SKILL.md` e `framework-scope-guard.skill.md` — non hanno precedenti in nessun repo

---

## Esito Validazione Preliminare

**Esito complessivo:** validazione parziale, piano correggibile e implementabile.

### Discrepanze verificate nel workspace

1. `scf-master-codecrafter` non contiene ancora `.github/` né `docs/`: la Fase B va eseguita come **bootstrap completo** guidato da `package-manifest.json`, non come semplice adattamento incrementale.
2. La regola "tabboz prima, py fallback" resta valida solo a livello **file-specifico**: diverse skill in `tabboz-simulator-202` esistono solo nel formato flat legacy (`*.skill.md`), mentre il target del master richiede in più punti il formato cartella standard già presente in `scf-pycode-crafter` (`docs-manager/`, `clean-architecture/`, `error-recovery/`, `framework-query/`, `project-doc-bootstrap/`, `validate-accessibility/`, `changelog-entry/`).
3. `scf-pycode-crafter` è ancora alla versione `1.2.1` con `min_engine_version: 1.4.2`, mentre `scf-registry` pubblica ancora `engine_min_version: 1.3.0`: le Fasi C e D devono essere trattate come upgrade coordinato a `2.0.0` / `1.5.0`.
4. In `scf-pycode-crafter` vanno rimossi solo i componenti trasversali migrati al master. Restano fuori dallo scope di rimozione i file Python-specific (`python.instructions.md`, `tests.instructions.md`, `error-recovery/reference/errors-python.md`) e il workflow `.github/workflows/notify-engine.yml`.
5. La fonte canonica per l'inventario dei file del master è già disponibile in `scf-master-codecrafter/package-manifest.json`: ogni creazione della Fase B deve essere verificata contro quel manifest, non solo contro l'elenco descrittivo del piano.

### Strategia correttiva obbligatoria

- Eseguire la Fase B partendo dal `package-manifest.json` del master come checklist canonica dei file da creare.
- Selezionare la sorgente per ogni file in quest'ordine: tabboz se il file esiste in formato compatibile, pycode-crafter se il target richiede il formato cartella standard o una versione già normalizzata, creazione da zero solo per i tre file esplicitamente nuovi.
- Creare `docs/TODO.md` prima dell'implementazione e aggiornare le checklist al termine di ogni fase A, B, C, D.
- Validare ogni fase prima di procedere alla successiva; se una validazione fallisce, aggiornare prima il piano e solo dopo riprendere l'implementazione.

---

## Vincoli Invarianti

1. Tutti i file markdown SCF devono avere `spark: true` nel frontmatter YAML
2. NON modificare `ManifestManager` o il package system dell'engine
3. NON toccare `.github/runtime/` con il ManifestManager — quella directory è runtime, non manifest
4. `file_ownership_policy: "error"` su tutti i manifest — nessun merge automatico
5. Ogni agente deve avere frontmatter completo: `name`, `version`, `spark`, `layer`
6. Agenti dispatcher devono avere: `role: dispatcher`, `delegates_to_capabilities`, `fallback`
7. Agenti plugin devono avere: `plugin`, `capabilities`, `languages`
8. Output strutturato NVDA-compatibile: prefisso `ERRORE:` per errori critici, output testuale navigabile
9. NON eseguire `git push` direttamente — sempre via Agent-Git
10. NON modificare `FRAMEWORK_CHANGELOG.md` con Agent-Docs (scope esclusivo Agent-FrameworkDocs)

---

## Fase A — Patch `spark-framework-engine` → v1.5.0

**File da modificare**: `spark-framework-engine/spark-framework-engine.py`

### A1. Bump versione
```python
ENGINE_VERSION: str = "1.5.0"  # era 1.4.2
```

### A2. Nuovo metodo in `FrameworkInventory` — dopo `get_package_changelog`

```python
def list_agents_indexes(self) -> list[FrameworkFile]:
    """Scopre tutti i file AGENTS*.md in .github/ root.
    Supporta il pattern multi-plugin M1: master possiede AGENTS.md,
    ogni plugin possiede AGENTS-{plugin-id}.md.
    """
    if not self._ctx.github_root.is_dir():
        return []
    return sorted(
        [
            self._build_framework_file(p, "index")
            for p in self._ctx.github_root.glob("AGENTS*.md")
            if p.is_file()
        ],
        key=lambda ff: ff.name,
    )

def get_orchestrator_state(self) -> dict:
    """Leggi stato runtime orchestratore da .github/runtime/orchestrator-state.json.
    Restituisce stato di default se il file non esiste.
    Restituisce {} con warning se il file è corrotto.
    .github/runtime/ NON viene tracciato dal ManifestManager.
    """
    state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
    if not state_path.is_file():
        return {
            "current_phase": "",
            "current_agent": "",
            "retry_count": 0,
            "confidence": 1.0,
            "execution_mode": "autonomous",
            "last_updated": "",
            "phase_history": [],
            "active_task_id": "",
        }
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning("orchestrator-state.json unreadable: %s", exc)
        return {}

def set_orchestrator_state(self, patch: dict) -> dict:
    """Aggiorna orchestrator-state.json con merge parziale.
    Crea .github/runtime/ se non esiste.
    Aggiorna last_updated con timestamp UTC ISO-8601.
    Restituisce lo stato completo post-aggiornamento.
    """
    state_path = self._ctx.github_root / "runtime" / "orchestrator-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    current = self.get_orchestrator_state()
    current.update(patch)
    current["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    state_path.write_text(
        json.dumps(current, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return current
```

### A3. Aggiornamento resource `scf://agents-index` in `register_resources()`

Sostituire il blocco esistente della resource `scf://agents-index` con:

```python
@self._mcp.resource("scf://agents-index")
async def resource_agents_index() -> str:
    indexes = inventory.list_agents_indexes()
    if not indexes:
        return "AGENTS.md not found."
    parts = []
    for ff in indexes:
        parts.append(ff.path.read_text(encoding="utf-8", errors="replace"))
    return "\n\n---\n\n".join(parts)
```

### A4. Nuovi tool in `register_tools()` — in fondo, prima della fine del metodo

```python
@self._mcp.tool()
async def scf_get_runtime_state() -> dict:
    """Leggi lo stato runtime dell'orchestratore da .github/runtime/orchestrator-state.json.
    Restituisce stato corrente o default se il file non esiste.
    Usare prima di ogni fase autonoma per verificare execution_mode e confidence.
    """
    return inventory.get_orchestrator_state()

@self._mcp.tool()
async def scf_update_runtime_state(patch: dict) -> dict:
    """Aggiorna campi selezionati di orchestrator-state.json (merge parziale).
    Accetta solo i campi da modificare. Aggiorna last_updated automaticamente.
    Crea .github/runtime/ se non esiste.
    Esempio: {"current_phase": "CODE", "confidence": 0.92, "current_agent": "code-Agent-Code"}
    Restituisce lo stato completo post-aggiornamento.
    """
    return inventory.set_orchestrator_state(patch)
```

### A5. Nuova resource in `register_resources()` — prima del _log.info finale

```python
@self._mcp.resource("scf://runtime-state")
async def resource_runtime_state() -> str:
    """Stato runtime orchestratore come JSON formattato.
    Leggibile direttamente da Agent mode senza chiamare il tool.
    """
    state = inventory.get_orchestrator_state()
    return json.dumps(state, indent=2, ensure_ascii=False)
```

### A6. Aggiornare il log finale di `register_resources()`

```python
# da:
_log.info("Resources registered: 4 list + 4 template + 6 scf:// singletons (14 total)")
# a:
_log.info("Resources registered: 4 list + 4 template + 7 scf:// singletons (15 total)")
```

### A7. Aggiornare il docstring di `register_tools()`

```python
# da: """Register all 23 MCP tools."""
# a:  """Register all 25 MCP tools."""
```

### A8. Aggiungere entry CHANGELOG in `spark-framework-engine/CHANGELOG.md`

Nuova sezione in testa al file:

```markdown
## [1.5.0] - 2026-04-10

### Added
- `scf_get_runtime_state` tool: legge `.github/runtime/orchestrator-state.json`
- `scf_update_runtime_state` tool: merge parziale su orchestrator-state.json
- `scf://runtime-state` resource: stato runtime come JSON leggibile da Agent mode
- `FrameworkInventory.get_orchestrator_state()`: lettura con default e gestione errori
- `FrameworkInventory.set_orchestrator_state()`: scrittura con merge, mkdir, timestamp UTC
- `FrameworkInventory.list_agents_indexes()`: glob `AGENTS*.md` per pattern multi-plugin M1
- `scf://agents-index` resource aggiornata: vista aggregata di tutti i file AGENTS*.md

### Changed
- Tool count: 23 → 25
- Resource count: 14 → 15
- `scf://agents-index`: da singolo file a concatenazione di tutti AGENTS*.md presenti

### Notes
- `.github/runtime/` non viene tracciato dal ManifestManager — comportamento by design
- `min_engine_version` richiesta da scf-master-codecrafter: 1.5.0
```

---

## Fase B — Popolare `scf-master-codecrafter`

Tutti i file elencati in `package-manifest.json` devono essere creati.
Il `package-manifest.json` del master è la checklist canonica di completamento della fase.

### Mappa Fonti Tabboz → Master

Per ogni file del master, leggere prima la fonte primaria in `tabboz-simulator-202`, poi il fallback in `scf-pycode-crafter`. **Non scrivere mai nulla in `tabboz-simulator-202`.**

Correzione validata: per le skill nel formato cartella standard richieste dal manifest del master, usare come fonte primaria `scf-pycode-crafter/.github/skills/` se `tabboz-simulator-202` contiene solo la variante flat legacy.

| File da creare nel master | Fonte primaria (tabboz) | Cosa rimuovere/adattare |
|---|---|---|
| `Agent-Orchestrator.md` | agente condiviso fornito da `spark-base` | Nulla da rimuovere — già trasversale. Aggiungere frontmatter: `execution_mode`, `confidence_threshold`, `checkpoints`, `runtime_state_tool`, `runtime_update_tool`. Impostare `layer: master`, `version: 2.0.0` |
| `Agent-Git.md` | agente condiviso fornito da `spark-base` | Rimuovere riferimenti a comandi Python-specific se presenti |
| `Agent-Helper.md` | agente condiviso fornito da `spark-base` | Rimuovere riferimenti a stack Python |
| `Agent-Release.md` | agente condiviso fornito da `spark-base` | Rimuovere step Python-specific (es. `pip`, `pypi`, `wheel`) |
| `Agent-FrameworkDocs.md` | agente condiviso fornito da `spark-base` | Nulla — già trasversale |
| `Agent-Welcome.md` | agente condiviso fornito da `spark-base` | Rimuovere istruzioni setup Python-specific, generalizzare il linguaggio |
| `code-Agent-CodeRouter.md` (dispatcher) | `.github/agents/code-Agent-CodeRouter.md` | Aggiungere frontmatter `role: dispatcher`, `delegates_to_capabilities`, `fallback: Agent-Research` |
| `Agent-Analyze.md` (dispatcher) | agente condiviso fornito da `spark-base` | Aggiungere frontmatter dispatcher, rimuovere riferimenti Python-specific |
| `code-Agent-Design.md` (dispatcher) | `.github/agents/code-Agent-Design.md` | Aggiungere frontmatter dispatcher |
| `Agent-Plan.md` (dispatcher) | agente condiviso fornito da `spark-base` | Aggiungere frontmatter dispatcher |
| `Agent-Docs.md` (dispatcher) | agente condiviso fornito da `spark-base` | Aggiungere frontmatter dispatcher, rimuovere riferimenti `pytest`/`ruff`/`mypy` |
| `code-Agent-CodeUI.md` (dispatcher) | `.github/agents/code-Agent-CodeUI.md` | Aggiungere frontmatter dispatcher |
| `copilot-instructions.md` | `.github/copilot-instructions.md` di tabboz | Rimuovere tutto ciò che cita Python, pytest, ruff, mypy, type hints |
| `project-profile.md` | `.github/project-profile.md` di tabboz | Azzerare: `active_plugins: []`, `framework_version: ""`, `initialized: false` — è un template |
| `AGENTS.md` | `.github/AGENTS.md` di tabboz | Rimuovere agenti Python-specific; aggiungere sezione "Plugin Agents" vuota e sezione "MCP Runtime Tools" |

> **Nota**: `Agent-Validate.md` e `code-Agent-Code.md` di tabboz **NON vanno nel master** — sono esecutori linguaggio-specifico. Restano come base per `py-Agent-Code.md` e `py-Agent-Validate.md` in `scf-pycode-crafter` (Fase C).

### B1. File di progetto root

**Fonte primaria**: `tabboz-simulator-202/.github/`

**`.github/project-profile.md`** — profilo neutro, senza language:
```yaml
---
spark: true
initialized: false
active_plugins: []
framework_version: ""
---
```
Corpo: istruzioni per compilare il profilo al setup.

**`.github/copilot-instructions.md`** — istruzioni base framework, NON Python-specific.
Fonte primaria: `.github/copilot-instructions.md` in `tabboz-simulator-202`, rimuovere
tutto ciò che fa riferimento a Python, pytest, ruff, mypy, type hints.

**`.github/AGENTS.md`** — indice master. Struttura:
```markdown
# AGENTS Index

## Master Agents (scf-master-codecrafter)
[lista agenti esecutori e dispatcher con nome, ruolo, capabilities]

## Plugin Agents
[sezione vuota con nota: "Populated by installed plugins via AGENTS-{plugin-id}.md"]

## MCP Runtime Tools (engine v1.5.0+)
- scf_get_runtime_state() — leggi stato orchestratore
- scf_update_runtime_state(patch) — aggiorna stato orchestratore
- scf://runtime-state — resource stato runtime
```

### B2. Agenti esecutori (7 file in `.github/agents/`)

**Fonte primaria**: `tabboz-simulator-202/.github/agents/` — vedi tabella mappatura sopra.
**Fallback**: `scf-pycode-crafter/.github/agents/` se il file non esiste in tabboz.

Frontmatter obbligatorio per tutti gli agenti esecutori:
```yaml
---
spark: true
name: Agent-{Nome}
version: 1.0.0
layer: master
role: executor
---
```

**`Agent-Orchestrator.md`** — frontmatter esteso:
```yaml
---
spark: true
name: Agent-Orchestrator
version: 2.0.0
layer: master
role: executor
execution_mode: autonomous
confidence_threshold: 0.85
checkpoints: [design-approval, plan-approval, release]
runtime_state_tool: scf_get_runtime_state
runtime_update_tool: scf_update_runtime_state
---
```
Corpo: flusso E2E con loop autonomo, gestione confidence, retry max 2,
post-step analysis, riduzione checkpoint a 3.
Fonte primaria: agente condiviso `Agent-Orchestrator`, oggi fornito da `spark-base` (origine storica: `tabboz-simulator-202`).
Aggiungere i nuovi campi frontmatter; il corpo è già trasversale e non richiede modifiche sostanziali.

**`Agent-Git.md`** — oggi agente condiviso fornito da `spark-base`.
**`Agent-Helper.md`** — oggi agente condiviso fornito da `spark-base`.
**`Agent-Release.md`** — oggi agente condiviso fornito da `spark-base`; rimuovere step Python-specific.
**`Agent-FrameworkDocs.md`** — oggi agente condiviso fornito da `spark-base`.
**`Agent-Welcome.md`** — oggi agente condiviso fornito da `spark-base`, generalizzare sezioni Python-specific.
**`Agent-Research.md`** — oggi agente condiviso fornito da `spark-base`; in questa fase storica era previsto come nuovo file.
```yaml
---
spark: true
name: Agent-Research
version: 1.0.0
layer: master
role: executor
visibility: internal
output_path: .github/runtime/research-cache/
---
```
Corpo: ricerca online su linguaggio/framework sconosciuto, produce brief strutturato
in `research-cache/{language}-{task-type}.md`. Dichiara sempre che l'output
è fallback dinamico, non competenza nativa. Non è user-facing.

### B3. Agenti dispatcher (6 file in `.github/agents/`)

**Fonte primaria**: `tabboz-simulator-202/.github/agents/` — vedi tabella mappatura sopra.
**Fallback**: `scf-pycode-crafter/.github/agents/` se il file non esiste in tabboz.

Frontmatter obbligatorio:
```yaml
---
spark: true
name: Agent-{Nome}
version: 1.0.0
layer: master
role: dispatcher
delegates_to_capabilities: [{capability}]
fallback: Agent-Research
---
```

Meccanismo dispatcher (corpo comune per tutti):
1. Leggi `project-profile.md` → campo `active_plugins`
2. Leggi tutti i file `AGENTS*.md` via MCP tool `scf://agents-index` → mappa capabilities
3. SE esiste agente con capability richiesta → delega con contesto completo
4. SE non esiste → chiama `Agent-Research` → usa il brief prodotto come contesto

Capabilities per ciascun dispatcher:
- `code-Agent-CodeRouter` — `delegates_to_capabilities: [code, code-ui, routing]`
- `Agent-Analyze` — `delegates_to_capabilities: [analyze]`
- `code-Agent-Design` — `delegates_to_capabilities: [design]`
- `Agent-Plan` — `delegates_to_capabilities: [plan]`
- `Agent-Docs` — `delegates_to_capabilities: [docs]`
- `code-Agent-CodeUI` — `delegates_to_capabilities: [code-ui, ui]`

### B4. Instructions (6 file in `.github/instructions/`)

**Fonte primaria**: `tabboz-simulator-202/.github/instructions/`.
**Fallback**: `scf-pycode-crafter/.github/instructions/` se il file non esiste in tabboz.
Rimuovere tutto ciò che è Python-specific da ogni file.
File da non portare nel master: `python.instructions.md`, `tests.instructions.md`,
`project-reset.instructions.md` (valutare se generica, se sì portarla).

### B5. Skill (24+ file in `.github/skills/`)

**Fonte primaria**: `tabboz-simulator-202/.github/skills/`.
**Fallback**: `scf-pycode-crafter/.github/skills/` se la skill non esiste in tabboz.
Rimuovere riferimenti Python-specific da ogni file migrato.
File da non portare nel master: `error-recovery/reference/errors-python.md`
(resta esclusivamente nel plugin Python).

Skill `framework-index/SKILL.md` e `framework-scope-guard.skill.md` — NUOVE,
non presenti in nessun repo esistente, da creare da zero:
- `framework-index`: catalogo navigabile di tutti gli agenti e skill del framework installato
- `framework-scope-guard`: protezione perimetro framework, evita modifiche fuori scope

### B6. Runtime state default

**`.github/runtime/orchestrator-state.json`**:
```json
{
  "current_phase": "",
  "current_agent": "",
  "retry_count": 0,
  "confidence": 1.0,
  "execution_mode": "autonomous",
  "last_updated": "",
  "phase_history": [],
  "active_task_id": ""
}
```

### B7. Changelog package

**`.github/changelogs/scf-master-codecrafter.md`**:
```markdown
# Changelog — scf-master-codecrafter

## [1.0.0] - 2026-04-10

### Added
- Prima release del layer master SCF
- 7 agenti esecutori: Orchestrator v2.0, Git, Helper, Release, FrameworkDocs, Welcome, Research
- 6 agenti dispatcher con meccanismo fallback via Agent-Research
- 24 skill trasversali migrate da tabboz-simulator-202 e scf-pycode-crafter
- 6 instruction files trasversali
- Runtime state orchestratore: .github/runtime/orchestrator-state.json
- Supporto pattern multi-plugin M1: AGENTS-{plugin-id}.md per plugin
- min_engine_version: 1.5.0 (richiede scf_get_runtime_state e scf_update_runtime_state)
```

---

## Fase C — Refactor `scf-pycode-crafter` → v2.0.0

Correzione validata: il workflow `.github/workflows/notify-engine.yml` non rientra tra i file migrati al master e va preservato.

### C1. Creare `.github/AGENTS-python.md`

Indice degli agenti Python. Struttura:
```markdown
# AGENTS — scf-pycode-crafter (Python)

## Agenti specializzati Python

| Nome | Capabilities | Linguaggi |
|---|---|---|
| py-Agent-Code | code, implementation | python |
| py-Agent-Analyze | analyze, code-review, refactor, type-check | python |
| py-Agent-Design | design, architecture | python |
| py-Agent-Plan | plan | python |
| py-Agent-Validate | validate, test, lint | python |
```

### C2. Creare `.github/python.profile.md`

Profilo tecnico Python del progetto:
```yaml
---
spark: true
plugin: scf-pycode-crafter
---
```
Corpo: stack Python (interprete, testing, linting, type checker), convenzioni specifiche.

### C3. Aggiornare frontmatter di tutti gli agenti rimanenti

Aggiungere a ogni `py-Agent-*.md`:
```yaml
plugin: scf-pycode-crafter
capabilities: [...]   # vedi lista per ciascuno
languages: [python]
```

Capabilities per ciascun agente:
- `py-Agent-Code`: `[code, implementation]`
- `py-Agent-Analyze`: `[analyze, code-review, refactor, type-check]`
- `py-Agent-Design`: `[design, architecture]`
- `py-Agent-Plan`: `[plan]`
- `py-Agent-Validate`: `[validate, test, lint]`

### C4. Rimuovere i file migrati al master

File da eliminare dal repo `scf-pycode-crafter` (già posseduti dal master):
- `.github/agents/py-Agent-Orchestrator.md` (Opzione A: rimosso, non sostituito)
- `.github/agents/py-Agent-Git.md`
- `.github/agents/py-Agent-Helper.md`
- `.github/agents/py-Agent-Release.md`
- `.github/agents/py-Agent-CodeRouter.md`
- `.github/agents/py-Agent-Docs.md`
- `.github/AGENTS.md` → sostituito da `AGENTS-python.md`
- `.github/copilot-instructions.md`
- `.github/project-profile.md`
- Tutte le skill trasversali (vedi lista in package-manifest.json del master)
- Tutte le instructions trasversali (framework-guard, git-policy, model-policy, personality, verbosity, workflow-standard)

### C5. Aggiornare `package-manifest.json` di pycode-crafter

```json
{
  "schema_version": "2.0",
  "package": "scf-pycode-crafter",
  "version": "2.0.0",
  "display_name": "SCF Python Code Crafter",
  "description": "Agenti, skill e istruzioni specializzati per lo sviluppo Python. Richiede scf-master-codecrafter.",
  "author": "Nemex81",
    "min_engine_version": "1.9.0",
  "dependencies": ["scf-master-codecrafter"],
  "conflicts": [],
  "file_ownership_policy": "error",
  "changelog_path": ".github/changelogs/scf-pycode-crafter.md",
  "files": [
    ".github/AGENTS-python.md",
    ".github/python.profile.md",
    ".github/changelogs/scf-pycode-crafter.md",
    ".github/agents/py-Agent-Code.md",
    ".github/agents/py-Agent-Analyze.md",
    ".github/agents/py-Agent-Design.md",
    ".github/agents/py-Agent-Plan.md",
    ".github/agents/py-Agent-Validate.md",
    ".github/instructions/python.instructions.md",
    ".github/instructions/tests.instructions.md",
    ".github/skills/error-recovery/reference/errors-python.md"
  ]
}
```

---

## Fase D — Aggiornare `scf-registry`

**File**: `scf-registry/registry.json`

Aggiungere nel array `packages`:
```json
{
  "id": "scf-master-codecrafter",
  "display_name": "SCF Master CodeCrafter",
  "description": "Layer base prerequisito per tutti i plugin SCF linguaggio-specifici.",
  "latest_version": "1.0.0",
  "status": "stable",
  "repo_url": "https://github.com/Nemex81/scf-master-codecrafter",
    "engine_min_version": "1.9.0",
  "tags": ["master", "orchestrator", "dispatcher", "base"]
}
```

Aggiornare entry esistente `scf-pycode-crafter`:
- `latest_version`: `"1.2.1"` → `"2.0.0"`
- Aggiungere `"engine_min_version": "1.9.0"`

---

## Checklist Finale per Copilot

Prima di considerare il lavoro completo, verificare:

- [ ] `spark-framework-engine.py` versione è `1.5.0`
- [ ] Tool count nel docstring di `register_tools()` è 25
- [ ] Resource count nel log di `register_resources()` è 15
- [ ] Tutti i file in `package-manifest.json` di master esistono nel repo
- [ ] Tutti gli agenti master hanno frontmatter con `spark: true` e `layer: master`
- [ ] Tutti gli agenti dispatcher hanno `role: dispatcher`, `delegates_to_capabilities`, `fallback`
- [ ] `Agent-Research` ha `visibility: internal`
- [ ] `Agent-Orchestrator` ha `execution_mode`, `confidence_threshold`, `checkpoints`
- [ ] `.github/runtime/orchestrator-state.json` esiste con valori default
- [ ] `scf-pycode-crafter` non contiene più i file migrati al master
- [ ] `AGENTS-python.md` esiste in `scf-pycode-crafter`
- [ ] Tutti gli agenti `py-Agent-*` hanno `plugin`, `capabilities`, `languages` nel frontmatter
- [ ] `registry.json` contiene `scf-master-codecrafter` e `scf-pycode-crafter` v2.0.0
- [ ] CHANGELOG aggiornato in tutti e tre i repo
- [ ] NON esiste `py-Agent-Orchestrator.md` in `scf-pycode-crafter` (Opzione A)
- [ ] NON è stato scritto nulla in `tabboz-simulator-202`
