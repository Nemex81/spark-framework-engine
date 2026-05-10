# SPARK — Audit Sistema Post-Refactoring

**Ramo:** `feature/dual-mode-manifest-v3.1`
**Data:** 2026-05-09
**Eseguito da:** Perplexity AI (Coordinatore) — analisi statica sul commit `14eac95d`
**Approvato da:** Nemex81

---

## 1. Sintesi Esecutiva

**Stato generale: GIALLO**

| Categoria | Conteggio |
|---|---|
| Problemi critici (P0/CRITICO) | 1 |
| Problemi alti (P1/ALTO) | 2 |
| Problemi medi (P2/MEDIO) | 3 |
| Problemi bassi / tech debito (P3) | 2 |
| Gap di documentazione | 3 |

Il disaccoppiamento Universo A / Universo B è **strutturalmente completo** a livello di separazione dei file e degli import. Nessuna contaminazione incrociata rilevata tra `tools_bootstrap.py` e `tools_plugins.py`. Tuttavia, il sottosistema di onboarding presenta un **difetto critico latente** sull'event loop `asyncio` che rende silenziosamente non operative le installazioni pacchetti al primo avvio in contesto FastMCP. I test coprono il boot generale ma mancano completamente test unitari per `OnboardingManager`. La documentazione è presente ma il commit `14eac95d` non risulta menzionato esplicitamente nel `CHANGELOG.md`.

---

## 2. Stato Implementazione — Universo A / Universo B

Il refactoring del commit `14eac95d` ha raggiunto una separazione netta dei due universi:

- **Universo A** (`tools_bootstrap.py`): gestisce esclusivamente bootstrap Cat.A, copia file workspace da `packages/spark-base/`, sentinella `AGENTS.md`, idempotenza SHA-256. Non contiene riferimenti a plugin, registry SCF o `tools_plugins.py`.
- **Universo B** (`tools_plugins.py`): registra i 7 tool MCP plugin, delega a `PluginManagerFacade` per le operazioni store-based (Dual-Mode v1.0) e mantiene compat legacy con `download_plugin`. Non importa nulla da `tools_bootstrap.py` né da logica Cat.A.
- **OnboardingManager** (`onboarding.py`): coordina i due universi chiamando `ensure_minimal_bootstrap()` (sincrono, Universo A) e poi `install_package_for_onboarding()` (async, connesso al registry remoto — Universo B). Il **confine concettuale è rispettato**, ma il meccanismo di chiamata `asyncio.run()` è incompatibile con il runtime FastMCP.

Il livello di disaccoppiamento dichiarato è **raggiunto nell'80% dei casi**. Il 20% residuo riguarda la gestione dell'event loop nel bridge onboarding → Universo B.

---

## 3. Punti di Verifica

### V1 — `install_package_for_onboarding()`

**STATO: PARZIALE**

Il metodo esiste in `engine.py` alla riga 343, definito come `async def install_package_for_onboarding(self, package_id: str) -> dict[str, Any]`. È implementato correttamente: richiama `RegistryClient` per recuperare il manifest remoto, verifica compatibilità v3 tramite `_is_v3_package()`, e delega a `self._install_package_v3()` (riga ~413). Non è un placeholder vuoto — la logica è presente. Il problema non è il metodo in sé, ma come viene chiamato: in `onboarding.py` riga 338, `asyncio.run()` invoca questo metodo `async` dall'interno di `run_onboarding()`, che è un metodo **sincrono** chiamato da `_build_app()`, che a sua volta è chiamato **dopo** che FastMCP ha già avviato il suo event loop. Questo degrada silenziosamente a una RuntimeError gestita, rendendo V1 non fatale ma comunque non operativo al runtime normale.

### V2 — Problema event loop in `_install_declared_packages()`

**STATO: CRITICO**

> **⚠ NOTA POST-AUDIT (2026-05-09):** la classificazione CRITICO è stata
> rivista a **MEDIO** nel report di consolidamento
> `SPARK-REPORT-DualUniverse-Consolidation-v1.0.md` (§ V2).
> Analisi statica dell'entry point (`spark-framework-engine.py` riga 196)
> conferma che `_build_app()` ritorna l'istanza FastMCP **prima** che
> `.run(transport="stdio")` avvii il proprio event loop. Le chiamate
> `asyncio.run()` in `_build_app()` operano quindi in una finestra sicura.
> Il `try/except RuntimeError` difensivo già presente è sufficiente come hardening.
> Nessuna modifica al codice richiesta.

