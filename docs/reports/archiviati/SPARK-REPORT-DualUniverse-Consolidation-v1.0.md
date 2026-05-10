# SPARK — Report Consolidamento Dual-Universe v1.0

| Campo | Valore |
|-------|--------|
| Data esecuzione | 2026-05-09 |
| Branch | `feature/dual-mode-manifest-v3.1` |
| Coordinatore | Perplexity AI / Nemex81 |
| Esecutore | Claude Opus 4.7 (Copilot Agent Mode, modalita `spark-engine-maintainer`) |
| Documento di partenza | `docs/reports/rapporto perplexity - audit-system-state-v1.0.md` |
| Stato finale | VERDE (post-fix) |

---

## 1. Sintesi Esecutiva

L'audit Perplexity ha identificato 6 punti di verifica (V1-V6) sul
disaccoppiamento Universo A (pacchetti interni `mcp_only`) vs Universo B
(plugin esterni installabili). L'esecuzione di questo task ha:

1. Confermato lo stato VERDE su V1, V3, V4 (gia coperti da fix
   precedenti del branch `feature/dual-mode-manifest-v3.1`).
2. Riclassificato V2 da CRITICO a MEDIO sulla base dell'analisi
   statica del punto di entry FastMCP.
3. Colmato i gap V5 (narrativa dual-universe per l'utente finale)
   e V6 (zero copertura test su `OnboardingManager`).
4. Scoperto e risolto **una nuova anomalia bloccante** non presente
   nel rapporto Perplexity: `OnboardingManager` falliva silenziosamente
   ad ogni esecuzione per un import path errato.

Tutte le modifiche sono confinate a:

- `spark/boot/onboarding.py` (1 riga)
- `spark/boot/tools_plugins.py` (4 return + 1 costante modulo)
- `packages/spark-base/.github/agents/spark-assistant.agent.md` (sezione)
- `tests/test_onboarding_manager.py` (file nuovo)
- `CHANGELOG.md` (sezione `[Unreleased]`)
- `docs/reports/SPARK-REPORT-DualUniverse-Consolidation-v1.0.md`
  (questo report)

Nessuna modifica al motore `spark-framework-engine.py`. Nessuna
modifica all'ownership dei file `.github/` del repository engine
(`framework_edit_mode: false` rispettato).

---

## 2. Stato Disaccoppiamento Universo A / Universo B

| Aspetto | Universo A (pacchetti interni) | Universo B (plugin workspace) |
|---------|--------------------------------|-------------------------------|
| Distribuzione | Engine store (`packages/`) | Registry GitHub (`scf-registry`) |
| Installazione | Automatica (bootstrap MCP) | Esplicita (`scf_plugin_install`) |
| Ownership file | Engine (`mcp_only: true`) | Workspace utente (`.github/`) |
| Tool primari | `scf_list_installed_packages`, `scf_get_package_info` | `scf_plugin_*` (store-based) |
| Tool legacy | n/a | `scf_list_plugins`, `scf_install_plugin` (deprecati) |
| Esempi | `spark-base` | `scf-master-codecrafter`, `scf-pycode-crafter` |

Il disaccoppiamento e oggi **completo a livello tecnico**. Le
osservazioni di consolidamento riguardavano principalmente:

- coerenza UX (V5: la documentazione utente non spiegava la differenza)
- segnalazione UX (P2.1: i tool legacy non erano marcati `deprecated` nel
  payload JSON, solo nella docstring)
- robustezza (V6: zero test sul percorso di onboarding)

Tutti questi punti sono stati indirizzati in questo task.

---

## 3. Punti di Verifica V1-V6

### V1 — Boot perimeter rispetta ownership

**Stato: VERDE.** `_v3_repopulate_registry` al boot espone i pacchetti
interni via MCP senza copiare file nel workspace. `bootstrap_targets`
include solo i file esplicitamente dichiarati in
`packages/spark-base/package-manifest.json` `workspace_files` + 3
sentinelle. Nessuna regressione rilevata.

### V2 — `asyncio.run` in `ensure_minimal_bootstrap`

**Stato originale (Perplexity): CRITICO.** Speculato rischio di
`RuntimeError` se l'event loop FastMCP fosse gia attivo.

**Stato riclassificato: MEDIO.** Analisi del punto di entry
`spark-framework-engine.py` riga 196:

```python
_build_app(engine_root=Path(__file__).resolve().parent).run(transport="stdio")
```

`_build_app()` viene risolto e ritorna l'istanza FastMCP **prima** che
`.run(transport="stdio")` avvii il proprio event loop. Tutte le
chiamate `asyncio.run()` interne a `_build_app()` (incluso
`ensure_minimal_bootstrap`) operano in una finestra in cui non esiste
event loop attivo. Il `try/except RuntimeError` difensivo gia presente
e quindi corretto come hardening. Nessun fix necessario.

### V3 — Nessun pacchetto `mcp_only` finisce nel workspace

**Stato: VERDE.** `_install_workspace_files_v3` filtra esclusivamente
`workspace_files` di Categoria A. I file `mcp_only` non vengono mai
trasferiti.

### V4 — Tool plugin store-based hanno tracking corretto

**Stato: VERDE.** `PluginManagerFacade` aggiorna
`.github/.spark-plugins` in ogni operazione (install/update/remove) e
gestisce il preservation gate per i file modificati dall'utente.

### V5 — Gap narrativa Universo A vs B all'utente finale

**Stato originale: GIALLO.** Il file
`packages/spark-base/.github/agents/spark-assistant.agent.md`
delegava ogni spiegazione a `spark-guide`, ma non esisteva un punto
unico in cui l'utente leggesse "esistono due famiglie di
estensioni e si gestiscono diversamente".

**Stato post-fix: VERDE.** Aggiunta sezione
"Architettura — pacchetti interni vs plugin workspace" prima del
"Flusso A — Onboarding workspace vergine". Tabella comparativa
breve, nessun bump di versione del frontmatter (modifica di
contenuto descrittivo, non di interfaccia).

### V6 — Zero copertura test su `OnboardingManager`

**Stato originale: ROSSO.** `spark/boot/onboarding.py` non aveva test
diretti. Il bug descritto al punto 4 di questo report e stato
scoperto **proprio scrivendo i test richiesti dal gap V6**.

**Stato post-fix: VERDE.** Creato `tests/test_onboarding_manager.py`
con 17 test unitari che coprono tutti i percorsi pubblici di
`OnboardingManager`:

- `is_first_run` (7 casi)
- `_install_declared_packages` (7 casi)
- `run_onboarding` (3 casi: `completed`, `partial`, `skipped`)

Tutti i test passano. Pattern fixture: `MagicMock` per
`SparkFrameworkEngine` e `FrameworkInventory`, `WorkspaceContext`
reale + `ManifestManager` reale popolato via helper `_seed_manifest`.

---

## 4. Anomalie Rilevate

### ANOMALIA-NEW (NON nel rapporto Perplexity) — `OnboardingManager` import path errato

**Severita: ALTA (effettivamente bloccante in produzione).**

**Sintomo.** Ad ogni esecuzione di
`OnboardingManager.run_onboarding()`, il log riportava:

```
[SPARK-ENGINE][WARNING] Store population step error:
  No module named 'spark.packages.store'
```

E lo stato finale era sempre `status: "partial"`, anche su workspace
che avrebbero dovuto chiudere `completed`.

**Causa.** `spark/boot/onboarding.py` importava
`PackageResourceStore` da `spark.packages.store`, ma la classe e
definita in `spark.registry.store` (verificato con `grep_search`:
unica definizione a `spark/registry/store.py:28`).

**Fix.** Una riga, import path corretto, con commento esplicativo
breve. Nessuna modifica all'API pubblica.

**Impatto pre-fix.** Onboarding tecnicamente funzionava (nessuna
eccezione propagata) ma il segnale di stato all'utente era falso
("parziale" anziche "completato"). Probabilmente mascherato finora
perche i test integrazione live sono `--ignore`d nel comando di
regressione standard.

### V2 — `asyncio.run` defensive guard

Vedi sezione 3, punto V2. Riclassificato MEDIO. Nessun fix.

### P2.1 — Tool legacy senza marker `deprecated` nel payload

**Severita: MEDIA.**

**Sintomo.** I tool `scf_list_plugins` e `scf_install_plugin` erano
marcati DEPRECATED solo nella docstring. Copilot/agenti che leggono
il payload JSON non avevano segnale forte per preferire i tool
store-based equivalenti.

**Fix.** Aggiunta costante `_LEGACY_DEPRECATION_NOTICE` in
`spark/boot/tools_plugins.py`. Tutti i 4 return blocks (success +
error per ciascuno dei 2 tool) ora includono:

```python
"deprecated": True,
"deprecation_notice": _LEGACY_DEPRECATION_NOTICE,
```

Nessuna modifica firma. Aggiunta non-breaking.

---

## 5. File Modificati

| File | Tipo | Note |
|------|------|------|
| `spark/boot/onboarding.py` | Fix | Import path `PackageResourceStore` |
| `spark/boot/tools_plugins.py` | Add | Costante + 4 augment `deprecated` |
| `packages/spark-base/.github/agents/spark-assistant.agent.md` | Add | Sezione dual-universe |
| `tests/test_onboarding_manager.py` | New | 17 unit test (V6) |
| `CHANGELOG.md` | Update | Sezione `[Unreleased]` |
| `docs/reports/SPARK-REPORT-DualUniverse-Consolidation-v1.0.md` | New | Questo report |

**Non toccati intenzionalmente:**

- `spark-framework-engine.py` (motore — nessun cambio firma tool)
- Engine `.github/**` (`framework_edit_mode: false` rispettato)
- Manifest dei pacchetti
- `packages/spark-base/.github/spark-packages.json`

---

## 6. Test Suite

**Comando di regressione:**

```
C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest -q --ignore=tests/test_integration_live.py
```

**Risultato post-task:** `471 passed, 9 skipped, 12 subtests passed`
(esecuzione 4.92s, exit 0).

**Nuovi test aggiunti:** 17 in `tests/test_onboarding_manager.py`,
tutti PASS.

**Test integration live:** non eseguiti in questo task. Il fix di
ANOMALIA-NEW dovrebbe ridurre i casi `status: "partial"` osservati
in scenari live; raccomandato un giro mirato in M5/postmerge.

---

## 7. Stato Documentazione

| Documento | Stato |
|-----------|-------|
| `CHANGELOG.md` `[Unreleased]` | Aggiornato con sezione "Dual-Universe Consolidation (audit 2026-05-09)" |
| `spark-assistant.agent.md` | Sezione dual-universe aggiunta |
| `spark-guide.agent.md` | Non modificato (gia copre routing) |
| `README.md` | Non modificato (nessun cambio API) |
| Report Perplexity originale | Mantenuto come fonte storica |
| Questo report | Creato |

---

## 8. Raccomandazioni

### P0 — Bloccante, immediato

Nessuna. Tutti i bloccanti sono stati risolti in questo task.

### P1 — Alto, prossima sessione

- **R1.** Eseguire `tests/test_integration_live.py` su un workspace
  reale per confermare che ANOMALIA-NEW e effettivamente l'unica
  causa dei `status: "partial"` storici. Se restano altri casi,
  aprire un audit dedicato su `OnboardingManager._install_declared_packages`.
- **R2.** Aggiungere un test integrazione che esegua
  `run_onboarding()` end-to-end (mock minimo) e verifichi
  `status == "completed"` su workspace vergine + `spark-packages.json`
  con `auto_install: true`. Oggi i 17 test sono unitari ma non
  catturerebbero un'altra regressione di import.

### P2 — Medio, backlog

- **R3.** Definire un orizzonte di rimozione per i tool legacy
  `scf_list_plugins` e `scf_install_plugin` (es. due minor release
  dopo l'introduzione del marker `deprecated`). Documentare la
  data target nel CHANGELOG.
- **R4.** Considerare se `spark-guide.agent.md` debba duplicare la
  sezione dual-universe o se basti il rimando da `spark-assistant`.
  Decisione UX, non tecnica.

### P3 — Basso

- **R5.** Aggiungere lint/CI check che verifichi assenza di import
  orfani sui modulo `spark.boot.*` (avrebbe catturato ANOMALIA-NEW
  in CI invece che a runtime).

---

## 9. Decisioni Aperte

- **D1.** Bumpare `version` nel frontmatter di
  `spark-assistant.agent.md` da 1.2.0 a 1.3.0 per la nuova sezione?
  Non fatto in questo task per evitare modifiche fuori dal perimetro
  esplicito della richiesta. Da decidere prima del prossimo merge.
- **D2.** Estrarre `_LEGACY_DEPRECATION_NOTICE` in un modulo
  condiviso (es. `spark/boot/_legacy_markers.py`) per riusarlo se
  altri tool diventeranno legacy? Oggi non necessario: i tool
  legacy sono solo 2 nello stesso modulo.

---

**Fine report.**
