# Migration Guide — SPARK Framework Engine v2.x → v3.0

**Data rilascio target:** 2026-04-28
**Engine:** `spark-framework-engine` 3.0.0
**Pacchetti compatibili:** `spark-base@1.6+`, `scf-master-codecrafter@2.4+`,
`scf-pycode-crafter@2.2+`

---

## Cosa cambia in v3.0

### 1. Centralized Package Store

In v2.x i file dei pacchetti (`agents/`, `prompts/`, `skills/`,
`instructions/`) venivano **copiati** in `workspace/.github/`. In v3.0 i
file vivono **una sola volta** in `engine_dir/packages/{pkg_id}/.github/`
e sono serviti tramite MCP resources.

Risultato: `workspace/.github/` non contiene più cartelle `agents/`,
`prompts/`, `skills/`, `instructions/` di pacchetto. Contiene solo:

- `copilot-instructions.md` (composto via `merge_sections`)
- `AGENTS.md` (generato dal bootstrap, safe-merge)
- `AGENTS-{plugin}.md` (uno per pacchetto con agenti)
- `project-profile.md` (template, da compilare via spark-welcome)
- `overrides/{type}/{name}.{ext}` (custom utente)
- `.scf-manifest.json` (schema 3.0)

### 2. Override workspace

Per personalizzare un agente/prompt/skill/instruction senza forkare il
pacchetto:

```text
workspace/.github/overrides/agents/spark-guide.agent.md
workspace/.github/overrides/prompts/git-commit.prompt.md
```

L'override ha priorità sull'asset engine quando viene risolto via MCP.

Tool MCP correlati:

- `scf_override_resource(uri, content)` — scrive override
- `scf_drop_override(uri)` — rimuove override
- `scf_read_resource(uri, source="auto"|"engine"|"override")` — legge
- `scf_list_overrides()` — elenca override attivi

### 3. AGENTS.md dinamico

`workspace/.github/AGENTS.md` non è più un file copiato, è generato dal
bootstrap a partire dalla lista agenti engine + agenti dei pacchetti
installati. Il file usa marker SCF per safe-merge:

```markdown
# Custom user content (preserved)

<!-- SCF:BEGIN:agents-index -->
… contenuto rigenerato a ogni bootstrap …
<!-- SCF:END:agents-index -->

## More user content (preserved)
```

### 4. ManifestManager schema 3.0

`.scf-manifest.json` ora include `overrides[]` derivato dalle entry:

```json
{
  "schema_version": "3.0",
  "entries": [...],
  "overrides": [
    {"type": "agents", "name": "spark-guide", "file": "...", "sha256": "..."}
  ]
}
```

Schemi 1.0/2.0/2.1 sono ancora letti correttamente; alla prima `save()`
il file viene riscritto in schema 3.0.

---

## Procedura di migrazione automatica

### Pre-requisiti

1. Backup del workspace (consigliato: `git commit` o copia di
   `.github/`).
2. Engine aggiornato a v3.0.0 e MCP server riavviato.
3. Pacchetti ricostruiti: `engine_dir/packages/{pkg_id}/` deve esistere
   per ogni pacchetto installato.

### Step 1 — Dry-run

```text
scf_migrate_workspace(dry_run=True)
```

Output: lista file che verranno rimossi (agents/, prompts/, ecc.) e
override che verranno preservati. Nessuna scrittura.

### Step 2 — Apply

```text
scf_migrate_workspace(dry_run=False)
```

Effetti:

- Rimuove `workspace/.github/agents/*`, `prompts/*`, `skills/*`,
  `instructions/*` (escludendo `overrides/`).
- Mantiene `copilot-instructions.md`, `AGENTS.md`, `project-profile.md`.
- Riscrive `.scf-manifest.json` in schema 3.0.

### Step 3 — Bootstrap v3

```text
scf_bootstrap_workspace(install_base=False)
```

Effetti (Phase 6):

- Genera `AGENTS.md` dinamico (safe-merge se presente).
- Genera `AGENTS-{pkg_id}.md` per ogni pacchetto con agenti.
- Crea template `project-profile.md` se assente.
- Crea `.clinerules` se assente (mai sovrascritto).

### Step 4 — Verifica

1. Dropdown agenti Copilot mostra agenti engine e pacchetto.
2. `scf_list_overrides()` elenca eventuali override preservati.
3. `scf_verify_workspace()` non riporta `duplicate_owners` o
   `untagged_spark_files` inattesi.

---

## Aggiornamento `min_engine_version` nei pacchetti

I manifest dei pacchetti devono dichiarare:

```json
{
  "min_engine_version": "3.0.0"
}
```

I pacchetti del repo aggiornati in questa release:

- `spark-base/package-manifest.json`
- `scf-master-codecrafter/package-manifest.json`
- `scf-pycode-crafter/package-manifest.json`

I pacchetti che dichiarano `min_engine_version < 3.0.0` continuano ad
essere installabili, ma non beneficiano del centralized store: l'engine
emette un warning e ricade sul flusso v2 di copia file.

---

## Rollback

Se la migrazione causa problemi:

1. Ripristina `.github/` dal backup.
2. Riporta `ENGINE_VERSION` a `2.4.0` (pin engine in `mcp.json`).
3. Apri issue con il diff di `scf_migrate_workspace(dry_run=True)`.

---

## FAQ

**Domanda:** perché `project-profile.md` non viene aggiornato dopo
modifiche manuali?
**Risposta:** v3.0 non implementa ancora `scf_update_profile`. Per
propagare le modifiche agli asset derivati (AGENTS.md, .clinerules),
ri-esegui `scf_bootstrap_workspace`. Tool dedicato pianificato per v3.1.

**Domanda:** come edito un agente engine?
**Risposta:** crea un override:
`scf_override_resource("agents://spark-guide", "<contenuto>")`. Il file
viene scritto in `.github/overrides/agents/spark-guide.agent.md`.

**Domanda:** le risorse `engine-skills://` e `engine-instructions://`
sono ancora disponibili?
**Risposta:** sì, sono mantenute per retrocompatibilità con v2.4.x.

---

## Test eseguiti

- pytest suite: **272 passed** (escluso `tests/test_integration_live.py`).
- Smoke test manuali Copilot: vedi `docs/SMOKE-TEST-COPILOT-v3.md`
  (DEFERRED, eseguibili solo da utente con UI Copilot).