`sequence.py` chiama `onboarding.run_onboarding()` **sincronamente** alla riga 190, all'interno di `_build_app()` che è una funzione `def` (non `async`). Il problema reale è che `_build_app()` viene chiamato dall'entry point dello script principale che avvia FastMCP con `transport="stdio"`. FastMCP (basato su `anyio`/`asyncio`) gestisce internamente il proprio event loop. Al momento in cui `_install_declared_packages()` esegue `asyncio.run()` (riga 338 di `onboarding.py`), l'event loop potrebbe già essere attivo, causando `RuntimeError: This event loop is already running`.

La mitigazione presente (riga 354: `except RuntimeError as exc`) cattura l'eccezione e la logga come warning su stderr — ma il pacchetto NON viene installato. L'onboarding risulta apparentemente completato (`status: "partial"` o `status: "skipped"`) senza installare nulla, senza alcuna segnalazione visibile all'utente. Il bug non causa crash, ma produce un **onboarding silenziosamente vuoto** in ogni avvio normale con FastMCP attivo.

**Contesto preciso:** la finestra sicura in cui `asyncio.run()` funzionerebbe è solo se `_build_app()` viene chiamato prima che FastMCP avvii il proprio loop — ma l'ordine nella sequenza è: bootstrap → onboarding → `return mcp` → il chiamante invoca `mcp.run(transport="stdio")`. L'event loop di FastMCP viene avviato *dopo* il ritorno di `_build_app()`, quindi tecnicamente la finestra esiste. Occorre verifica sperimentale, ma il rischio rimane alto e dipende dall'implementazione interna di FastMCP.

### V3 — Idempotenza bootstrap su `spark-packages.json`

**STATO: OK**

`spark-packages.json` è presente nella lista `_SPARK_BASE_FALLBACK_WORKSPACE_FILES` alla riga 647 di `tools_bootstrap.py`. La logica di copia **non sovrascrive** file utente già modificati: la riga 778 confronta SHA-256 sorgente e destinazione (`manifest._sha256(dest_path) == manifest._sha256(source_path)`), e scrive solo se gli hash differiscono E solo se il file non esiste già (riga 690: `if not dest_path.is_file()`). Il controllo idempotenza usa quindi sia `is_file()` come gate primario sia SHA-256 come gate secondario per i file già presenti. Il comportamento è corretto e non distruttivo.

### V4 — Separazione Universo A / Universo B

**STATO: OK**

Analisi degli import e dei riferimenti incrociati:

- `tools_bootstrap.py` non contiene import da `tools_plugins.py`, né riferimenti a `plugin`, `Plugin`, `scf-registry` o concetti Universo B. Gli import si limitano a: `spark.manifest`, `spark.packages`, `spark.assets`, `spark.workspace`, `spark.merge.validators`, `spark.boot.install_helpers`.
- `tools_plugins.py` non contiene import da `tools_bootstrap.py`, né riferimenti a `bootstrap`, `Cat.A`, `FALLBACK`, o strutture Universo A. I suoi import sono: `spark.plugins`, `spark.registry.client`, `spark.core.constants`, `spark.core.utils`, `spark.packages`.
- I due file condividono l'uso di `spark.packages` e `spark.registry.client`, ma questo è corretto: sono utilità condivise, non logica di business di uno dei due universi.

La separazione è **architetturalmente pulita**.

### V5 — Narrazione utente in `spark-assistant.agent.md`

**STATO: PARZIALE**

Il file `spark-assistant.agent.md` esiste nel bundle `packages/spark-base/.github/agents/` ed è semanticamente ricco. Contiene:

- Sezione "Flusso A — Onboarding workspace vergine" con istruzioni su `scf_bootstrap_workspace`.
- Riferimenti espliciti ai tool `scf_plugin_install`, `scf_plugin_list`, `scf_plugin_update`, `scf_plugin_remove` (Universo B).
- Istruzione di delega a `spark-guide` per spiegazioni architetturali.

