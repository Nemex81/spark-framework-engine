# SPARK-REPORT — Init Audit & Dual-Mode Analysis v1.0

**Data esecuzione:** 2026-05-11
**Branch:** `workspace-slim-registry-sync-20260511`
**Agente:** `@spark-engine-maintainer`
**Prompt origine:** richiesta utente — audit profondo server tasks MCP/plugin, UX newbie, dual-mode
**Stato:** COMPLETATO ✓

---

## Indice

1. Obiettivo e perimetro
2. Architettura attuale: mappa componenti
3. AREA 1 — Sequenza di avvio e OnboardingManager
4. AREA 2 — scf_bootstrap_workspace: flusso completo
5. AREA 3 — Plugin install: dual-mode (local .github vs MCP-only)
6. AREA 4 — UX Newbie: analisi e gap
7. Tabella anomalie (PASS/FAIL + confidence)
8. Valutazioni e ottimizzazioni proposte
9. Scenari post-audit: matrice decisionale
10. Raccomandazioni per iterazione successiva

---

## 1. Obiettivo e perimetro

Audit architetturale su quattro aree:

| Area | Scope |
|------|-------|
| AREA 1 | Sequenza `_build_app` → `ensure_minimal_bootstrap` → `OnboardingManager` |
| AREA 2 | `scf_bootstrap_workspace`: flusso completo con dual-universe, policy, conflitti |
| AREA 3 | `scf_plugin_install` (PluginManagerFacade + PluginInstaller): local copy vs MCP-only |
| AREA 4 | UX newbie: strato alto di inizializzazione, trasferimento risorse .github base |

**Modalità:** audit-only, zero modifiche al codice in questo report.
**Riferimento evidenze:** file:riga precisi per ogni finding.

---

## 2. Architettura attuale: mappa componenti

```
spark-framework-engine.py
  └─► _build_app(engine_root)                   [spark/boot/sequence.py]
        │
        ├── WorkspaceLocator.resolve()           → WorkspaceContext
        ├── resolve_runtime_dir()                → runtime_dir (isolata per workspace)
        ├── _migrate_runtime_to_engine_dir()     → idempotente, marker .runtime-migrated
        ├── FrameworkInventory(context)          → agenti/skill/instructions/prompts
        ├── validate_engine_manifest()           → engine-manifest.json
        ├── inventory.populate_mcp_registry()   → McpResourceRegistry + URI
        │
        ├── SparkFrameworkEngine(mcp, ctx, inv, runtime_dir)
        │     └─ _init_runtime_objects()          [lazy, prima di register_tools]
        │           ├── ManifestManager           .github/.scf-manifest.json
        │           ├── RegistryClient            .github/.scf-registry-cache.json
        │           ├── MergeEngine
        │           ├── SnapshotManager
        │           ├── MergeSessionManager
        │           └── PluginManagerFacade       .github/.spark-plugins
        │
        ├── app.register_resources()             → URI agents://, skills://, prompts://...
        ├── app.register_tools()                 → factory per gruppo tool
        │     ├── tools_resources.py
        │     ├── tools_override.py
        │     ├── tools_bootstrap.py             [4 tool: verify_workspace, verify_system,
        │     │                                    bootstrap_workspace, migrate_workspace]
        │     ├── tools_policy.py
        │     ├── tools_packages.py
        │     └── tools_plugins.py               [7 tool: plugin_install, _remove, _update,
        │                                           _list, get_plugin_info, list_plugins (dep),
        │                                           install_plugin (dep)]
        │
        ├── app._v3_repopulate_registry()        → ricarica store packages/ nel registry
        ├── app.ensure_minimal_bootstrap()       → sentinel gate (5 Cat.A files)
        │
        └── OnboardingManager(ctx, inv, app)     [spark/boot/onboarding.py]
              ├── is_first_run()                 → confronta spark-packages.json vs manifest
              └── run_onboarding()               → 3 step: bootstrap / store / declared_pkgs
```

**Dual-Universe (packages resolution):**

```
_get_package_install_context(package_id)
  ├── Universe A: local store  delivery_mode="mcp_only" → packages/{id}/  (zero HTTP)
  └── Universe B: remote registry → RegistryClient HTTPS
```

