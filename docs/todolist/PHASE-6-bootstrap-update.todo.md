# Fase 6 — scf_bootstrap_workspace aggiornato
# Dipende da: Fasi 1, 2, 5
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_bootstrap_workspace.py (estensione)

## Prerequisiti

- [ ] Fase 1: engine-manifest.json e spark-welcome presenti
- [ ] Fase 2: McpResourceRegistry operativa
- [ ] Fase 5: get_override_dir disponibile

## Task

- [ ] 6.1 Generare AGENTS.md dinamicamente da
      `McpResourceRegistry`
      File: `spark-framework-engine.py`
      Helper: `_render_agents_md(registry, packages) -> str`.
      Output: lista markdown con frontmatter SPARK, sezione
      "Agenti engine" e "Agenti pacchetto" raggruppati.
      Safe-merge con file esistente: preserva testo utente fuori
      dai marker `<!-- SCF:BEGIN:agents-index --> ... END`.

- [ ] 6.2 Generare AGENTS-{plugin}.md per ogni pacchetto con
      agenti
      File: `spark-framework-engine.py`
      Helper: `_render_plugin_agents_md(package_id, agents)`.

- [ ] 6.3 Generare `.clinerules` se assente
      File: `spark-framework-engine.py`
      Helper: `_render_clinerules(profile_summary) -> str`.
      Contenuto: vedi §7.1 del design. Estrae sommario da
      `project-profile.md` se presente.

- [ ] 6.4 Scrivere template `project-profile.md` se assente
      File: `spark-framework-engine.py`
      Template minimale con frontmatter e sezioni vuote che
      l'utente compila via spark-welcome.

- [ ] 6.5 Riscrivere `scf_bootstrap_workspace`
      File: `spark-framework-engine.py`
      Riga partenza: 5075.
      Nuova logica (vedi §6.5 del design):
      1. Sentinella `project-profile.md` per idempotenza.
      2. Copia `workspace_files` da engine-manifest + manifest
         pacchetti.
      3. Genera AGENTS.md + AGENTS-{plugin}.md.
      4. Genera `.clinerules` se assente.
      5. Scrive template `project-profile.md` se assente.
      6. Scansiona `.github/overrides/` e popola registry.
      7. NON copia agents/, prompts/, skills/ nel workspace.

- [ ] 6.6 Test bootstrap workspace vergine
      File: `tests/test_bootstrap_workspace.py`
      Verifica file generati e assenza di
      `agents/`, `prompts/`, `skills/` nel workspace.

- [ ] 6.7 Test bootstrap idempotente
      File: `tests/test_bootstrap_workspace.py`
      Secondo run su workspace già bootstrapato →
      `project-profile.md` modificato preservato.

- [ ] 6.8 Test bootstrap con overrides preesistenti
      File: `tests/test_bootstrap_workspace.py`
      Workspace con `.github/overrides/agents/X.md` →
      registry registra override.

## Test di accettazione

- [ ] Bootstrap su workspace vergine produce:
      `.github/copilot-instructions.md`, `.github/AGENTS.md`,
      `.github/project-profile.md`, `.clinerules`.
- [ ] Nessun file in `.github/agents/`, `.github/prompts/`,
      `.github/skills/` post-bootstrap.
- [ ] Bootstrap su workspace con overrides → registry popolata.
- [ ] `project-profile.md` modificato dall'utente non
      sovrascritto al re-bootstrap.

## Note tecniche

- AGENTS.md esistente nell'engine `.github/AGENTS.md` non va
  toccato (è asset engine, non workspace).
- Il safe-merge deve usare lo stesso pattern di
  `copilot-instructions.md` (marker `SCF:BEGIN/END`).
- `.clinerules` non ha marker SCF: se esiste già con contenuto
  utente, log warning e NON sovrascrivere.