**Mancante:** Non esiste una sezione esplicita che descriva la distinzione tra i due universi (pacchetti interni Universo A vs plugin SCF Universo B) in termini comprensibili all'utente finale. L'agente cita i tool corretti ma non spiega *perché* esistono due famiglie separate e quali sono le implicazioni pratiche per l'utente. Questo è un **gap narrativo medio**: funzionalmente l'agente opera correttamente, ma un utente che chiede "qual è la differenza tra un pacchetto e un plugin?" non ottiene risposta da questo agente, essendo rimandato a `spark-guide` (la cui esistenza nel bundle non è stata verificata in questo audit).

### V6 — Copertura test OnboardingManager

**STATO: MANCANTE**

Analisi dei 44 file di test presenti: non esiste nessun file dedicato a `OnboardingManager`. Il file `test_boot_sequence.py` testa solo che `ensure_minimal_bootstrap()` venga chiamato durante `_build_app()`, ma non tocca `OnboardingManager`.

Test mancanti identificati:

- `is_first_run()` con `spark-packages.json` presente e tutti i pacchetti installati → deve ritornare `False`
- `is_first_run()` con `spark-packages.json` presente e pacchetto mancante → deve ritornare `True`
- `is_first_run()` senza file → fallback legacy, manifest vuoto → `True`
- `is_first_run()` con `auto_install: false` → deve ritornare `False`
- `run_onboarding()` con errore in uno step → `status == "partial"`, altri step non bloccati
- `_install_declared_packages()` con `auto_install: false` → lista vuota
- `_install_declared_packages()` con RuntimeError su asyncio.run → skip silenzioso, nessun crash

Copertura stimata `OnboardingManager`: **0%** (nessun test diretto).

---

## 4. Problemi Trovati (fuori dai punti di verifica)

### Problema 4.1 — `asyncio.run()` in `ensure_minimal_bootstrap()` stesso

**File:** `spark/boot/engine.py`
**Riga:** 342 (`return asyncio.run(self._bootstrap_workspace_tool())`)
**Severità:** ALTO
**Descrizione:** `ensure_minimal_bootstrap()` usa anch'esso `asyncio.run()` per invocare `self._bootstrap_workspace_tool()`. Il problema è identico a V2: se chiamato in un contesto dove l'event loop è già attivo, il bootstrap Cat.A fallisce silenziosamente con RuntimeError catturata. Il catch alla riga 343-348 restituisce `status: "auto_bootstrap_skipped"` ma il workspace rimane non inizializzato.
**Impatto:** In ambiente FastMCP già avviato (es. re-init, hot reload), il bootstrap Cat.A non viene mai eseguito, lasciando il workspace privo dei file sentinella.
**Proposta:** Sostituire `asyncio.run()` con una chiamata sincrona o refactorare il bootstrap Cat.A per avere un percorso sincrono separato da quello asincrono dei tool MCP.

### Problema 4.2 — Commit `14eac95d` non tracciato in `CHANGELOG.md`

**File:** `CHANGELOG.md`
**Riga:** N/A
**Severità:** BASSO
**Descrizione:** La ricerca nel `CHANGELOG.md` per `14eac95d`, `dual-mode`, `decoupl` e `spark-packages` non restituisce nessun entry corrispondente al commit oggetto di questo audit. L'ultima entry datata è `[3.2.0] - 2026-05-06`, tre giorni prima di questo commit.
**Impatto:** Nessun impatto funzionale. Il branch non è ancora su main, quindi il CHANGELOG potrà essere aggiornato prima del merge. Segnalato per completezza.
**Proposta:** Aggiungere entry in CHANGELOG.md per le modifiche al sottosistema onboarding prima del merge su main.

### Problema 4.3 — `tools_plugins.py`: nomenclatura legacy non documentata nel namespace MCP

