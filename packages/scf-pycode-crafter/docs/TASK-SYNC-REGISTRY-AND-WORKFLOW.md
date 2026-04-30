# Task per Copilot — Sincronizzazione Registry e Automazione Fase 3

> ✅ **COMPLETATO** — Task 1 (sync manuale registry.json), Task 2 (notify-engine.yml), Task 3 (verifica) tutti eseguiti.
> L'architettura finale differisce dal piano originale: usa `notify-engine.yml` (pycode-crafter) + `registry-sync-gateway.yml` (engine) invece di un singolo `sync-registry.yml`.

## Contesto: cosa è successo e perché

Questo progetto fa parte di un ecosistema chiamato SCF (Spark Copilot Framework), composto da tre repo che devono rimanere coerenti tra loro:

- **spark-framework-engine** — il motore centrale
- **scf-pycode-crafter** — questo repo, un pacchetto installabile dal motore
- **scf-registry** — un indice centralizzato che tiene traccia di tutti i pacchetti disponibili

Il principio fondamentale del sistema si chiama *Canonical Truth Architecture*: ogni dato ha una sola fonte autorevole. La versione del pacchetto vive in `package-manifest.json` (questo repo). Il registry (`scf-registry/registry.json`) deve rispecchiare quella versione — non inventarla, non duplicarla a mano.

Il problema attuale: `package-manifest.json` è già alla versione **1.0.1** con `min_engine_version: "1.2.1"`, ma `scf-registry/registry.json` è ancora fermo alla versione **1.0.0** con `engine_min_version: "1.0.0"`. Sono desincronizzati su entrambi i campi perché finora la sincronizzazione veniva fatta manualmente, e questa volta non è stata fatta.

---

## Cosa devi fare — in ordine

### Compito 1 — Sincronizzazione manuale (ultima volta che si fa a mano)

Apri il file `scf-registry/registry.json` nel repo **Nemex81/scf-registry** e aggiorna la voce del pacchetto `scf-pycode-crafter` con i valori corretti:

- `latest_version` → `"1.0.1"`
- `engine_min_version` → `"1.2.1"`
- `updated_at` → timestamp ISO 8601 del momento in cui fai la modifica

Questo chiude il debito corrente. Da questo momento in poi non si tocca più a mano.

### Compito 2 — Implementazione del workflow di automazione

Crea il file `.github/workflows/sync-registry.yml` in **questo repo** (`scf-pycode-crafter`).

Il workflow deve fare questa cosa semplice: ogni volta che qualcuno pusha una modifica a `package-manifest.json` sul branch `main`, il workflow legge automaticamente i dati aggiornati dal manifest e apre una Pull Request sul repo `scf-registry` con i valori corretti già scritti in `registry.json`.

In questo modo il flusso diventa: modifichi il manifest → push → PR aperta automaticamente su scf-registry → fai merge → sistema coerente. Zero lavoro manuale, zero possibilità di dimenticare.

**Dettagli tecnici che il workflow deve rispettare:**

1. Si attiva solo su push a `main` quando cambia `package-manifest.json`
2. Legge dal manifest: il campo `package` (usato come ID), `version`, `min_engine_version`
3. Fa checkout di `scf-registry` usando il secret `REGISTRY_WRITE_TOKEN`
4. Aggiorna `registry.json` cercando la voce con `id == package` e sovrascrivendo `latest_version` e `engine_min_version`
5. Se il pacchetto non viene trovato in `registry.json`, il workflow deve fallire con un errore esplicito (non scrivere silenziosamente dati parziali)
6. Aggiorna il campo `updated_at` con il timestamp corrente
7. Apre una PR su `scf-registry` con branch `sync/<package-id>-<version>`, titolo e corpo descrittivi
8. Usa `peter-evans/create-pull-request@v6` per aprire la PR

**Prerequisito che devi verificare prima di finire:** il valore del campo `package` in `package-manifest.json` deve coincidere esattamente con il campo `id` nella voce corrispondente di `registry.json`. Se non coincidono, segnalalo esplicitamente invece di procedere.

### Compito 3 — Verifica finale

Dopo aver completato i Compiti 1 e 2:

1. Controlla che `scf-registry/registry.json` abbia i valori aggiornati (1.0.1 / 1.2.1)
2. Controlla che `.github/workflows/sync-registry.yml` esista e sia sintatticamente valido
3. Verifica che il campo `package` in `package-manifest.json` corrisponda al campo `id` in `registry.json`
4. Conferma in chat cosa hai fatto e cosa rimane da fare (il secret `REGISTRY_WRITE_TOKEN` deve essere creato manualmente da Nemex81 nelle impostazioni GitHub del repo — non puoi farlo tu)

---

## Cosa NON devi fare

- Non modificare `package-manifest.json` — è la fonte canonica, non si tocca in questo task
- Non modificare il motore (`spark-framework-engine`) — non è coinvolto in questo task
- Non inventare versioni o valori — leggi sempre dal manifest, non hardcodare nulla
- Non creare branch inutili — il workflow va su `main` di questo repo direttamente

---

## Nota per il maintainer (Nemex81)

Dopo che Copilot ha completato il Compito 2, devi fare **una sola cosa manuale** per attivare l'automazione:

Nelle impostazioni di questo repo su GitHub → *Settings → Secrets and variables → Actions* → crea un nuovo secret chiamato `REGISTRY_WRITE_TOKEN` con il valore di un Personal Access Token che abbia permesso di **write** sul repo `scf-registry`.

Senza quel secret il workflow esiste ma non può aprire PR sul registry. Con quel secret, tutto diventa automatico.
