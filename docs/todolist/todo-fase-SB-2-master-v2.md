# Fase SB-2 — Riduzione scf-master-codecrafter a v2.0.0

Stato attuale: In corso

Riferimenti:
- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 2)
- Analisi ROSSA: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Lista Rossa)

Checklist:
- [x] Aggiornare `package-manifest.json` di scf-master-codecrafter:
  - [x] `version: "2.0.0"`
  - [x] `dependencies: ["spark-base"]`
  - [x] `description`: descrivere come "Plugin CORE-CRAFT per master-layer SCF"
  - [x] `files`: ridurre a 12 file esatti (vedi lista sotto)
- [x] Creare `.github/AGENTS-master.md` con lista 3 agenti CORE-CRAFT (Agent-Design, Agent-CodeRouter, Agent-CodeUI)
- [x] Aggiornare `.github/changelogs/scf-master-codecrafter.md` aggiungendo voce `[2.0.0]`
- [ ] Verifica che i file rimasti siano esattamente:
  - [ ] `.github/AGENTS-master.md` (nuovo)
  - [ ] `.github/changelogs/scf-master-codecrafter.md`
  - [ ] `.github/agents/Agent-Design.md`
  - [ ] `.github/agents/Agent-CodeRouter.md`
  - [ ] `.github/agents/Agent-CodeUI.md`
  - [ ] `.github/instructions/mcp-context.instructions.md`
  - [ ] `.github/skills/clean-architecture/SKILL.md`
  - [ ] `.github/skills/clean-architecture/templates/project-structure.md`
  - [ ] `.github/skills/code-routing.skill.md`
  - [ ] `.github/skills/docs-manager/SKILL.md`
  - [ ] `.github/skills/docs-manager/templates/readme-template.md`
  - [ ] `.github/skills/docs-manager/templates/adr-template.md`
- [ ] Committare e pushare

Criteri di uscita:
- `package-manifest.json` di scf-master-codecrafter ha esattamente 12 file
- `dependencies: ["spark-base"]` dichiarata
- `version: "2.0.0"` nel manifest
- `AGENTS-master.md` presente nel repo

Note operative:
- SB-2 è parallelizzabile con SB-1 (repo diversi)
- I file rimossi dal manifest NON vengono cancellati dal repo master-codecrafter:
  rimangono nel repository sorgente ma non vengono più installati come parte del pacchetto
- Il bump MAJOR (1.0.0 → 2.0.0) è corretto: il pacchetto perde 48+ file dichiarati
  e acquisisce una nuova dependency (spark-base)
- Validazione locale completata: manifest parsabile, `files.Count = 12`, dependency `spark-base` confermata,
  changelog senza errori markdown.
