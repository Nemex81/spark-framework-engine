# Changelog

Tutte le modifiche importanti a questo progetto sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com) e il versioning segue [Semantic Versioning](https://semver.org).

---

## [2.3.2] - 2026-04-21

### Changed

- `.github/copilot-instructions.md` del motore convertito da file single-owner a file condiviso canonico con marker `<!-- SCF:BEGIN:{package}@{version} -->` / `<!-- SCF:END:{package} -->`, con sezioni per `spark-framework-engine@2.3.1`, `spark-base@1.2.0`, `scf-master-codecrafter@2.1.0` e `scf-pycode-crafter@2.0.1`, ordinate per `scf_merge_priority` (0 → 10 → 20 → 30).
- File `.github/` del motore classificati esplicitamente per ownership: file nativi engine taggati con `scf_owner: "spark-framework-engine"`; 10 file shadow di `spark-base` (`spark-guide.agent.md` e i 9 prompt `scf-*.prompt.md`) riallineati al contenuto del pacchetto sorgente con `scf_owner: "spark-base"`.
- README riallineato: la sezione `## Migrazione Da Workspace Pre-Ownership` e' stata spostata fuori dal blocco codice di `## Tools Disponibili (35)` per ripristinare una struttura markdown coerente con i contenuti runtime documentati.

### Notes

- Nessuna modifica al codice Python del motore. Release di governance `.github/` e normalizzazione ownership degli asset installati.

---

## [2.3.1] - 2026-04-19

### Fixed

- `scf_verify_workspace()` non segnala piu' come `duplicate_owners` i file condivisi intenzionalmente tra piu' pacchetti quando tutte le entry del manifest usano `scf_merge_strategy: merge_sections`.
- Il manifest runtime riallinea ora hash e merge strategy delle entry condivise dopo install, update, finalize e remove di file `merge_sections`, evitando falsi `modified` sui package owner residui.

---

## [2.3.0] - 2026-04-19

### Added

- `scf_get_update_policy()` e `scf_set_update_policy()` per leggere e persistare la policy update del workspace in `.github/runtime/spark-user-prefs.json`.
- `diff_summary`, `authorization_required`, `github_write_authorized` e `backup_path` nei payload pubblici dei flussi install/update quando entra in gioco il sistema di policy del workspace.
- Estensione di `scf_bootstrap_workspace(..., update_mode="")` con handshake iniziale di policy, preview diff per `spark-base` e gate esplicito per le scritture protette in `.github/`.

### Changed

- `scf_install_package(package_id, conflict_mode, update_mode)` e `scf_update_package(package_id, conflict_mode, update_mode)` risolvono ora il comportamento package-level tramite `mode_per_package`, `mode_per_file_role` e `default_mode`, mantenendo invariato il flusso legacy se il workspace non ha ancora una policy esplicita.
- I file `merge_sections` usano ora in scrittura `_scf_section_merge()` come path canonico, mentre i file `user_protected` continuano a essere delegati senza fetch o overwrite impliciti.
- README, copilot instructions, skill e prompt del motore descrivono ora il flusso ownership-aware in 6 step, le modalita `integrative` / `replace` / `conservative` / `selective` e il ruolo del bootstrap esteso.

### Notes

- Release minor: consolida le feature OWN-B, OWN-C, OWN-D, OWN-E e OWN-F in una versione documentata e pronta per il rollout, senza introdurre breaking change sui tool legacy.

---

## [2.2.1] - 2026-04-17

### Fixed
- Rimossa chiave legacy `engine_min_version` dall'output di `_plan_package_updates`.
  La chiave canonica `min_engine_version` è l'unico output corretto per i tool
  `scf_check_updates` e `scf_update_packages`.

---

## [2.2.0] - 2026-04-17

### Removed
- `scf_get_package_info`: rimosso il campo legacy `engine_min_version` dall'output.
  Il campo canonico è `min_engine_version`. Breaking change dell'output del tool.
  La funzione interna `_get_registry_min_engine_version` mantiene ancora il fallback
  in lettura del campo legacy per compatibilità con cache locali non ancora aggiornate.

---

## [2.1.3] — 2026-04-17

### Changed

- Il registry usa ora `min_engine_version` come campo canonico anche nel workflow di sincronizzazione automatica, mantenendo nel motore la compatibilita' in lettura del legacy `engine_min_version`.

### Fixed

- `MergeEngine` calcola ora `start_line` e `end_line` dei conflitti sulla base del contesto realmente condiviso da `base`, `ours` e `theirs`, evitando coordinate sfalsate quando il testo base diverge.

---

## [2.1.2] — 2026-04-17

### Changed

- `scf_apply_updates(package_id | None, conflict_mode)` inoltra ora davvero il `conflict_mode` al batch update invece di forzare sempre `replace`.
- `scf_bootstrap_workspace(install_base=True, conflict_mode)` inoltra il mode scelto all'installazione di `spark-base` durante il bootstrap MCP.
- `spark-init.py` chiede ora una scelta esplicita `replace` / `preserve` / `integrate` quando trova file gia presenti nel primo bootstrap standalone di `spark-base`.

### Fixed

- `conflict_mode="replace"` sovrascrive ora anche i file tracciati e modificati che prima cadevano sempre sul ramo di preservazione implicita.
- Allineata la documentazione runtime e i prompt operativi al nuovo comportamento di bootstrap e update batch.

---

## [2.1.1] — 2026-04-15

### Changed

- `scf_bootstrap_workspace(install_base=True)` puo' ora completare il bootstrap MCP e tentare subito l'installazione gestita di `spark-base`, saltando il passo se il pacchetto e gia installato.
- `spark-init.py` sostituisce il bootstrap hard-coded con un installer embedded di `spark-base`, aggiornando `.github/.scf-manifest.json` e riducendo lo stdout al solo riepilogo finale.
- README allineato al bootstrap embedded di `spark-init.py`, al manifest runtime e al nuovo riepilogo in 3 righe.

### Fixed

- Aggiornata la cache locale del registry bundlata con il motore al formato `2.0` e all'inventario pacchetti corrente.
- Allineato `scf-pycode-crafter` a `engine_min_version: 2.1.0` nel registry per riflettere la dipendenza effettiva dalla chain `spark-base -> scf-master-codecrafter -> scf-pycode-crafter`.

### Notes

- Il registry pubblico e il manifest remoto di `spark-base` risultano ancora disallineati sulla versione pubblicata; `spark-init.py` usa il manifest remoto reale e segnala la discrepanza su `stderr`.

---

## [2.1.0] — 2026-04-15

### Added

- Adozione dei file bootstrap da parte dei pacchetti installabili: `spark-base` puo' ora rilevare e assorbire in modo sicuro `spark-guide.agent.md` gia' tracciato da `scf-engine-bootstrap`.

### Changed

- `scf_install_package(package_id, conflict_mode)` rimuove l'ownership bootstrap superata quando `spark-base` installa file gia' bootstrap-pati e puliti.
- `scf_bootstrap_workspace()` evita di ri-registrare nel manifest bootstrap file gia' posseduti da un pacchetto SCF non-bootstrap.

### Notes

- Versione minor per supportare la promozione di `spark-guide` dentro `spark-base` senza conflitti di ownership nei workspace gia' inizializzati.

---

## [2.0.0] — 2026-04-14

### Added

- Sistema di merge a 3 vie per file markdown: snapshot BASE, versione utente e nuova versione pacchetto vengono combinati da `MergeEngine` con percorsi `manual`, `auto` e `assisted`.
- `conflict_mode: "manual"` — apre una sessione stateful e scrive i marker di conflitto nel file finche' l'utente non li risolve e chiude la sessione con `scf_finalize_update`.
- `conflict_mode: "auto"` — tenta una risoluzione best-effort deterministica tramite `scf_resolve_conflict_ai`; se il caso non e sicuro o i validator falliscono, degrada esplicitamente a `manual`.
- `conflict_mode: "assisted"` — apre una sessione stateful, conserva i marker sul file e permette di proporre, approvare o rifiutare una risoluzione per singolo conflitto.
- `scf_finalize_update(session_id)` — finalizza una sessione di merge chiudendola e applicando le decisioni confermate al manifest e ai file del workspace.
- `scf_resolve_conflict_ai(session_id, conflict_id)` — propone automaticamente una risoluzione conservativa per un singolo conflitto in una sessione attiva.
- `scf_approve_conflict(session_id, conflict_id)` — approva la risoluzione proposta per un conflitto, marcandolo come risolto nella sessione.
- `scf_reject_conflict(session_id, conflict_id)` — rifiuta la risoluzione proposta per un conflitto, mantenendo la versione utente corrente.
- Validator post-merge: verifica strutturale, completezza heading e coerenza del blocco `tools:` per i file `.agent.md`.
- Policy multi-owner `extend` e `delegate`: gestione di file condivisi tra più pacchetti con regole di ownership esplicite e risoluzione conflitti cross-package.

### Changed

- `scf_install_package(package_id, conflict_mode)` supporta ora i nuovi valori `"manual"`, `"auto"` e `"assisted"` in aggiunta ai precedenti `"abort"` e `"replace"`. Il default rimane `"abort"`.
- `scf_plan_install(package_id)` restituisce ora anche l'anteprima del piano di merge quando il `conflict_mode` richiesto e un merge mode.
- `scf_update_package(package_id, conflict_mode)` propaga il `conflict_mode` alla pipeline di merge durante l'aggiornamento del pacchetto.
- `ManifestManager` permette ora ownership multiple sullo stesso file quando il package differisce, abilitando il modello multi-owner con policy per-file.
- `ENGINE_VERSION` aggiornato a `2.0.0`.

### Notes

- Versione major per cambio architetturale: introduzione `MergeEngine`, sessioni stateful e policy multi-owner rappresentano un'estensione dell'interfaccia MCP non retrocompatibile con motori `< 2.0.0` per i nuovi `conflict_mode`.
- `scf_cleanup_sessions` resta helper interno e non e esposto come tool MCP pubblico.
- Il numero totale di tool registrati passa da 29 a 33.

---

## [1.9.0] — 2026-04-13

### Added

- `scf_plan_install(package_id)` — dry-run tool per classificare i target di installazione prima di qualsiasi scrittura e mostrare write plan, preserve plan e conflict plan.

### Changed

- `scf_install_package(package_id, conflict_mode="abort")` blocca di default i conflitti su file esistenti non tracciati e richiede un opt-in esplicito `replace` per sovrascriverli.
- `scf_apply_updates()` esegue ora un preflight su tutti i package target prima della prima scrittura del batch, fermandosi se rileva conflitti irrisolti.
- `scf_update_package(package_id)` propaga i conflitti di preflight restituiti dal flusso di update.
- `spark-guide.agent.md` torna coerente con i tool realmente dichiarati nel frontmatter.

### Fixed

- Corretto il rischio di overwrite silenzioso su file `.github/` pre-esistenti ma non tracciati dal manifest durante installazione e update.
- Corretta la documentazione del registry: il manifest consumer canonico usa `entries[]`, non `installed_packages[]`.
- Allineata la documentazione del bootstrap MCP al set asset realmente copiato da `scf_bootstrap_workspace()`.

---

## [1.8.2] — 2026-04-12

### Added

- `spark-assistant v1.0.0` — agente utente finale per onboarding, gestione pacchetti e diagnostica workspace. Sostituisce il placeholder precedente.
- `spark-guide v1.0.0` — agente di orientamento user-facing nel repo engine; interpreta richieste in linguaggio naturale e instrada le operazioni concrete verso `spark-assistant` o `spark-engine-maintainer`.

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
