# Fase 1 — Schema manifest v3.0 + engine-manifest.json + spark-welcome
# Dipende da: Fase 0
# Effort stimato: M
# File target:
#   - spark-framework-engine/engine-manifest.json (nuovo)
#   - spark-framework-engine/.github/agents/spark-welcome.agent.md (nuovo)
#   - spark-base/package-manifest.json
#   - scf-master-codecrafter/package-manifest.json
#   - scf-pycode-crafter/package-manifest.json

## Prerequisiti

- [ ] Fase 0 completata e in main
- [ ] Backup di tutti i package-manifest.json prima di toccarli

## Task

- [ ] 1.1 Creare `engine-manifest.json` nella root engine
      File: `spark-framework-engine/engine-manifest.json`
      Schema: vedi §5.4 del design.
      Contenuto minimo: schema_version 3.0, package
      "spark-framework-engine", version "3.0.0", `workspace_files[]`
      con le 6 instruction da §3.5, `mcp_resources` con 4 agenti
      (incluso spark-welcome) e 3 instruction MCP.

- [ ] 1.2 Creare agente `spark-welcome.agent.md`
      File:
      `.github/agents/spark-welcome.agent.md`
      Contenuto: descrizione ruolo onboarding, responsabilità da
      §3.1 del design, frontmatter coerente con altri agenti
      engine, `spark: true`, `scf_owner: "spark-framework-engine"`.

- [ ] 1.3 Aggiornare manifest spark-base
      File: `spark-base/package-manifest.json`
      Aggiungere `workspace_files[]` (file Copilot-loaded) e
      `mcp_resources{}` (agents/skills/instructions/prompts).
      `engine_provided_skills` mantenuto per fallback v2.x ma
      duplicato in `mcp_resources.skills`.
      Aggiornare `schema_version` a "3.0", incrementare `version` a
      "1.6.0".

- [ ] 1.4 Aggiornare manifest scf-master-codecrafter
      File: `scf-master-codecrafter/package-manifest.json`
      Identico al 1.3, version → "2.4.0".

- [ ] 1.5 Aggiornare manifest scf-pycode-crafter
      File: `scf-pycode-crafter/package-manifest.json`
      Identico al 1.3, version → "2.2.0".

- [ ] 1.6 Estendere `EngineInventory` per caricare engine-manifest
      File: `spark-framework-engine.py`
      Riga di partenza: 1308 (`class EngineInventory`).
      Aggiungere metodo `load_engine_manifest() -> dict` chiamato
      al costruttore. Se file assente: log warning e continua con
      manifest vuoto.

- [ ] 1.7 Test: engine v2.4.0 legge manifest v3.0 senza crash
      File: `tests/test_manifest_compatibility.py`
      Verifica fallback su `files` quando `workspace_files`
      assente, e viceversa.

- [ ] 1.8 Test: engine carica engine-manifest.json correttamente
      File: `tests/test_engine_inventory.py` (estendere se esiste)
      Verifica popolamento `mcp_resources` da engine-manifest.

## Test di accettazione

- [ ] Tutti i 3 manifest pacchetto a `schema_version: 3.0`.
- [ ] Engine v2.4.0 (in stage) avvia correttamente con manifest
      v3.0, log warning fallback solo per `engine_provided_skills`.
- [ ] `engine-manifest.json` valido secondo schema definito.
- [ ] `.github/agents/spark-welcome.agent.md` esiste con frontmatter
      corretto.
- [ ] `EngineInventory` espone metadata di spark-welcome via
      `list_agents()`.

## Note tecniche

- Migrazione additiva: NON rimuovere `files[]` dai manifest v2.1,
  serve come fallback per engine v2.x in lettura.
- `files_metadata[]` rimane invariato; engine v3.x lo userà solo
  per file in `workspace_files[]`.
- Il file `.github/AGENTS.md` esistente nell'engine non va toccato
  in questa fase (verrà rigenerato dinamicamente in Fase 6).
