# Changelog

Tutte le modifiche importanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com) e il versioning segue [Semantic Versioning](https://semver.org).

---

## [1.8.2] — 2026-04-12

### Added

- `spark-assistant v1.0.0` — agente utente finale per onboarding, gestione pacchetti e diagnostica workspace. Sostituisce il placeholder precedente.

### Changed

- `spark-init.py` include ora anche `spark-engine-maintainer.agent.md` tra gli asset bootstrap copiati nel workspace utente.
- `ENGINE_VERSION` aggiornato a `1.8.2`.

---

## [1.8.1] — 2026-04-12

### Changed

- `WorkspaceLocator` usa ora una cascata piu robusta: `WORKSPACE_FOLDER` valido, marker locali del workspace (`.vscode/settings.json`, `.vscode/mcp.json`, `*.code-workspace`), discovery SCF sotto `.github/`, quindi fallback finale su `cwd`.

### Fixed

- Il motore non accetta piu in modo cieco il path della home utente come workspace quando `WORKSPACE_FOLDER` manca o viene risolto in modo errato senza marker locali SPARK.
- Ridotte le risoluzioni errate del workspace causate da merge parziali della configurazione MCP tra livello globale e livello workspace.

### Notes

- Il fix mantiene compatibile il bootstrap di workspace non inizializzati: un `WORKSPACE_FOLDER` esplicito e valido continua a essere accettato anche se `.github/` non esiste ancora.

---

## [1.8.0] — 2026-04-12

### Added

- `spark-assistant.agent.md`: nuovo agente bootstrap per l'utente finale orientato a catalogo, installazione, update e diagnostica base dei pacchetti SCF.
- `spark-assistant-guide.instructions.md`: instruction dedicata al comportamento operativo dell'assistente bootstrap.
- `scf-package-management` skill: guida riutilizzabile per il ciclo install/update/remove/verify dei pacchetti SCF.
- `spark-init.py`: `_update_vscode_settings()` crea o aggiorna `.vscode/settings.json` scrivendo solo la chiave `mcp.servers.sparkFrameworkEngine`; JSON corrotto loggato su stderr e ricreato.
- `spark-init.py`: `_bootstrap_github_files()` copia `agents/spark-assistant.agent.md`, `instructions/spark-assistant-guide.instructions.md` e tutti i `prompts/scf-*.prompt.md` dal repo engine al workspace utente con idempotenza SHA-256.
- `spark-init.py`: `main()` produce ora su stdout un riepilogo ordinato (workspace, settings, ogni file bootstrap, modalità e cartella); tutto il logging intermedio è su stderr nel formato `[SPARK-INIT][LEVEL]`.

### Changed

- `scf_bootstrap_workspace()` ora copia l'agente `spark-assistant.agent.md` e `spark-assistant-guide.instructions.md` dal repo engine al workspace utente.
- `ENGINE_VERSION` aggiornato a `1.8.0`.

### Notes

- Il bootstrap resta idempotente e, se trova un workspace gia bootstrap-pato in modo parziale, completa solo gli asset mancanti senza sovrascrivere file utente.

---

## [1.7.0] — 2026-04-12

### Added

- `scf_bootstrap_workspace()` tool: copia i prompt base SPARK e l'agente assistant dal repo engine alla cartella `.github/` del workspace utente senza usare il manifest dei pacchetti.

### Changed

- Conteggio tool aggiornato da 27 a 28.
- `ENGINE_VERSION` aggiornato a `1.7.0`.

### Notes

- Il bootstrap usa solo I/O locale, preserva i file gia presenti con contenuto diverso e suggerisce `/scf-list-available` come passo successivo.

---

## [1.6.0] — 2026-04-11

### Added

- `scf_check_updates()` tool: restituisce solo i pacchetti installati che hanno un aggiornamento disponibile.
- `scf_update_package(package_id)` tool: aggiorna un singolo pacchetto installato preservando i file modificati dall'utente.

### Changed

- Conteggio tool aggiornato da 25 a 27.
- `ENGINE_VERSION` aggiornato a `1.6.0`.

### Notes

- `scf_update_package(package_id)` riusa il planner dependency-aware e la logica di installazione esistenti, senza introdurre nuovi modelli dati.

---

## [1.5.1] — 2026-04-10

### Changed

- `scf_update_packages()` ora restituisce anche un piano di update ordinato per dipendenze e gli eventuali blocchi operativi.
- `scf_apply_updates()` ora usa il piano dependency-aware invece di applicare aggiornamenti in ordine lineare.
- `registry-sync-gateway.yml` accetta anche `stable` come status valido del registry.

### Fixed

- Allineata la documentazione pubblica del motore al conteggio reale delle resource e al flusso di update.

### Notes

- Nessun nuovo tool MCP pubblico: il rafforzamento riguarda il comportamento dei tool di update esistenti.

---

## [1.5.0] — 2026-04-10

### Added

- `scf_get_runtime_state` tool: legge `.github/runtime/orchestrator-state.json`.
- `scf_update_runtime_state` tool: aggiorna con merge parziale `orchestrator-state.json`.
- `scf://runtime-state` resource: espone lo stato runtime come JSON leggibile direttamente.
- `FrameworkInventory.get_orchestrator_state()`: lettura con default e gestione file corrotto.
- `FrameworkInventory.set_orchestrator_state()`: scrittura con merge, creazione cartella runtime e timestamp UTC.
- `FrameworkInventory.list_agents_indexes()`: scoperta di tutti i file `AGENTS*.md` per supporto multi-plugin.

### Changed

- `scf://agents-index`: ora aggrega tutti i file `AGENTS*.md` presenti nella root `.github/`.
- Conteggio resource aggiornato da 14 a 15.
- Conteggio tool aggiornato da 23 a 25.

### Notes

- `.github/runtime/` resta esclusa dal `ManifestManager` per design.
- `scf-master-codecrafter` richiede `min_engine_version: 1.5.0`.

---

## [1.4.2] — 2026-04-06

### Fixed

- **README.md**: corretto conteggio tool da 22 a 23; aggiunto `scf_verify_system` nella lista tool.
- **CHANGELOG.md**: normalizzate le date delle versioni precedenti al formato ISO 8601 (YYYY-MM-DD).

---

## [1.4.1] — 2026-04-02

### Fixed

- **Atomicità installazione in `scf_install_package`**: il blocco diff-cleanup (rimozione file
  obsoleti) è stato spostato **dopo** la fase fetch. Se uno o più file non possono essere
  scaricati, l'installazione si interrompe prima di toccare il disco — manifiest e file esistenti
  rimangono intatti. In precedenza, i file obsoleti venivano eliminati prima ancora di verificare
  se il fetch sarebbe andato a buon fine, causando corruzione silenziosa dello stato.
- **Chiavi mancanti nei return di errore di `scf_install_package`**: tutti i path di ritorno
  (successo, fetch failure, OSError rollback e tutti i guard iniziali) includono ora
  uniformemente `removed_obsolete_files` e `preserved_obsolete_files`. I return anticipati
  restituiscono liste vuote `[]`; il rollback OSError restituisce i valori effettivi poiché
  il diff-cleanup è già avvenuto a quel punto.
- **Import inutilizzato** rimosso da `tests/test_update_diff.py` (`import json`).
- **Nuovi test di regressione** in `tests/test_update_diff.py`:
  - `test_fetch_error_leaves_manifest_intact` — verifica che manifest e disco siano intatti
    se il fetch fallisce.
  - `test_fetch_error_return_has_all_keys` — verifica che il dict di ritorno contenga tutte
    le chiavi richieste anche in caso di fetch failure.

---

## [1.4.0] — 2026-04-02

### Added

- **Diff-based cleanup in `scf_install_package`**: durante un update/reinstall, il motore
  calcola i file presenti nell'installazione corrente ma assenti nel nuovo manifest del pacchetto
  e li rimuove automaticamente. I file modificati dall'utente (SHA mismatch) vengono preservati.
  Il risultato include i nuovi campi `removed_obsolete_files` e `preserved_obsolete_files`.
- **Classificazione tripartita in `verify_integrity`**: i file non tracciati nel manifest
  non sono più raggruppati indiscriminatamente come `orphan_candidates`, ma separati in:
  - `user_files` — file `.md` senza `spark: true` (componenti locali utente, non SCF)
  - `untagged_spark_files` — file `.md` con `spark: true` ma non nel manifest (anomalia)
  - `orphan_candidates` — invariante retrocompatibile, ora = `untagged_spark_files`
- Campo `user_file_count` e `untagged_spark_count` aggiunti al `summary` di `verify_integrity`.
- Campi `user_files` e `untagged_spark_files` propagati automaticamente nel risultato
  di `scf_verify_workspace` (passthrough dal report di `verify_integrity`).

---

## [1.3.2] — 2026-04-02

### Fixed

- Corretto docstring `register_tools()`: aggiornato da `"Register all 22 MCP tools"` a `"Register all 23 MCP tools"` per allinearlo al conteggio reale.
- Rimosso `.github/.scf-registry-cache.json` dal tracking Git (era già in `.gitignore`).
- Aggiunta validazione schema JSON nel workflow `registry-sync-gateway.yml`: lo step verifica campi obbligatori, semver e status validi prima di aprire la PR su `scf-registry`.

---

## [1.3.1] — 2026-03-31

### Added

- Workflow `registry-sync-gateway.yml`: gateway centralizzato per la sincronizzazione automatica di `scf-registry`. Riceve eventi `plugin-manifest-updated` via `repository_dispatch` dai plugin e apre PR su `scf-registry` aggiornando `latest_version` ed `engine_min_version`. È l'unico punto del sistema con accesso diretto al registry (tramite `REGISTRY_WRITE_TOKEN`).

---

## [1.3.0] — 2026-03-31

### Added

- Nuovo tool MCP `scf_verify_system`: verifica la coerenza cross-component tra motore, pacchetti installati e registry (versioni e `min_engine_version`).
- Nuovo file `tests/test_engine_coherence.py`: due test di invariante che verificano l'allineamento contatori tool MCP e l'allineamento `ENGINE_VERSION`/CHANGELOG.

### Fixed

- `scf_remove_package`: aggiunta guard esplicita che restituisce errore descrittivo se il pacchetto non è nel manifest, eliminando il falso positivo silenzioso precedente.
- Allineato il commento `Tools (21)` → `Tools (23)` (era desincronizzato rispetto ai tool effettivi).

---

## [1.2.1] — 2026-03-31

### Fixed

- Rimosso il fallback legacy a `.github/FRAMEWORK_CHANGELOG.md` dal motore.
- `FrameworkInventory.get_package_changelog()` e `scf_get_package_changelog` usano ora solo il path canonico `.github/changelogs/{package_id}.md`.
- Rimossi i test del comportamento legacy deprecato.

## [1.2.0] — 2026-03-30

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

## [1.1.0] — 2026-03-30

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

## [1.0.0] — 2026-02-20

### Initial Release

- Server MCP universale per il SPARK Code Framework
- Discovery dinamico di agenti, skill, istruzioni e prompt da `.github/`
- 14 Resources MCP (agents, skills, instructions, prompts, scf-*) e 11 tool core
- Gestione manifest di installazione con SHA-256 tracking
- Source registry support (pubblico, read-only in v1)
- Tool di installazione, aggiornamento e rimozione di pacchetti SCF
- Parser YAML-style frontmatter con supporto liste inline e block
- Test coverage con unittest (standard library, zero external dependencies)
