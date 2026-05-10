# Report P2-Audit — Plugin Architecture Gap Resolution

## Metadata

- Data: 2026-05-09 UTC
- Branch: feature/dual-mode-manifest-v3.1
- Gap risolti: P2-A (scf_get_plugin_info), P2-B (dualita famiglie plugin)
- Strategia: P2-A Opzione C, P2-B Scenario Beta

## Mappa tool plugin (post-audit)

| Tool | Famiglia | Store | Tracking | File sorgente | Stato finale |
| ------ | ---------- | ------- | ---------- | --------------- | -------------- |
| `scf_plugin_install` | PluginManagerFacade | No engine store | Si, ManifestManager + PluginRegistry | `spark/boot/tools_plugins.py` | Target lifecycle |
| `scf_plugin_remove` | PluginManagerFacade | No engine store | Si, ManifestManager + PluginRegistry | `spark/boot/tools_plugins.py` | Target lifecycle |
| `scf_plugin_update` | PluginManagerFacade | No engine store | Si, ManifestManager + PluginRegistry | `spark/boot/tools_plugins.py` | Target lifecycle |
| `scf_plugin_list` | PluginManagerFacade | No engine store | Legge installati + registry remoto | `spark/boot/tools_plugins.py` | Target listing |
| `scf_get_plugin_info` | Plugin metadata | No write | Read-only | `spark/boot/tools_plugins.py` | Nuovo tool target |
| `scf_list_plugins` | Direct Dual-Mode | No | No | `spark/boot/tools_plugins.py` | Deprecated compat |
| `scf_install_plugin` | Direct Dual-Mode | No | No | `spark/boot/tools_plugins.py` | Deprecated compat |

## Strategia adottata

### P2-A

Opzione scelta: **C — aggiungere `scf_get_plugin_info`**.

`scf_list_plugins` restituiva solo le entry del registry filtrate con
`delivery_mode != "mcp_only"`. Questi dati includono normalmente `id`,
`description`, `latest_version`, `repo_url`, `status`, `min_engine_version` e
campi eventuali del registry, ma non scaricano il `package-manifest.json`.
Di conseguenza non garantivano dettagli come `dependencies` e `plugin_files`.

`scf_get_package_info` funziona solo parzialmente per un ID plugin: legge la
stessa entry registry e scarica il manifest remoto, ma interpreta il payload
come pacchetto store-based. In particolare calcola `file_count`, `categories` e
`files` dal campo `files`, mentre i plugin workspace dichiarano `plugin_files`.
Per l'esperienza utente risultava quindi informativo ma non semanticamente
corretto.

La soluzione minima senza refactor ampio e' stata aggiungere
`scf_get_plugin_info(plugin_id)`, read-only, con sorgente dati coerente con
`scf_list_plugins`: registry filtrato per plugin installabili e manifest remoto
del plugin. Il payload espone `name`, `description`, `version`, `dependencies`,
`source_url`, `min_engine_version`, compatibilita engine e `plugin_files`.

### P2-B

Scenario identificato: **Beta — PluginManagerFacade e' l'evoluzione, il
download diretto e' legacy compat**.

Il design `SPARK-DESIGN-FullDecoupling-v2.0` definisce due universi:

- Universo A: pacchetti interni MCP, serviti dall'engine, non installati o
  aggiornati nel workspace utente.
- Universo B: plugin workspace esterni, scritti in `.github/` e gestiti dal
  Plugin Manager.

Nel codice reale esistono due percorsi:

- `scf_plugin_*` delega a `PluginManagerFacade`, scrive file nel workspace e
  registra ownership file-level in `ManifestManager` piu stato package-level in
  `PluginRegistry`.
- `scf_list_plugins` e `scf_install_plugin` delegano a
  `spark.plugins.manager`, scaricano direttamente in `.github/` e non
  registrano nulla nel manifest o nel registry plugin locale.

Il secondo percorso resta utile per compatibilita, ma non soddisfa il target di
decoupling perche lascia file non tracciati. Per questo e' stato marcato come
deprecated e documentato con rimozione prevista al 2026-06-30.

### Interdipendenza P2-A ↔ P2-B

