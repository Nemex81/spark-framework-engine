# Piano Tecnico - Dual-Mode Manifest v3.1

## Stato validazione proposta

- Check 1.1 - Classificazione file: PASS con adattamenti. `scf-master-codecrafter` dichiara come `workspace_files` solo `.github/copilot-instructions.md` e `.github/instructions/mcp-context.instructions.md`; gli agenti, le skill, `AGENTS-master.md`, changelog e README restano nello store/MCP. `scf-pycode-crafter` dichiara come `workspace_files` solo `.github/copilot-instructions.md`, `.github/instructions/python.instructions.md`, `.github/instructions/tests.instructions.md`; `.github/workflows/notify-engine.yml`, `.github/python.profile.md` e `.github/skills/error-recovery/reference/errors-python.md` sono nel campo `files` ma non in `workspace_files`, quindi sono candidati corretti per `plugin_files`. Nota: gli `AGENTS-*.md` non sono oggi `workspace_files`; sono trattati come risorse package/store o rigenerati dal sistema Phase 6.
- Check 1.2 - Funzioni target: PASS con adattamento path. `_install_workspace_files_v3` e `_install_standalone_files_v3` esistono in `spark/boot/lifecycle.py`, non in `spark/packages/lifecycle.py`. `spark/packages/lifecycle.py` contiene solo helper store/deployment, incluso `_get_deployment_modes`.
- Check 1.3 - Schema manifest attuale: PASS con adattamento. Non esiste `schemas/package-manifest.schema.json`. La compatibilita dei manifest package e verificata da test e parsing JSON permissivo; `tests/test_engine_inventory.py` contiene il controllo schema `3.0` dei manifest reali.
- Check 1.4 - Backward compatibility: PASS con rischio basso. Il codice legge i campi manifest con `.get(...)` e non ci sono validatori strict su campi extra per i package manifest. Rischio concreto: test esistenti che richiedono `schema_version == "3.0"` per i manifest reali devono accettare `3.1`.
- Check 1.5 - Baseline test: PASS. Suite non-live pre-implementazione: `409 passed / 9 skipped / 0 failed / 12 subtests passed`.

## Baseline test

`409 passed / 9 skipped / 0 failed / 12 subtests passed` - 2026-05-08 UTC.

Comando usato tramite task VS Code `pytest-full-suite-non-live`:

```powershell
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

## Adattamenti alla proposta originale

- Il file schema JSON formale non esiste: il Task schema diventa aggiornamento dei test/manifest e della documentazione del formato package manifest.
- Il punto codice non e `spark/packages/lifecycle.py` ma `spark/boot/lifecycle.py`.
- `plugin_files` deve essere considerato anche in rimozione package: se il motore installa file fisici plugin, `scf_remove_package` deve preservarli/rimuoverli con lo stesso preservation gate usato per `workspace_files`.
- `deployment_mode="auto"` deve installare `plugin_files` quando dichiarati, perche il campo e una dichiarazione esplicita di file fisici plugin. `deployment_mode="store"` resta il modo per non scrivere file aggiuntivi oltre al percorso v3 store/workspace minimo gia esistente.
- La chiave deprecata `installed` nel payload v3 deve rappresentare i file fisici scritti nel workspace, deduplicando `workspace_files_written`, `plugin_files_installed` e gli eventuali `standalone_files_written`.
- Per vincoli del workspace, la creazione branch e i commit sono delegati ad Agent-Git. Anomalia AP-GIT-0: Agent-Git ha preparato la ref branch manualmente dopo un tentativo instabile di `git switch`; `.git/HEAD` punta a `refs/heads/feature/dual-mode-manifest-v3.1`.

## Task di implementazione

### Task 1 - Estendere lifecycle v3 con plugin_files

- File: `spark/boot/lifecycle.py`
- Funzione/sezione: `_install_standalone_files_v3`, `_remove_workspace_files_v3`, `_install_package_v3`
- Modifica: leggere `pkg_manifest.get("plugin_files", [])`, installare i plugin file tramite `_install_workspace_files_v3` con manifest sintetico, restituire `plugin_files_installed` e `plugin_files_preserved`, includere gli stessi path nella cleanup di remove e nel payload v3 (`mcp_services_activated`, `installed` alias deprecato).
- Rischio: MEDIO
- Gate test: `pytest tests/test_standalone_files_v3.py tests/test_install_workspace_files.py tests/test_deployment_modes.py -q --tb=short`

### Task 2 - Aggiornare test schema/manifest v3.1

- File: `tests/test_engine_inventory.py`
- Funzione/sezione: `TestManifestSchemaCompatibility`
- Modifica: accettare `schema_version` `3.0` e `3.1`, verificare che `plugin_files` sia opzionale e lista quando presente.
- Rischio: BASSO
- Gate test: `pytest tests/test_engine_inventory.py -q --tb=short`

### Task 3 - Aggiornare manifest package embedded engine

- File: `packages/scf-master-codecrafter/package-manifest.json`
- Funzione/sezione: root manifest
- Modifica: `schema_version` a `3.1`, aggiungere `plugin_files: []`.
- Rischio: BASSO
- Gate test: `pytest tests/test_engine_inventory.py -q --tb=short`

### Task 4 - Aggiornare manifest scf-master-codecrafter workspace

- File: `../scf-master-codecrafter/package-manifest.json`
- Funzione/sezione: root manifest
- Modifica: `schema_version` a `3.1`, aggiungere `plugin_files: []`.
- Rischio: BASSO
- Gate test: controllo JSON manuale + `pytest tests/test_engine_inventory.py -q --tb=short` dal repo engine

### Task 5 - Aggiornare manifest scf-pycode-crafter embedded e workspace

- File: `packages/scf-pycode-crafter/package-manifest.json`
- File: `../scf-pycode-crafter/package-manifest.json`
- Funzione/sezione: root manifest
- Modifica: `schema_version` a `3.1`, aggiungere `plugin_files` con `.github/workflows/notify-engine.yml`, `.github/python.profile.md`, `.github/skills/error-recovery/reference/errors-python.md`. Lasciare `workspace_files` limitato agli editor-binding stretti gia presenti.
- Rischio: BASSO
- Gate test: controllo JSON manuale + `pytest tests/test_engine_inventory.py tests/test_standalone_files_v3.py -q --tb=short`

### Task 6 - Aggiornare documentazione correlata

- File: `docs/TODO.md`, `README.md`, `docs/getting-started.md`, `docs/REFACTORING-DESIGN.md`
- Funzione/sezione: sezioni package install/manifest/deployment pertinenti
- Modifica: sostituire TODO sessione corrente; aggiungere note concise su MCP Service Mode, Plugin Mode e `plugin_files` senza riscrivere sezioni non correlate.
- Rischio: BASSO
- Gate test: controllo manuale Markdown + suite finale non-live

### Task 7 - Creare report finale implementazione

- File: `docs/reports/SPARK-REPORT-DualMode-Implementation-v1.0.md`
- Funzione/sezione: nuovo report
- Modifica: riepilogare modifiche, test baseline/intermedi/finale, adattamenti e anomalie.
- Rischio: BASSO
- Gate test: controllo manuale presenza sezioni richieste + suite finale non-live

## Anomalie parallele

- AP-GIT-0: branch preparato da Agent-Git con scrittura manuale di `.git/refs/heads/feature/dual-mode-manifest-v3.1` e `.git/HEAD` dopo tentativo instabile di `git switch`. Non blocca l'implementazione; richiede verifica finale dello stato branch da Agent-Git prima dei commit/review.
- AP-SCHEMA-0: `schemas/package-manifest.schema.json` non esiste. La compatibilita viene garantita da parsing permissivo e test `tests/test_engine_inventory.py`.
- AP-DOC-0: README contiene una descrizione bootstrap storica che parla di prompt copiati nel workspace; se toccata, va aggiornata solo nella porzione pertinente.

## Ordine di esecuzione

1. Task 1 - lifecycle v3 con `plugin_files` e payload response.
2. Task 2 - test schema/manifest v3.1.
3. Task 3 - manifest embedded `scf-master-codecrafter`.
4. Task 5 - manifest embedded `scf-pycode-crafter` e test plugin file.
5. Task 4 e parte workspace di Task 5 - manifest nei repository secondari, se il perimetro operativo lo consente.
6. Task 6 - documentazione e TODO.
7. Task 7 - report finale.
8. Gate finale non-live completo.
9. Delegare ad Agent-Git i commit atomici richiesti, uno per gruppo logico, senza push.

## Criteri di accettazione finale

- `plugin_files` e opzionale e sempre letto con `.get("plugin_files", [])`.
- Manifest v3.0 privi di `plugin_files` continuano a installare senza errori.
- `scf_install_package` v3 espone `mcp_services_activated`, `workspace_files_written`, `plugin_files_installed` e mantiene `installed` come alias deprecato.
- I plugin fisici installati vengono rimossi/preservati da `scf_remove_package` con lo stesso preservation gate dei `workspace_files`.
- Nessuna modifica diretta a `WorkspaceWriteGateway` o `ManifestManager`.
- Nessun `print()` stdout aggiunto nei file Python modificati.
- Baseline finale non-live: passed >= 409 e failed = 0.
- Manifest di `scf-master-codecrafter` e `scf-pycode-crafter` aggiornati a `schema_version: "3.1"` dove consentito dal perimetro.
- `docs/TODO.md` e report finale creati/aggiornati.
