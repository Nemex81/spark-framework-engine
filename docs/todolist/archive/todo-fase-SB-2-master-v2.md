# Fase SB-2 — Riduzione scf-master-codecrafter a CORE-CRAFT

Stato attuale: Completata

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 2)
- Analisi ROSSA: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Lista Rossa)

Checklist:

- [x] Aggiornare `package-manifest.json` di scf-master-codecrafter:
  - [x] `version: "2.1.0"`
  - [x] `dependencies: ["spark-base"]`
  - [x] `description`: descrivere come "Plugin CORE-CRAFT per master-layer SCF"
  - [x] `files`: ridurre a 14 file esatti (vedi lista sotto)
- [x] Creare `.github/AGENTS-master.md` con lista agenti CORE-CRAFT e asset master attivi
- [x] Aggiornare `.github/changelogs/scf-master-codecrafter.md` aggiungendo la voce della release corrente
- [x] Verifica che i file rimasti siano esattamente:
  - [x] `.github/AGENTS-master.md`
  - [x] `.github/changelogs/scf-master-codecrafter.md`
  - [x] `.github/agents/Agent-Code.md`
  - [x] `.github/agents/Agent-Design.md`
  - [x] `.github/agents/Agent-CodeRouter.md`
  - [x] `.github/agents/Agent-CodeUI.md`
  - [x] `.github/copilot-instructions.md`
  - [x] `.github/instructions/mcp-context.instructions.md`
  - [x] `.github/skills/clean-architecture/SKILL.md`
  - [x] `.github/skills/clean-architecture/templates/project-structure.md`
  - [x] `.github/skills/code-routing.skill.md`
  - [x] `.github/skills/docs-manager/SKILL.md`
  - [x] `.github/skills/docs-manager/templates/readme-template.md`
  - [x] `.github/skills/docs-manager/templates/adr-template.md`
- [x] Committare e pushare

Criteri di uscita:

- `package-manifest.json` di scf-master-codecrafter ha esattamente 14 file
- `dependencies: ["spark-base"]` dichiarata
- `version: "2.1.0"` nel manifest
- `AGENTS-master.md` presente nel repo

Note operative:

- SB-2 è parallelizzabile con SB-1 (repo diversi)
- I file rimossi dal manifest NON vengono cancellati dal repo master-codecrafter:
  rimangono nel repository sorgente ma non vengono più installati come parte del pacchetto
- Il bump MAJOR (1.0.0 → 2.0.0) ha ridotto il perimetro del pacchetto; la release corrente documentata è `2.1.0`.
- Validazione locale e runtime completata: manifest parsabile, `files.Count = 14`, dependency `spark-base`
  confermata e pacchetto reinstallato con successo nel workspace reale `uno-ultra-v68`.