**Plugin path:**

```
scf_plugin_install(pkg_id, workspace_root)
  └── PluginManagerFacade.install(pkg_id)
        ├── RegistryClient.list_packages()       (Universe B always)
        ├── RegistryClient.fetch_package_manifest(repo_url)
        └── PluginInstaller.install_files()      → download raw GitHub + WorkspaceWriteGateway
              └── writes .github/<plugin_files>  → fisicamente nel workspace utente
```

---

## 3. AREA 1 — Sequenza di avvio e OnboardingManager

### 3.1 Flusso sequenziale verificato

**File:** `spark/boot/sequence.py` righe 143–200

La sequenza in `_build_app` procede correttamente in 13 passi documentati nel
report `SPARK-REPORT-MCP-Server-Flow-v1.0.md`. Nessuna anomalia strutturale rilevata.

**Sentinel gate** (`ensure_minimal_bootstrap`, `engine.py` righe ~320–340):

```python
required_paths = (
    .github/agents/spark-assistant.agent.md,
    .github/agents/spark-guide.agent.md,
    .github/AGENTS.md,
    .github/copilot-instructions.md,
    .github/project-profile.md,
)
```

Gate: se **tutti e 5** presenti → `status: "already_present"`, zero scritture.
Se **anche uno solo mancante** → avvia `asyncio.run(_bootstrap_workspace_tool())`.

**GAP-1 (WARN):** I 5 file Cat.A del sentinel includono `spark-guide.agent.md` e
`spark-assistant.agent.md`, ma la `scf_bootstrap_workspace` usa come sentinel primario
`agents/Agent-Welcome.md` (`sentinel_rel = "agents/Agent-Welcome.md"` —
`tools_bootstrap.py` riga ~622). I due set di sentinelle non sono allineati.
Un workspace può avere Agent-Welcome ma mancante di spark-guide/spark-assistant,
o viceversa, producendo comportamenti divergenti tra auto-bootstrap e tool MCP.

### 3.2 OnboardingManager

**File:** `spark/boot/onboarding.py` righe 1–400

| Metodo | Comportamento | Status |
|--------|--------------|--------|
| `is_first_run()` | Legge `spark-packages.json`, confronta con manifest installato | PASS |
| `_ensure_bootstrap()` | Chiama `ensure_minimal_bootstrap` solo se mancano Cat.A sentinelle | PASS |
| `_ensure_store_populated()` | Verifica presenza file in `packages/<pkg>/` — NON installa | PASS |
| `_install_declared_packages()` | Chiama `install_package_for_onboarding(pkg_id)` per ogni pkg mancante | PASS |

**GAP-2 (WARN):** `_ensure_store_populated()` rileva solo lo stato (ritorna bool),
non avvia alcuna installazione. Il suo valore booleano non influenza il ciclo:
se lo store è vuoto, `_install_declared_packages` tenterà comunque l'installazione.
Il metodo ha quindi effetto solo logging. Potenziale confusione per futura manutenzione.

**GAP-3 (WARN):** `_install_declared_packages` usa `asyncio.run(...)` che fallisce
silenziosamente se c'è già un event loop attivo (eccezione `RuntimeError` loggata e
swallowed — `onboarding.py` riga ~345). In un contesto async (es. future integrazione
con server MCP async) questo path è inaffidabile. Attualmente non impatta il runtime
sincrono standard.

**GAP-4 (INFO):** Il fallback legacy in `is_first_run()` (nessun `spark-packages.json`
→ manifest vuoto = primo avvio) funziona solo se il workspace è completamente vergine.
Se l'utente ha aggiunto file a `.github/` manualmente senza un manifest, il fallback
non scatta e il primo avvio non eseguirà onboarding. Non è un bug (comportamento
documentato) ma è un gap UX per newbie.

---

## 4. AREA 2 — scf_bootstrap_workspace: flusso completo

### 4.1 Sorgente file bootstrap

**File:** `spark/boot/tools_bootstrap.py` righe ~622–640