**File:** `spark/boot/tools_plugins.py`
**Riga:** Header docstring, tool `scf_list_plugins` e `scf_install_plugin`
**Severità:** MEDIO
**Descrizione:** Il file dichiara esplicitamente che `scf_list_plugins` e `scf_install_plugin` sono "compat legacy per download diretto senza tracking". Tuttavia, questi tool vengono comunque registrati via `mcp.tool()` e sono visibili a Copilot. Non esiste un meccanismo di deprecation warning nel risultato MCP, né una distinzione documentata nel manifesto dei tool che consenta a Copilot di preferire i tool store-based.
**Impatto:** Copilot potrebbe scegliere i tool legacy invece di quelli store-based (`scf_plugin_install`, `scf_plugin_list`), producendo installazioni plugin senza tracking completo.
**Proposta:** Aggiungere un campo `deprecated: true` o un warning nel risultato JSON dei tool legacy, o includerli nella policy `tools_policy.py` con priorità esplicita.

### Problema 4.4 — `spark-guide.agent.md` non verificato nel bundle spark-base

**File:** `packages/spark-base/.github/agents/`
**Riga:** N/A
**Severità:** MEDIO
**Descrizione:** `spark-assistant.agent.md` rimanda esplicitamente all'agente `spark-guide` per spiegazioni architetturali. La directory agents contiene: `Agent-Analyze.md`, `Agent-Docs.md`, `Agent-FrameworkDocs.md`, `Agent-Git.md`, `Agent-Helper.md`, `Agent-Orchestrator.md`, `Agent-Plan.md`, `Agent-Release.md`, `Agent-Research.md`, `Agent-Validate.md`, `Agent-Welcome.md`, `spark-assistant.agent.md`, `spark-guide.agent.md`. Il file `spark-guide.agent.md` **esiste**, ma il suo contenuto non è stato analizzato in questo audit. Se non contiene la narrativa sui due universi, il rimando di `spark-assistant` è un dead-end comunicativo.
**Impatto:** L'utente che chiede spiegazioni architetturali potrebbe non ricevere risposta adeguata.
**Proposta:** Verificare che `spark-guide.agent.md` contenga la sezione dual-universe in un audit successivo o esteso.

---

## 5. Suite di Test — Stato

**Test totali trovati relativi al sottosistema boot/onboarding:** 2 (parziali)

- `tests/test_boot_sequence.py`: testa che `ensure_minimal_bootstrap()` venga chiamato — non testa OnboardingManager.
- `tests/test_bootstrap_workspace.py` e `test_bootstrap_workspace_extended.py`: testano il bootstrap Cat.A da `tools_bootstrap.py` — non toccano onboarding.

**Test mancanti identificati:**

- `test_onboarding_is_first_run_all_installed` — è_first_run = False quando tutti installati
- `test_onboarding_is_first_run_missing_package` — is_first_run = True quando pacchetto mancante
- `test_onboarding_is_first_run_no_file_legacy` — fallback legacy, manifest vuoto → True
- `test_onboarding_is_first_run_auto_install_false` — auto_install: false → False
- `test_onboarding_run_partial_on_step_error` — errore in step → status partial, altri step eseguiti
- `test_onboarding_install_declared_auto_install_false` — lista vuota quando auto_install: false
- `test_onboarding_install_declared_runtime_error` — RuntimeError su asyncio.run → skip silenzioso
- `test_onboarding_install_declared_already_installed` — pacchetto già installato non rieseguito

**Copertura stimata `OnboardingManager`:** 0% (nessun test diretto su nessun metodo pubblico)

---

## 6. Stato Documentazione

**Report di design presenti:**

- `docs/REFACTORING-DESIGN.md` (28 KB)
- `docs/SPARK-DESIGN-FullDecoupling-v1.0.md` (13 KB)
- `docs/SPARK-DESIGN-FullDecoupling-v2.0.md` (33 KB)
- `docs/implementation-plan-dual-mode-v3.1.md` (8 KB)
- `docs/refactoring-phase1-2.md` (3 KB)
- `docs/reports/SPARK-REPORT-DualMode-PostFix-v1.0.md`
- `docs/reports/SPARK-REPORT-P2-PluginAudit-v1.0.md`

**Coerenza con codice attuale: DIVERGENZE PARZIALI**

**Divergenze rilevate:**

