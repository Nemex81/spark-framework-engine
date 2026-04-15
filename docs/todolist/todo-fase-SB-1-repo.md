# Fase SB-1 — Creazione repository spark-base

Stato attuale: In corso

Riferimenti:
- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 1)
- Analisi VERDE: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Lista Verde/Gialla)

Checklist:
- [ ] Creare repo `Nemex81/spark-base` su GitHub (pubblico, branch `main`)
- [x] Creare struttura `.github/` nel repo locale
- [x] Copiare 8 agenti VERDE da master-codecrafter senza modifiche
- [x] Copiare 3 agenti GIALLA (Agent-Orchestrator, Agent-Release, Agent-Validate) senza modifiche
- [x] Copiare 5 instruction VERDE senza modifiche
- [x] Copiare `git-policy.instructions.md` GIALLA senza modifiche
- [x] Copiare 22 skill GP VERDE senza modifiche
- [x] Copiare 7 skill riclassificate GIALLA (git-execution, conventional-commit, rollback-procedure, semver-bump, changelog-entry/SKILL.md, changelog-entry/templates/entry-template.md) senza modifiche
- [x] Copiare 18 prompt `.prompt.md` + `README.md` da `.github/prompts/` senza modifiche
- [x] Creare `.github/AGENTS.md` versione spark-base (G10): lista 11 agenti base
- [x] Editare `.github/copilot-instructions.md` (G11): descrizione "layer fondazionale", rimuovere riferimenti plugin-specific
- [x] Copiare `.github/project-profile.md` (G12) invariato
- [x] Creare `.github/changelogs/spark-base.md` con voce `[1.0.0]`
- [x] Creare `package-manifest.json` con ~69 file, `version: "1.0.0"`, `dependencies: []`, `min_engine_version: "1.9.0"`
- [x] Creare `README.md` del repository
- [ ] Committare e pushare tutti i file

Criteri di uscita:
- Repo `Nemex81/spark-base` pubblicamente accessibile su GitHub
- `package-manifest.json` scaricabile via raw URL
- Tutti i file elencati nel manifest sono presenti nel repo al path corretto
- `https://raw.githubusercontent.com/Nemex81/spark-base/main/package-manifest.json` restituisce il manifest corretto

Note operative:
- Verificare che il conteggio file nel manifest corrisponda alla realtà (puntare a 68–69)
- Il file `changelogs/spark-base.md` deve seguire il formato Keep a Changelog
- L'AGENTS.md di spark-base deve includere: Agent-Analyze, Agent-Plan, Agent-Docs, Agent-Helper,
  Agent-Research, Agent-Welcome, Agent-FrameworkDocs, Agent-Git, Agent-Orchestrator,
  Agent-Release, Agent-Validate (11 agenti)
- La `copilot-instructions.md` deve smettere di menzionare `python.instructions.md`,
  `tests.instructions.md`, `mcp-context.instructions.md`
- Implementazione locale completata e validata: `package-manifest.json` dichiara 69 file e i 69 file
    esistono realmente sotto `.github/` nel repo locale `spark-base`.
- Publish remoto ancora bloccato: `gh` non installato e sessione browser GitHub non autenticata.
