# Changelog

Tutte le modifiche importanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com) e il versioning segue [Semantic Versioning](https://semver.org).

---

## [1.2.0] — 30 marzo 2026

### Added

- **Agente di manutenzione SCF**: creato `.github/agents/spark-engine-maintainer.agent.md` con perimetro operativo, responsabilita' e regole di comportamento per la manutenzione del motore.
- **Skill dedicate all'agente**: aggiunte 6 skill in formato standard `skill-name/SKILL.md`:
	- `.github/skills/scf-coherence-audit/SKILL.md`
	- `.github/skills/scf-changelog/SKILL.md`
	- `.github/skills/scf-tool-development/SKILL.md`
	- `.github/skills/scf-prompt-management/SKILL.md`
	- `.github/skills/scf-release-check/SKILL.md`
	- `.github/skills/scf-documentation/SKILL.md`
- **Istruzioni operative dominio motore**: creato `.github/instructions/spark-engine-maintenance.instructions.md` con convenzioni su naming tool/prompt, contatori, versioning e policy di conferma.
- **Entry point Copilot repository-scoped**: creato `.github/copilot-instructions.md` con regole di ingaggio e riferimenti agli artefatti del maintainer.

### Notes

- Introduzione non-breaking: la release aggiunge artefatti di governance e manutenzione senza alterare API MCP o comportamento runtime del motore.

## [1.1.0] — 30 marzo 2026

### Added

- **Dual-format skill discovery**: `FrameworkInventory.list_skills()` ora scopre le skill sia nel formato legacy piatto (`.github/skills/*.skill.md`) sia nel formato standard Agent Skills (`.github/skills/skill-name/SKILL.md`). Entrambi i formati sono completamente supportati e funzionali.
- **Test coverage for skill discovery**: suite di test completa per verificare la scoperta di skill in formato piatto, standard, collisioni di nome e comportamento su directory vuote.

### Changed

- **Skill deduplication logic**: in caso di collisione tra un file `foo.skill.md` e una directory `foo/SKILL.md`, il formato piatto legacy ha priorità e prevale.
- **Skill listing sort**: le skill risultati sono ordinate alfabeticamente per nome.

### Fixed

- **Typo in README**: contatore tool corretto da 13 a 18. I tool effettivamente registrati sono 18: lista aggiornata nel README per riflettere `scf_list_available_packages`, `scf_get_package_info`, `scf_list_installed_packages`, `scf_install_package`, `scf_update_packages`, `scf_apply_updates`, `scf_remove_package` aggiunti agli 11 tool core di inventory.

### Notes

- Nessuna breaking change: il comportamento su repository legacy contenenti solo skill in formato piatto rimane completamente invariato.
- La resource `skills://{name}` e il tool `scf_get_skill` funzionano correttamente su entrambi i formati senza modifiche.

---

## [1.0.0] — 20 febbraio 2026

### Initial Release

- Server MCP universale per il SPARK Code Framework
- Discovery dinamico di agenti, skill, istruzioni e prompt da `.github/`
- 14 Resources MCP (agents, skills, instructions, prompts, scf-*) e 11 tool core
- Gestione manifest di installazione con SHA-256 tracking
- Source registry support (pubblico, read-only in v1)
- Tool di installazione, aggiornamento e rimozione di pacchetti SCF
- Parser YAML-style frontmatter con supporto liste inline e block
- Test coverage con unittest (standard library, zero external dependencies)