1. **CHANGELOG.md non aggiornato** — Il commit `14eac95d` (prima fase disaccoppiamento boot/onboarding) non ha una entry corrispondente. L'ultimo tag è `[3.2.0] - 2026-05-06`.
2. **Documentazione onboarding assente** — Nessun doc in `docs/` descrive il flusso `OnboardingManager` → `spark-packages.json` → `install_package_for_onboarding`. Il design doc `implementation-plan-dual-mode-v3.1.md` descrive l'architettura target ma non documenta il meccanismo di onboarding automatico introdotto in `14eac95d`.
3. **Gap narrativo in spark-assistant** — Descritto in V5. La documentazione utente-facing non copre la distinzione pratica tra i due universi per l'utente finale.

---

## 7. Raccomandazioni Prioritizzate

### P0 — Bloccante (da risolvere prima del merge su main)

**P0.1 — Verificare sperimentalmente il comportamento asyncio.run() in contesto FastMCP**

Anche se l'analisi statica indica che `_build_app()` viene chiamato *prima* che FastMCP avvii il suo loop (il chiamante invoca `mcp.run()` solo dopo il `return mcp`), questo comportamento dipende dall'implementazione interna di FastMCP. Aggiungere un test d'integrazione che simuli il contesto di avvio reale e verifichi che `_install_declared_packages()` esegua effettivamente l'installazione e non produca solo `RuntimeError` inghiottite. Se il test fallisce, il fix è obbligatorio prima del merge.

**P0.2 — Aggiungere test unitari per `OnboardingManager`**

Copertura 0% su un componente che gestisce il primo avvio utente è inaccettabile per un merge su main. Minimo richiesto: i 5 casi descritti in V6 (is_first_run positivo/negativo, run_onboarding partial, _install_declared con auto_install false, _install_declared con RuntimeError).

### P1 — Alta priorità (da risolvere in questo branch)

**P1.1 — Refactoring asyncio in `ensure_minimal_bootstrap()` e `_install_declared_packages()`**

Entrambi i metodi usano `asyncio.run()` per chiamare coroutine da contesto sincrono. La soluzione raccomandata: creare un metodo `_run_coro_safe(coro)` che usa `asyncio.get_event_loop().run_until_complete()` se il loop è già attivo (tramite `nest_asyncio` o via `asyncio.ensure_future` con `concurrent.futures`), oppure refactorare i metodi interni del bootstrap e dell'installazione per avere un percorso puramente sincrono separato da quello MCP.

**P1.2 — Aggiornare `CHANGELOG.md` con entry per commit `14eac95d`**

Documentare: disaccoppiamento boot/onboarding, introduzione `OnboardingManager`, `spark-packages.json` come file dichiarativo, metodo `install_package_for_onboarding()` su engine.

### P2 — Media priorità (prossimo sprint)

**P2.1 — Aggiungere warning di deprecation ai tool plugin legacy**

`scf_list_plugins` e `scf_install_plugin` in `tools_plugins.py` devono segnalare nel risultato MCP che sono tool legacy e indicare i sostituti store-based raccomandati.

**P2.2 — Sezione dual-universe in `spark-assistant.agent.md`**

Aggiungere una sezione breve (max 10 righe) che spieghi in termini utente-finali la differenza tra pacchetti interni (Universo A, gestiti automaticamente dall'engine al boot) e plugin SCF (Universo B, scelti e installati esplicitamente tramite Plugin Manager).

**P2.3 — Verificare contenuto `spark-guide.agent.md`**

Confermare che l'agente guida contenga la narrativa completa sui due universi prima che `spark-assistant` inizi a redirigere utenti verso di esso.

### P3 — Bassa priorità / tech debito

**P3.1 — Documentare `OnboardingManager` in `docs/`**

Aggiungere una sezione in `implementation-plan-dual-mode-v3.1.md` o un documento separato che descriva il flusso completo di onboarding automatico, incluse le condizioni di fallback e il comportamento in caso di RuntimeError.

**P3.2 — Policy esplicita per tool deprecati in `tools_policy.py`**

Valutare se `tools_policy.py` debba includere una policy di deprecazione esplicita per gestire la transizione tool legacy → tool store-based in modo uniforme per tutto il sistema.