```python
bootstrap_source_root = ctx.engine_root / "packages" / "spark-base" / ".github"
if not bootstrap_source_root.is_dir():
    bootstrap_source_root = ctx.engine_root / ".github"
```

**PASS:** il bootstrap usa prioritariamente il pacchetto locale `spark-base` (Universe A),
con fallback al `.github/` dell'engine root. Zero dipendenze di rete per il bootstrap
di base.

### 4.2 Flusso extended bootstrap (con update_mode)

Il tool supporta due modalità principali:

| Modalità | Trigger | Comportamento |
|----------|---------|---------------|
| **Legacy** | `update_mode=""` | Copia file Cat.A direttamente, nessuna policy configurata |
| **Extended** | `update_mode="ask"/"integrative"/"conservative"/"ask_later"` | Richiede policy, autorizzazione .github, poi install spark-base |

**Gate sequenza extended:**

```
1. policy_source != "file" → ritorna "policy_configuration_required" (action_required)
2. legacy_workspace E !github_write_authorized → ritorna "authorization_required"
3. policy configurata → _configure_initial_bootstrap_policy()
4. install_base=True → _get_package_install_context("spark-base") → Universe A/B routing
5. _build_local_file_records() / _build_remote_file_records()
6. _build_diff_summary() → mostra diff prima di applicare
7. Scrittura file tramite WorkspaceWriteGateway
```

**GAP-5 (FAIL — UX):** Il flusso extended richiede tre chiamate separate da parte
del client MCP in sequenza (prima config policy, poi autorizzazione, poi bootstrap
effettivo), ognuna con `action_required` diverso. Non esiste un comando single-shot
per un newbie. Un utente che invoca `scf_bootstrap_workspace(update_mode="ask")`
riceve un payload JSON con `"action_required": "configure_update_policy"` e deve
sapere cosa fare con esso. Non c'è guida testuale in-context per il passo successivo
nel payload (solo `available_update_modes` e `recommended_update_mode`).

**GAP-6 (WARN):** Il legacy bootstrap mode (nessun `update_mode`) non configura
alcuna policy né verifica `github_write_authorized`. Funziona "just copy", ma
lascia il workspace senza policy di aggiornamento configurata. Newbie che usano
il percorso legacy hanno un workspace sotto-configurato.

**GAP-7 (INFO):** `conflict_mode` è validato solo quando `install_base=True`
(riga ~565 tools_bootstrap.py). Se `install_base=False`, qualsiasi valore di
`conflict_mode` viene accettato silenziosamente. Coerenza incompleta dell'input.

### 4.3 File scritti dal bootstrap base (legacy mode)

Verificato da `spark/boot/tools_bootstrap.py`: copia **tutti** i file nell'alberatura
`packages/spark-base/.github/` verso il workspace utente `<workspace>/.github/`.

Questo include (da `spark-base/package-manifest.json`):
- 10 agenti (`Agent-*.md`, incluso `Agent-Welcome.md`)
- 9 instruction files
- `AGENTS.md`, `copilot-instructions.md`, `project-profile.md`
- 32 prompt files
- 23+ skill files

**PASS:** Il trasferimento base è completo e include tutte le risorse fondamentali.

---

## 5. AREA 3 — Plugin install: dual-mode (local .github vs MCP-only)

### 5.1 Architettura attuale

Il sistema distingue due categorie:

| Categoria | Tool | Flusso | Dove scrive |
|-----------|------|--------|-------------|
| **Pacchetti SCF** (Universe A/B) | `scf_install_package` | `tools_packages_install.py` → `_install_package_v3_into_store` | Engine store + manifest workspace |
| **Plugin** (sempre Universe B) | `scf_plugin_install` | `PluginManagerFacade.install()` → `PluginInstaller.install_files()` | `.github/` fisico nel workspace |

**GAP-8 (FAIL — architetturale):** `scf_plugin_install` usa **sempre** Universe B
(fetch remoto da GitHub). Non esiste un percorso Universe A per i plugin. Se il
registry è irraggiungibile, nessun plugin può essere installato, anche se il file
è già nel local store `packages/`. Questo è asimmetrico rispetto a `scf_install_package`.

