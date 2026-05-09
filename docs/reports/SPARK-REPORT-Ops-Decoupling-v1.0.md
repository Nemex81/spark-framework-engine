# SPARK Report - Disaccoppiamento spark-base -> spark-ops v1.0

## Sintesi Esecutiva

Il ciclo ha trasformato la proposta iniziale in una separazione implementata e
validata tra layer base e layer operativo:

- `spark-base` diventa il package fondazionale user-facing/shared, versione
  `2.0.0`.
- `spark-ops` nasce come package MCP-only operativo, versione `1.0.0`.
- `scf-master-codecrafter` dipende ora da `spark-base >= 2.0.0` e
  `spark-ops >= 1.0.0`, versione `2.7.0`.
- `scf-pycode-crafter` dipende ora da `scf-master-codecrafter >= 2.7.0`,
  versione `2.3.0`.

La modifica e non distruttiva: i file legacy presenti fisicamente in
`packages/spark-base/.github/` non sono stati eliminati. Sono stati rimossi dal
catalogo distribuito nel manifest, lasciando la cancellazione fisica a un
eventuale passaggio esplicitamente autorizzato.

## Ciclo Strategia

La strategia originale `spark-base -> spark-engine` e stata respinta per rischio
di collisione terminologica con `spark-framework-engine` e per possibili
dipendenze inverse. La strategia corretta usa `spark-ops` come layer operativo:

- dipendenza monodirezionale: `spark-ops` dipende da `spark-base`;
- nessuna dipendenza di `spark-base` verso `spark-ops`;
- stesso universo MCP-only, quindi nessun cambio di transport o signature tool;
- scope ristretto alle risorse operative realmente separabili.

Sono rimasti in `spark-base` i componenti condivisi o necessari a fallback e
policy base: `Agent-Research`, `framework-unlock`, `git-execution`,
`rollback-procedure`, `framework-scope-guard`, `semver-bump` e skill correlate.

## Implementazione

Creato `packages/spark-ops/` con:

- agenti `Agent-Orchestrator`, `Agent-FrameworkDocs`, `Agent-Release`;
- prompt `orchestrate`, `release`, `framework-update`, `framework-changelog`,
  `framework-release`;
- skill `semantic-gate`, `error-recovery`, `task-scope-guard`;
- `package-manifest.json`, README, AGENTS e changelog dedicati.

Aggiornato `packages/spark-base/package-manifest.json` per rimuovere dal catalogo
MCP le risorse migrate. I conteggi finali sono:

| Package | Versione | Agenti | Prompt | Skill |
| --- | --- | ---: | ---: | ---: |
| `spark-base` | `2.0.0` | 10 | 25 | 20 |
| `spark-ops` | `1.0.0` | 3 | 5 | 3 |

Aggiornati documentazione, changelog e README correlati:

- root `README.md`, `docs/architecture.md`, `CHANGELOG.md`, `docs/todo.md`;
- README/changelog dei package `spark-base`, `spark-ops`,
  `scf-master-codecrafter`, `scf-pycode-crafter`;
- `packages/spark-base/.github/AGENTS.md`, prompt README e `agent-selector`.

## Revisione Post

Controlli eseguiti:

- validazione JSON di tutti i manifest in `packages/*/package-manifest.json`;
- test mirato `tests/test_spark_ops_decoupling_manifest.py`;
- suite non-live completa;
- diagnostica VS Code mirata sui nuovi file `spark-ops`, sul test e sui documenti
  corretti.

Risultati finali:

```text
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/test_spark_ops_decoupling_manifest.py -q
4 passed in 0.03s

C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py
550 passed, 9 skipped, 12 subtests passed in 6.27s
```

Durante la revisione e stato intercettato un BOM UTF-8 introdotto da una
normalizzazione PowerShell su `spark-ops/package-manifest.json`. Il test mirato ha
fallito correttamente, il BOM e stato rimosso con scrittura UTF-8 senza BOM, e la
suite completa e stata rieseguita con esito PASS.

## Ottimizzazioni Consigliate

1. Aggiungere una procedura di clean-up opzionale per file legacy non referenziati
   dal manifest, protetta da conferma esplicita `ELIMINA`.
2. Introdurre un test di packaging che fallisca se un package MCP-only contiene
   file con BOM nei manifest JSON.
3. Valutare una policy di lint dedicata ai changelog package, dove heading come
   `Added` e `Changed` sono volutamente ripetuti per versione.
4. Aggiornare eventuali repository sorgente esterni a `spark-framework-engine`
   solo tramite task separato e perimetro esplicitamente autorizzato.

## Prossimi Passi

1. Delegare ad Agent-Git o all'utente la preparazione dei commit atomici.
2. Valutare, in un task separato, la rimozione fisica dei file legacy non piu
   referenziati da `spark-base`, con conferma `ELIMINA`.
3. Eseguire una verifica install/update su workspace temporaneo per simulare
   catena `spark-base -> spark-ops -> scf-master-codecrafter -> scf-pycode-crafter`.
