# Piano Tecnico Implementativo — Registry Sync Gateway (Architettura Centralizzata)

**Versione documento:** 2.0 — Architettura centralizzata (gateway sul motore)
**Data redazione:** 2026-03-31
**Stato:** ⏳ in lavorazione
**Motivo revisione v2.0:** cambio architetturale rispetto alla v1.0 (workflow diretto dal plugin)
**Riferimento progetto logico:** Task per Copilot — Sincronizzazione Registry e Automazione Fase 3

---

## Cambio architetturale: perché si cambia approccio

La versione 1.0 (prevista in `SCF-CANONICAL-TRUTH-IMPL-PLAN.md` — Fase 3) prevedeva che ogni
plugin avesse il permesso diretto di scrivere su `scf-registry`. Abbandonato perché:

- N plugin = N token `REGISTRY_WRITE_TOKEN` da gestire
- N logiche di aggiornamento diverse nei repo plugin
- N punti di accesso diretto al registry

La nuova architettura centralizza tutto sul motore (`spark-framework-engine`), che diventa
l'unico gateway autorizzato a scrivere su `scf-registry`. I plugin non scrivono mai
direttamente — segnalano al motore che qualcosa è cambiato via evento, il motore fa il resto.

```
plugin modifica package-manifest.json
  → push su main del plugin
    → workflow plugin invia evento al motore (repository_dispatch)
      → workflow motore riceve l'evento
        → motore legge il manifest del plugin
          → motore apre PR su scf-registry
```

---

## Note di convalida (analisi pre-implementazione — 2026-03-31)

### O1 — Sostituzione della Fase 3 del Canonical Truth Plan
`SCF-CANONICAL-TRUTH-IMPL-PLAN.md` (Fase 3) prevedeva un workflow diverso (`sync-registry.yml`
in `scf-pycode-crafter` con `REGISTRY_WRITE_TOKEN` sul plugin). Il presente piano lo supera con
l'architettura gateway. La Fase 3 del Canonical Truth va aggiornata per dichiarare la
sostituzione.

### O2 — Blocco E del Corrective Plan è stale
`SCF-CORRECTIVE-PLAN.md` mostra E1–E4 come `⏳ da fare`, ma nel sorgente
`fetch_package_manifest`, la logica reale di `scf_install_package` e `scf_remove_package`
esistono già. Da chiudere come parte del Compito 4 di questo piano.

### O3 — Validazione input nel gateway
Il workflow gateway deve validare i campi ricevuti dal payload `repository_dispatch`
(`pkg_id`, `version`, `engine_min`) prima di scrivere su `registry.json`. Un payload
malformato o vuoto potrebbe inserire dati invalidi. Aggiungere check nel blocco Python.

### O4 — Version bump
L'aggiunta di workflow infrastrutturali senza cambiare il runtime MCP è un **bump patch**:
`1.3.0` → `1.3.1`.

### O5 — Disambiguazione Compito 3 / CHANGELOG
L'aggiornamento di `CHANGELOG.md` nel Compito 3 è un'azione dell'agente in fase di
implementazione, non uno step automatico del workflow.

---

## Compito 1 — Sincronizzazione manuale del registry (ultima volta a mano)

**Repo:** `Nemex81/scf-registry`
**File:** `registry.json`

**Situazione attuale verificata:**
- `registry.json`: `latest_version: "1.0.0"`, `engine_min_version: "1.0.0"` (stale)
- `package-manifest.json`: `version: "1.0.1"`, `min_engine_version: "1.2.1"` (fonte canonica)
- Corrispondenza ID: `id: "scf-pycode-crafter"` == `package: "scf-pycode-crafter"` ✅

**Azioni:**

- [ ] Aggiornare `latest_version` → `"1.0.1"` in `registry.json`
- [ ] Aggiornare `engine_min_version` → `"1.2.1"` in `registry.json`
- [ ] Aggiornare `updated_at` con timestamp ISO 8601 corrente
- [ ] Committare su `main` di `scf-registry`

---

## Compito 2 — Workflow lato plugin (repo scf-pycode-crafter)

**Repo:** `Nemex81/scf-pycode-crafter`
**File da creare:** `.github/workflows/notify-engine.yml`

**Scopo:** quando cambia `package-manifest.json` su `main`, inviare un evento
`repository_dispatch` a `spark-framework-engine` con i dati del manifest.

**Dettagli tecnici:**
- Trigger: `push` su `main`, path filter `package-manifest.json`
- Legge dal manifest: `package` (→ `pkg_id`), `version`, `min_engine_version` (→ `engine_min`)
- Invia `repository_dispatch` a `Nemex81/spark-framework-engine`
  - `event_type: "plugin-manifest-updated"`
  - Payload: `{ pkg_id, version, engine_min }`
- Autentica con secret `ENGINE_DISPATCH_TOKEN`
- Fallisce visibilmente se l'invio non riesce (zero fallimenti silenziosi)

**Azioni:**

- [ ] Creare `.github/workflows/notify-engine.yml` in `scf-pycode-crafter`
- [ ] Verificare che il job utilizzi `actions/checkout@v4` per leggere il manifest
- [ ] Verificare step `jq` per estrazione campi: `package`, `version`, `min_engine_version`
- [ ] Verificare step `curl` per invio `repository_dispatch` con errore esplicito su fallimento
- [ ] Committare su `main` di `scf-pycode-crafter`