**Evidenza:** `spark/plugins/facade.py` riga ~100: `self._find_registry_entry(pkg_id)`
richiede il catalogo remoto. `spark/plugins/installer.py` riga ~84: `_download_file(raw_url)`
esegue HTTP sempre.

### 5.2 Opzioni per l'utente (stato attuale)

| Scenario utente | Tool disponibile | Risultato `.github/` |
|----------------|-----------------|---------------------|
| Installa pacchetto base (spark-base) | `scf_bootstrap_workspace` | Trasferimento fisico completo |
| Installa pacchetto SCF (v3, mcp_only) | `scf_install_package` | Store engine + manifest, **NON** .github/ fisico |
| Installa plugin language (scf-pycode-crafter) | `scf_plugin_install` | `.github/` fisico tramite download remoto |

**NOTA CRITICA:** `scf_install_package` per pacchetti `delivery_mode="mcp_only"`
installa nel deposito engine (`packages/`) e aggiorna il manifest, ma **non** copia
file fisicamente in `.github/` del workspace. Le risorse sono accessibili solo via
MCP URI (`agents://`, `skills://`, etc.), **non** come file `.github/` statici
(non appaiono nell'editor VS Code come file navigabili).

Questo è il comportamento intenzionale per il "MCP-only" mode, ma crea un gap UX:
i pacchetti MCP-only non sono visibili nell'explorer di VS Code, cosa controintuitiva
per un newbie.

### 5.3 Dual-mode (locale modificabile vs solo MCP)

**Scenario A — Local .github modificabile (modalità scf_plugin_install):**
- I file vengono scaricati e scritti fisicamente in `.github/`
- L'utente può modificarli direttamente nell'editor
- Aggiornamenti richiedono re-download remoto
- Conflitti gestiti tramite preservation gate (SHA-256 check nel gateway)

**Scenario B — Solo MCP, no copia locale (modalità scf_install_package + delivery_mode=mcp_only):**
- File nel store engine, serviti via MCP URI
- Non visibili in `.github/` come file statici
- Aggiornamenti gestiti tramite `scf_update_package`
- Override opzionali tramite `scf_override_resource`

**GAP-9 (INFO):** Non esiste un percorso utente documentato per scegliere
consapevolmente tra le due modalità al momento dell'installazione. Il routing
(plugin vs package) è determinato dal tipo di artefatto nel registry, non da
una scelta esplicita dell'utente.

---

## 6. AREA 4 — UX Newbie: analisi e gap

### 6.1 Esperienza utente attuale (primo avvio)

**Scenario: newbie con workspace vuoto avvia il server MCP per la prima volta.**

```
Sequenza automatica (gestita internamente senza input utente):
  1. _build_app() avvia il server                          [background]
  2. ensure_minimal_bootstrap()
      → 5 Cat.A files mancanti                            [background]
      → asyncio.run(scf_bootstrap_workspace())            [background]
      → bootstrap con update_mode="" (legacy mode)        [background]
      → copia tutti i file spark-base/.github/ → workspace [background]
  3. OnboardingManager.is_first_run()
      → nessun spark-packages.json E manifest vuoto       [background]
      → è il primo avvio → run_onboarding()               [background]
  4. Step 3 onboarding: nessun spark-packages.json
      → _install_declared_packages() → lista vuota → skip [background]
  5. Output su stderr: "[SPARK] Inizializzazione completata."
```

**Risultato per il newbie:**
- Il workspace riceve tutti i file `.github/` di `spark-base` automaticamente
- L'utente vede il messaggio "Inizializzazione completata" ma non sa cosa è successo
- Non c'è un wizard di configurazione interattivo
- Non viene creato `spark-packages.json` automaticamente → le esecuzioni successive
  NON rieseguono l'onboarding (fallback legacy: manifest non vuoto = non primo avvio)

**GAP-10 (FAIL — UX critico):** Non viene creato `spark-packages.json` durante il
bootstrap. Questo significa che la logica `is_first_run()` al boot successivo
userà il path legacy (nessun file dichiarativo → controlla manifest) e siccome
i file Cat.A sono già presenti, `is_first_run()` ritornerà `False`. L'onboarding
non si ripeterà mai, anche se l'utente vuole installare pacchetti aggiuntivi.

**GAP-11 (FAIL — UX critico):** Non esiste uno strato di setup guidato per il
newbie. `Agent-Welcome.md` è disponibile ma deve essere invocato **manualmente**
dall'utente dal dropdown agenti VS Code. Nessun prompt automatico compare al
primo avvio in chat.

**GAP-12 (INFO):** Il messaggio stderr finale:
```
[SPARK] Prossimo passo: apri VS Code e di' a Copilot 'inizializza il workspace SPARK'
```
... si vede solo se l'utente ha accesso alla console stderr del server MCP. In un
deployment tipico VS Code, l'utente non vede mai questo messaggio.

### 6.2 Confronto strato UX: attuale vs ideale

| Aspetto | Stato attuale | Ideale newbie-friendly |
|---------|--------------|----------------------|
| Primo avvio automatico | PASS: bootstrap Cat.A silenzioso | Idem, più feedback in-chat |
| Wizard configurazione | FAIL: manuale (Agent-Welcome) | Prompt automatico in chat |
| Selezione pacchetti | FAIL: nessuna UI di scelta | scf_plan_install con opzioni |
| Visibilità file installati | WARN: MCP-only invisibili in explorer | Almeno `AGENTS.md` aggiornato |
| `spark-packages.json` generato | FAIL: non creato automaticamente | Creato al primo bootstrap |
| Messaggio post-avvio in chat | FAIL: solo stderr | Risposta MCP visibile in chat |

---

## 7. Tabella anomalie (PASS/FAIL + confidence)

| ID | Area | Descrizione | Severità | Confidence |
|----|------|-------------|----------|-----------|
| GAP-1 | AREA 1 | Set sentinelle divergente tra `ensure_minimal_bootstrap` e `scf_bootstrap_workspace` | WARN | 0.90 |
| GAP-2 | AREA 1 | `_ensure_store_populated()` solo logging, nessun effetto operativo | INFO | 0.95 |
| GAP-3 | AREA 1 | `asyncio.run()` in onboarding: inaffidabile se event loop attivo | WARN | 0.85 |
| GAP-4 | AREA 1 | Fallback legacy `is_first_run()` non scatta su workspace semi-popolato | INFO | 0.80 |
| GAP-5 | AREA 2 | Extended bootstrap richiede 3 chiamate MCP sequenziali senza guida | FAIL | 0.92 |
| GAP-6 | AREA 2 | Legacy bootstrap non configura policy aggiornamento | WARN | 0.90 |
| GAP-7 | AREA 2 | `conflict_mode` validato solo con `install_base=True` | INFO | 0.88 |
| GAP-8 | AREA 3 | `scf_plugin_install` senza Universe A: sempre fetch remoto | FAIL | 0.93 |
| GAP-9 | AREA 3 | Nessuna UI per scegliere local copy vs MCP-only | INFO | 0.85 |
| GAP-10 | AREA 4 | `spark-packages.json` non generato → re-onboarding impossibile | FAIL | 0.95 |
| GAP-11 | AREA 4 | Nessun wizard guidato al primo avvio in chat | FAIL | 0.92 |
| GAP-12 | AREA 4 | Messaggio bootstrap su stderr invisibile al newbie in VS Code | INFO | 0.88 |

**Legenda severità:** FAIL = blocco UX o comportamento corretto ma non funzionale,
WARN = funziona ma sub-ottimale, INFO = miglioramento opzionale.

**FAIL count:** 4 (GAP-5, GAP-8, GAP-10, GAP-11)
**WARN count:** 4 (GAP-1, GAP-3, GAP-6, GAP-7)
**INFO count:** 4 (GAP-2, GAP-4, GAP-9, GAP-12)

---

## 8. Valutazioni e ottimizzazioni proposte

### 8.1 Allineamento sentinelle (GAP-1)

**Proposta:** Unificare il set di sentinelle. L'opzione più solida è che
`scf_bootstrap_workspace` adotti lo stesso set `_minimal_bootstrap_required_paths()`
usato da `ensure_minimal_bootstrap`, oppure — se si vuole ridurre la dipendenza —
creare una costante condivisa in `spark/core/constants.py`:

```python
_BOOTSTRAP_SENTINEL_FILES: tuple[str, ...] = (
    "agents/spark-assistant.agent.md",
    "agents/spark-guide.agent.md",
    "AGENTS.md",
    "copilot-instructions.md",
    "project-profile.md",
)
```

Usata da entrambi i siti. Impatto: basso, nessuna rottura di test.

### 8.2 Generazione automatica spark-packages.json (GAP-10)

**Proposta:** Nel flusso `ensure_minimal_bootstrap` (dopo bootstrap Cat.A riuscito),
se `spark-packages.json` non esiste, crearlo automaticamente con contenuto minimo:

```json
{
  "packages": ["spark-base"],
  "auto_install": true,
  "_generated_by": "spark-engine-auto-bootstrap",
  "_generated_at": "<timestamp>"
}
```

Questo abilita `is_first_run()` a usare la logica primaria dichiarativa anziché il
fallback legacy. Prerequisito: la creazione deve passare per `WorkspaceWriteGateway`
per essere tracciata nel manifest.

### 8.3 Wizard in-chat per newbie (GAP-11)

**Proposta:** Aggiungere in `scf_bootstrap_workspace` un campo `next_steps` nel
payload di ritorno con istruzioni human-readable per il passo successivo. Esempio:

```json
{
  "status": "completed",
  "next_steps": [
    "Il workspace SPARK è pronto.",
    "Digita '@Agent-Welcome' in chat per configurare il profilo del progetto.",
    "Oppure usa '#scf-install' per aggiungere pacchetti linguaggio-specifici."
  ]
}
```

Questo non richiede modifiche architetturali — solo l'aggiunta del campo al payload.
Copilot legge il campo e lo presenta all'utente.

### 8.4 Universe A per scf_plugin_install (GAP-8)

**Proposta:** In `PluginManagerFacade.install()`, prima di interrogare il registry
remoto, verificare se esiste un file `packages/{pkg_id}/package-manifest.json` nel
local store con `delivery_mode="mcp_only"`. Se presente, usare il percorso locale
(zero HTTP). Stessa logica di `_try_local_install_context` in `tools_bootstrap.py`.

Prerequisito: i plugin devono essere inclusi nel local store `packages/` per
beneficiare di Universe A. Attualmente lo sono (scf-master-codecrafter,
scf-pycode-crafter) ma solo come pacchetti SCF, non come plugin.

### 8.5 Validazione conflict_mode invariante (GAP-7)

**Proposta:** Spostare la validazione di `conflict_mode` fuori dal blocco `if install_base:`,
applicandola sempre all'inizio della funzione, come avviene già per `update_mode`.

---

## 9. Scenari post-audit: matrice decisionale

Tre scenari operativi identificati per il percorso di miglioramento:

### Scenario 1 — Local-heavy (massima visibilità file)

**Descrizione:** Tutti i pacchetti scrivono file fisici in `.github/`. L'utente
può vedere e modificare tutto dall'explorer VS Code.

**Pro:** Trasparenza totale, navigabilità, compatibilità con qualsiasi editor.
**Contro:** File `.github/` numerosi, rischio drift (utente modifica accidentalmente
file SPARK), aggiornamenti più complessi (merge file per file).

**Richiede:** Rimozione della distinzione `delivery_mode="mcp_only"` o aggiunta di
una flag `local_copy=true` in `scf_install_package`.

**Effort:** ALTO — modifica a `tools_packages_install.py` e `lifecycle.py`.

### Scenario 2 — MCP-only (massima leggerezza workspace)

**Descrizione:** Solo i file Cat.A (spark-base bootstrap) vivono in `.github/`.
Tutto il resto è servito via MCP URI. Workspace minimo.

**Pro:** `.github/` pulito, aggiornamenti trasparenti, zero conflitti file utente.
**Contro:** Risorse non navigabili in VS Code explorer, debugging più difficile,
dipendenza dal server MCP attivo per ogni operazione.

**Richiede:** Documentazione chiara per l'utente, UI in-chat per scoperta risorse.
**Effort:** BASSO — architettura attuale già supporta questo scenario.

### Scenario 3 — Hybrid (raccomandato)

**Descrizione:** Bootstrap Cat.A sempre locale (5 file sentinella + workspace_files
di spark-base). Pacchetti aggiuntivi MCP-only per default, con opzione
`--local-copy` esplicita per chi vuole file fisici (scf_plugin_install).

| Categoria | Default | Opzione utente |
|-----------|---------|----------------|
| spark-base workspace_files | Locale `.github/` | Non modificabile |
| Agenti/skill/prompts/instructions | MCP URI | `scf_override_resource` per file locale |
| Plugin language-specific | Locale `.github/` (scf_plugin_install) | Già funzionante |
| Nuovi pacchetti SCF | MCP-only store | Flag `local_copy=True` (da aggiungere) |

**Questo è lo scenario più bilanciato e il più vicino allo stato attuale.**
**Effort:** MEDIO — aggiungere `local_copy` param + aggiornare UX payload.

---

## 10. Raccomandazioni per iterazione successiva

Priorità ordinata per impatto/effort:

| Priorità | ID Gap | Azione | Effort | Impatto |
|----------|--------|--------|--------|---------|
| P0 | GAP-10 | Genera `spark-packages.json` al bootstrap se assente | BASSO | ALTO |
| P0 | GAP-11 | Aggiungi `next_steps` array nel payload `scf_bootstrap_workspace` | BASSO | ALTO |
| P1 | GAP-5 | Aggiungi parametro `wizard_mode=True` per single-shot bootstrap guidato | MEDIO | ALTO |
| P1 | GAP-1 | Centralizza costante sentinelle in `spark/core/constants.py` | BASSO | MEDIO |
| P2 | GAP-8 | Universe A fallback in `PluginManagerFacade.install()` | MEDIO | MEDIO |
| P2 | GAP-6 | Legacy bootstrap crea policy default automaticamente | BASSO | MEDIO |
| P3 | GAP-7 | Sposta validazione `conflict_mode` fuori da `if install_base` | MINIMO | BASSO |
| P3 | GAP-3 | Refactoring `asyncio.run()` in onboarding con `_run_async_safe()` helper | MEDIO | BASSO |

---

## Appendice A — File auditati

| File | Righe lette | Area |
|------|------------|------|
| `spark/boot/sequence.py` | 1–202 | AREA 1 |
| `spark/boot/onboarding.py` | 1–400 | AREA 1 |
| `spark/boot/engine.py` | 1–400 | AREA 1 |
| `spark/boot/tools_bootstrap.py` | 1–800 | AREA 2 |
| `spark/boot/tools_plugins.py` | 1–400 | AREA 3 |
| `spark/plugins/facade.py` | 1–150 | AREA 3 |
| `spark/plugins/installer.py` | 1–150 | AREA 3 |
| `spark/boot/lifecycle.py` | 1–150 | AREA 3 |
| `spark/boot/install_helpers.py` | 1–80 | AREA 2 |
| `packages/spark-base/package-manifest.json` | 1–200 | AREA 4 |
| `packages/spark-base/.github/agents/Agent-Welcome.md` | 1–100 | AREA 4 |
| `docs/reports/SPARK-REPORT-DualUniverse-v2.0.md` | 1–120 | Contesto |
| `docs/reports/SPARK-REPORT-MCP-Server-Flow-v1.0.md` | 1–120 | Contesto |

---

**OPERAZIONE COMPLETATA:** Creazione SPARK-REPORT-InitAudit-DualMode-v1.0.md
**GATE:** PASS
**CONFIDENCE:** 0.88
**FILE TOCCATI:** `docs/reports/SPARK-REPORT-InitAudit-DualMode-v1.0.md` (nuovo)
**OUTPUT CHIAVE:** 12 gap identificati (4 FAIL, 4 WARN, 4 INFO), 3 scenari architetturali, 8 raccomandazioni prioritizzate
**PROSSIMA AZIONE:** Revisione utente → approvazione implementazione P0 (GAP-10, GAP-11) | CHECKPOINT