La scelta Beta non elimina il bisogno di un tool informativo dedicato. Anzi,
lo rende piu chiaro: il lifecycle ordinario deve usare `scf_plugin_*`, mentre
la consultazione dettagliata prima dell'installazione passa da
`scf_get_plugin_info`. Il nuovo tool non installa, non aggiorna e non scrive
file: colma il gap narrativo P2-A senza rafforzare il percorso direct-download
legacy.

### Impatto agenti

L'asset embedded `packages/spark-base/.github/agents/spark-assistant.agent.md`
era ancora `version: 1.0.0`, non `1.1.0` post-P2. E' stato aggiornato
direttamente a `version: 1.2.0` e `scf_version: "1.7.3"`, aggiungendo la sezione
"Presentazione e primo orientamento" allineata alla famiglia tracked:
`scf_plugin_list`, `scf_get_plugin_info`, `scf_plugin_install`,
`scf_plugin_update`, `scf_plugin_remove`.

Non sono stati modificati `AGENTS.md` o `spark-guide.agent.md`: per lo scenario
Beta il task richiedeva l'allineamento diretto di `spark-assistant`; la
razionalizzazione piu ampia del naming resta backlog.

## File modificati

| File | Tipo | Righe + | Righe - |
| ------ | ------ | --------- | --------- |
| `docs/SPARK-DESIGN-FullDecoupling-v2.0.md` | Docs design | 16 | 0 |
| `packages/spark-base/.github/agents/spark-assistant.agent.md` | Agent asset | 36 | 2 |
| `spark/boot/engine.py` | Engine comment/docstring | 2 | 2 |
| `spark/boot/tools_plugins.py` | Tool MCP | 124 | 15 |
| `tests/test_plugin_manager_integration.py` | Test | 91 | 0 |
| `docs/reports/SPARK-REPORT-P2-PluginAudit-v1.0.md` | Report | 113 | 0 |

## Anomalie gestite durante l'implementazione

- **BLOCK-SOFT — asset agente embedded non allineato al prompt.** Il prompt
  indicava `packages/spark-base/.github/agents/spark-assistant.agent.md` come
  versione 1.1.0 post-P2, ma nel repo motore era ancora 1.0.0 e privo della
  sezione "Presentazione e primo orientamento". Soluzione: rivalutazione sul
  file reale e aggiornamento diretto a 1.2.0 entro il perimetro engine.
- **BLOCK-SOFT — sintassi test durante patch.** Un tentativo di inserimento del
  test ha lasciato incompleta la firma `FakeMCP.tool`. Il gate `py_compile` lo
  ha intercettato; la firma e' stata corretta e i test sono stati rilanciati.
- **OBSERVATION — placeholder report.** Il file report e' stato creato vuoto
  come placeholder e subito popolato con questo contenuto tramite patch.

## Backlog aperto (azioni non eseguite in questo task)

- Decidere se rinominare in futuro la famiglia target da `scf_plugin_*` a
  `scf_*_plugin` per allinearla al naming del design v2.0. Non eseguito ora per
  evitare breaking change sui tool gia registrati.
- Applicare la stessa narrativa a eventuali repository pacchetto esterni fuori
  dal perimetro `spark-framework-engine`, se necessario. Questo task opera solo
  sull'asset embedded del motore.
- Rimozione effettiva di `scf_list_plugins` e `scf_install_plugin` dopo la
  finestra di deprecazione documentata.

## Checklist finale

- [x] Nessun print() introdotto
- [x] Tutti i tool nuovi registrati correttamente
- [x] Docstring Google Style presenti
- [x] Markdownlint: tutti i .md modificati puliti
- [x] spark-framework-engine.py importa correttamente i moduli
- [x] Nessuna sovrapposizione non dichiarata con altri tool

## Verifica tecnica

- `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m py_compile spark/boot/tools_plugins.py tests/test_plugin_manager_integration.py`: PASS
- `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/test_plugin_manager_integration.py -q --tb=short`: PASS, 8 passed
- `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m py_compile spark-framework-engine.py spark/boot/engine.py spark/boot/tools_plugins.py tests/test_plugin_manager_integration.py`: PASS
- `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/test_plugin_manager_integration.py tests/test_engine_coherence.py tests/test_smoke_bootstrap_v3.py -q --tb=short`: PASS, 15 passed, 2 skipped
- `C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py`: PASS, 454 passed, 9 skipped, 12 subtests passed
- `git diff --check` sui file modificati: PASS