---

## Compito 3 — Workflow lato motore (repo spark-framework-engine)

**Repo:** `Nemex81/spark-framework-engine`
**File da creare:** `.github/workflows/registry-sync-gateway.yml`

**Scopo:** ascoltare gli eventi `plugin-manifest-updated` e aprire PR su `scf-registry`.

**Dettagli tecnici:**
- Trigger: `repository_dispatch` con `event_type: "plugin-manifest-updated"`
- Riceve dal payload: `pkg_id`, `version`, `engine_min`
- Checkout di `scf-registry` con `REGISTRY_WRITE_TOKEN`
- Aggiorna `registry.json`:
  - Cerca voce con `id == pkg_id`
  - Sovrascrive `latest_version` e `engine_min_version`
  - Valida che i campi non siano vuoti (O3)
  - Se il pacchetto non è trovato: fallisce con errore esplicito
  - Aggiorna `updated_at` con timestamp corrente
- Apre PR su `scf-registry` con:
  - Branch: `sync/<pkg_id>-<version>`
  - Titolo: `sync: <pkg_id> <version>`
  - Body: descrittivo con riferimento all'evento e al repo sorgente
- Usa `peter-evans/create-pull-request@v6`

**Azioni:**

- [ ] Creare `.github/workflows/registry-sync-gateway.yml` in `spark-framework-engine`
- [ ] Verificare step di checkout di `scf-registry` con `REGISTRY_WRITE_TOKEN`
- [ ] Verificare blocco Python: validazione input + aggiornamento `registry.json`
- [ ] Verificare step `peter-evans/create-pull-request@v6` con branch naming corretto
- [ ] Aggiornare `CHANGELOG.md` di `spark-framework-engine` con bump patch `1.3.1`
  - Voce: `Added` — workflow `registry-sync-gateway.yml` come gateway centralizzato
- [ ] Committare su `main` di `spark-framework-engine`

---

## Compito 4 — Chiusura debito documentale

**Azioni:**

- [ ] Aggiornare `SCF-CANONICAL-TRUTH-IMPL-PLAN.md` — Fase 3:
  dichiarare sostituzione con architettura gateway; eliminare `REGISTRY_WRITE_TOKEN` lato plugin
- [ ] Chiudere il Blocco E in `SCF-CORRECTIVE-PLAN.md`:
  marcare E1–E4 come `✅ completato` (implementazione già presente nel sorgente)
- [ ] Aggiornare `SCF-CORRECTIVE-PLAN.md` — tabella stato avanzamento
- [ ] Aggiornare questo file: `**Stato:** ✅ completato`

---

## Compito 5 — Verifica finale

**Checklist di completamento del piano:**

- [ ] `scf-registry/registry.json` aggiornato (`1.0.1` / `1.2.1`)
- [ ] `notify-engine.yml` esiste in `scf-pycode-crafter` e sintassi YAML valida
- [ ] `registry-sync-gateway.yml` esiste in `spark-framework-engine` e sintassi YAML valida
- [ ] I due workflow sono compatibili: il payload inviato dal plugin corrisponde
      ai campi attesi dal gateway (`pkg_id`, `version`, `engine_min`)
- [ ] `CHANGELOG.md` di `spark-framework-engine` aggiornato con voce `1.3.1`
- [ ] Blocco E di `SCF-CORRECTIVE-PLAN.md` chiuso
- [ ] `SCF-CANONICAL-TRUTH-IMPL-PLAN.md` Fase 3 aggiornata

---

## Secret da creare manualmente (azione umana — dopo l'implementazione)

**In `scf-pycode-crafter`** (e in ogni futuro plugin):
| Secret | Permesso richiesto |
|--------|-------------------|
| `ENGINE_DISPATCH_TOKEN` | `repository_dispatch` write su `spark-framework-engine` |

**In `spark-framework-engine`** (una volta sola per tutto il sistema):
| Secret | Permesso richiesto |
|--------|-------------------|
| `REGISTRY_WRITE_TOKEN` | write su `scf-registry` (PR e branch creation) |

Il `REGISTRY_WRITE_TOKEN` è l'**unico punto dell'intero sistema** con accesso diretto
al registry. Tutti i plugin futuri useranno solo `ENGINE_DISPATCH_TOKEN`.

---

## Stato avanzamento complessivo

| Compito | Descrizione | Repo coinvolto | Stato |
|---------|-------------|---------------|-------|
| 1 | Sync manuale `registry.json` | scf-registry | ⏳ da fare |
| 2 | Workflow `notify-engine.yml` | scf-pycode-crafter | ⏳ da fare |
| 3 | Workflow `registry-sync-gateway.yml` | spark-framework-engine | ⏳ da fare |
| 4 | Chiusura debito documentale | spark-framework-engine | ⏳ da fare |
| 5 | Verifica finale | tutti | ⏳ da fare |

---

*Piano redatto il 2026-03-31 — v2.0. Architettura gateway centralizzata sul motore.*
