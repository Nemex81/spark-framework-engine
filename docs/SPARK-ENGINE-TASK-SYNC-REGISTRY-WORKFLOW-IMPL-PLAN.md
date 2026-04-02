# SPARK System — Piano Tecnico di Implementazione
## Sync Registry, Workflow di Rilascio e Completamento Sistema

**Data:** 2026-03-31
**Versione:** 1.0
**Stato:** ✅ implementato
**Documento di riferimento analizzato:** `SCF-CANONICAL-TRUTH-IMPL-PLAN.md`
**Autore analisi:** GitHub Copilot

---

## Parte 1 — Convalida del Progetto Logico

### Documento analizzato

`docs/SCF-CANONICAL-TRUTH-IMPL-PLAN.md` — Canonical Truth Architecture (v1, 2026-03-31, stato dichiarato: ✅ completato).

### Criteri di convalida applicati

| Criterio | Verifica | Esito |
|---|---|---|
| Coerenza architetturale | Ogni dato ha esattamente una fonte canonica; nessuna circolarità | ✅ PASS |
| Correttezza tecnica | Implementazioni Level 1/2 verificate su codice reale | ✅ PASS |
| Consistenza interna | Sequenza Level 1→2→3→4 è ordinata e senza dipendenze cicliche | ✅ PASS |
| Completezza | Casi limite e tech debt documentati esplicitamente | ✅ PASS |
| Compatibilità di sistema | Non viola i confini tra i tre livelli SPARK | ✅ PASS |

### Evidenze rilevate sull'implementazione corrente

**Level 1 (test di coerenza interna) — ✅ IMPLEMENTATO**
- `tests/test_engine_coherence.py` esiste e verifica tool counter + ENGINE_VERSION/CHANGELOG alignment
- Guard in `scf_remove_package` (righe 1394–1403): implementata esattamente come specificata
- Tool counter allineato: `Tools (23)` nel commento di classe, `Tools registered: 23 total` nel log, 23 decorator `@self._mcp.tool()` nel sorgente

**Level 2 (tool `scf_verify_system`) — ✅ IMPLEMENTATO**
- `scf_verify_system` presente a riga 1439, logica identica alla specifica
- Gestisce edge case `manifest_empty`, rileva `registry_stale` e `engine_min_mismatch`
- ENGINE_VERSION = `1.3.0` allineata con il bump minor atteso dalla Fase 2

**Level 3 (GitHub Action sync-registry) — ⏳ PENDENTE**
- Workflow `sync-registry.yml` non esiste ancora in `scf-pycode-crafter`
- Prerequisito REGISTRY_WRITE_TOKEN non creato
- Ultima sincronizzazione manuale di `registry.json` non ancora eseguita

**Level 4 (protocollo di rilascio formale) — ⏳ PARZIALMENTE PENDENTE**
- Skill `scf-release-check` esiste in `.github/skills/scf-release-check/SKILL.md`
- Sezione "Protocollo di rilascio pacchetto" non ancora aggiunta a `SCF-PROJECT-DESIGN.md`
- BLOCCO E in `SCF-CORRECTIVE-PLAN.md` non chiuso (E2, E3, E4 sono implementati ma ancora marcati "⏳")

**Sistema più avanzato del dichiarato — strumenti aggiuntivi rilevati**

La `SCF-CORRECTIVE-PLAN.md` riporta E2, E3, E4 come "⏳ da fare", ma l'implementazione reale li ha già completati:
- `RegistryClient.fetch_package_manifest()` — implementato (usato in `scf_install_package` riga 1150)
- `scf_install_package` — logica reale completa (righe 1127–1386): engine version check, dipendenze, conflitti, file ownership policy
- `scf_remove_package` — implementato (righe 1387–1409)
- Strumenti aggiuntivi non previsti dal piano originale: `scf_apply_updates`, `scf_get_package_changelog`, `scf_verify_workspace`

### Esito convalida

> **✅ PASS** — Il progetto logico è architetturalmente coerente, tecnicamente corretto e sistematicamente completo. I livelli 1 e 2 sono pienamente implementati. I livelli 3 e 4 sono ben specificati, fattibili e privi di ambiguità architetturali. Il documento è idoneo come base per il piano tecnico di implementazione.

---

## Parte 2 — Mappa dello Stato Attuale del Sistema SPARK

### Livello 1 — `spark-framework-engine`

| Componente | Stato | Note |
|---|---|---|
| Motore MCP (FastMCP, stdio) | ✅ | ENGINE_VERSION 1.3.0 |
| 23 tool MCP | ✅ | Tutti implementati e contatori allineati |
| 14 resource MCP | ✅ | 4 list + 4 template + 6 singleton |
| ManifestManager | ✅ | Lettura, scrittura, SHA-256, remove, verify_integrity |
| RegistryClient | ✅ | Fetch registry.json, cache offline, fetch_package_manifest |
| Parser frontmatter dual-format | ✅ | Scalar + liste YAML inline/block |
| Discovery skill dual-format | ✅ | Legacy flat + standard SKILL.md in subdir |
| Suite di test | ✅ | 6 file test, inclusi coerenza, manifest, installation policies |
| Agente maintainer | ✅ | `.github/agents/spark-engine-maintainer.agent.md` |
| 6 skill maintainer | ✅ | changelog, release-check, coherence-audit, prompt-management, tool-development, documentation |
| 8 prompt package management | ✅ | install, remove, update, check-updates, status, list-available, list-installed, package-info |
| Istruzioni maintainer | ✅ | `.github/instructions/spark-engine-maintenance.instructions.md` |
| Documentazione doc allineata | ⚠️ | SCF-CORRECTIVE-PLAN.md ha E2/E3/E4 ancora marcati "⏳"; SCF-PROJECT-DESIGN.md manca "Protocollo rilascio" |

### Livello 2 — `scf-pycode-crafter`

| Componente | Stato | Note |
|---|---|---|
| Repo esistente | ✅ | Pacchetto dominio Python operativo |
| `package-manifest.json` | ❓ | Da verificare: versione attuale, campo `min_engine_version`, elenco `files` aggiornato |
| GitHub Action `sync-registry.yml` | ❌ | Non esiste ancora |
| Secret `REGISTRY_WRITE_TOKEN` | ❌ | Non creato |
| Test cross-repo (package.id == registry.id) | ❌ | Non esiste |

### Livello 3 — `scf-registry`

| Componente | Stato | Note |
|---|---|---|
| Repo esistente | ✅ | Pubblico, read-only per utenti |
| `registry.json` | ⚠️ | Potrebbe essere stale rispetto allo stato reale di `scf-pycode-crafter` |
| Processo aggiornamento | ❌ | Attualmente manuale; GitHub Action non ancora attiva |

---

## Parte 3 — Piano Tecnico di Implementazione

### Principio di ordinamento

Il piano rispetta la **gerarchia delle fonti canoniche**:
```
package-manifest.json (scf-pycode-crafter)
         ↓  [GitHub Action]
   registry.json (scf-registry)
         ↓  [HTTP GET, motore]
  scf_verify_system / scf_install_package
```

Nessuna fase dipende da infrastruttura non ancora disponibile dalla fase precedente.

---

### Fase 1 — Allineamento documentazione motore
**Repo:** `spark-framework-engine` | **Priorità:** Alta | **Costo stimato:** 30 minuti

Questa fase ha zero rischi: solo aggiornamenti documentali nel repo del motore.

#### Task 1.1 — Aggiornare SCF-CORRECTIVE-PLAN.md

Marcare come `✅ completato` i blocchi che l'implementazione ha già risolto:

- **E2** `RegistryClient.fetch_package_manifest()` → ✅ (implementato in righe 1150/1468 del motore)
- **E3** Logica reale `scf_install_package` → ✅ (implementato righe 1127–1386)
- **E4** Tool `scf_remove_package` → ✅ (implementato righe 1387–1409)

Aggiornare la tabella "Stato avanzamento complessivo" in fondo al documento.

Aggiungere nota: "BLOCCO E chiuso il 2026-03-31 — tutti i task E implementati nel motore v1.3.0".

#### Task 1.2 — Aggiungere sezione "Protocollo di rilascio pacchetto" a SCF-PROJECT-DESIGN.md

Inserire tra "Versioning del Motore" e "Limiti noti" la nuova sezione che documenta:

1. **Gerarchia fonti canoniche** (tabella da SCF-CANONICAL-TRUTH-IMPL-PLAN.md)
2. **Confini di responsabilità tra componenti** (motore, registry, pacchetto)
3. **Ciclo di vita di un rilascio pacchetto:**
   ```
   Modifica package-manifest.json
       → push su main
       → GitHub Action (sync-registry.yml)
       → PR auto-generata su scf-registry
       → merge PR
       → scf_verify_system verde = rilascio completo
   ```
4. **Gate obbligatori pre-tag:** `scf_verify_system` verde, CHANGELOG aggiornato, ENGINE_VERSION allineata

#### Task 1.3 — Aggiornare "Prossimi Passi" in SCF-PROJECT-DESIGN.md

Barrare come completato:
- Punto 2 (tool installazione intelligente + manifesto) → ✅
- Punto 3 (repo scf-registry) → ✅

#### Task 1.4 — Bump patch CHANGELOG e ENGINE_VERSION

Dopo i task 1.1–1.3: bump patch `1.3.1` per documentazione allineata.
Aggiornare `CHANGELOG.md` e `ENGINE_VERSION` in `spark-framework-engine.py`.

**Definizione di completamento Fase 1:**
- SCF-CORRECTIVE-PLAN.md: tutti i task E marcati ✅
- SCF-PROJECT-DESIGN.md: sezione "Protocollo di rilascio" presente
- ENGINE_VERSION = 1.3.1
- pytest -q verde

---

### Fase 2 — Setup sync automatico registry
**Repo:** `scf-pycode-crafter` | **Priorità:** Alta | **Costo stimato:** 1-2 ore

Questa fase introduce l'automazione cross-repo. È l'unica con side effect su repository esterni.

#### Task 2.1 — Verificare e aggiornare `package-manifest.json`

Verificare che `package-manifest.json` nella root di `scf-pycode-crafter` contenga:

```json
{
  "package": "scf-pycode-crafter",
  "version": "<versione corrente>",
  "min_engine_version": "1.3.0",
  "files": [
    ".github/copilot-instructions.md",
    ".github/project-profile.md",
    ".github/AGENTS.md",
    ".github/agents/<nome-agente>.md",
    "... tutti i file SCF del pacchetto ..."
  ]
}
```

Verificare che il campo `package` (es. `"scf-pycode-crafter"`) coincida esattamente con il campo `id` in `registry.json`. Questo è il prerequisito del workflow.

#### Task 2.2 — Creare test cross-repo `package_id == registry_id`

In `scf-pycode-crafter`, aggiungere test automatico (da eseguire in CI) che:

```python
# Legge package-manifest.json locale
# Legge registry.json remoto (o da cache locale)
# Asserta che package["package"] == entry["id"] in registry
```

Questo test fallisce visibilmente prima che il workflow tenti una sincronizzazione impossibile.

#### Task 2.3 — Creare `.github/workflows/sync-registry.yml`

Aggiungere il workflow in `scf-pycode-crafter` esattamente come specificato in `SCF-CANONICAL-TRUTH-IMPL-PLAN.md` (Livello 3), con le due correzioni già incorporate nel documento:

1. Guard Python esplicita: se `pkg_id` non è in `registry.json`, `raise ValueError` descrittivo (no scrittura silenziosa)
2. Trigger: `push` su `main`, path filter `package-manifest.json`

**Aggiunta rispetto alla specifica originale:** aggiungere step di notifica failure via `actions/github-script` che apre un'issue di warning in caso di errore del workflow.

#### Task 2.4 — Creare GitHub Secret `REGISTRY_WRITE_TOKEN`

- Creare PAT con scope `repo` (write su `scf-registry`)
- Registrarlo come secret `REGISTRY_WRITE_TOKEN` in `scf-pycode-crafter`
- Durata consigliata: 1 anno con promemoria rinnovo

#### Task 2.5 — Test del workflow su branch

Prima del merge in main:
1. Creare branch `test/sync-workflow` in `scf-pycode-crafter`
2. Modificare `package-manifest.json` (bump versione test)
3. Verificare che la PR arrivi su `scf-registry` con i valori corretti
4. Fare merge su `scf-registry` e verificare `registry.json` aggiornato
5. Ripristinare `package-manifest.json` alla versione reale
6. Merge su `main` di `scf-pycode-crafter`

**Definizione di completamento Fase 2:**
- `package-manifest.json` verificato e aggiornato
- `sync-registry.yml` attivo in CI
- `REGISTRY_WRITE_TOKEN` configurato
- Test branch completato con successo
- PR auto-generata su `scf-registry` verificata e mergiata nel test

---

### Fase 3 — Allineamento manuale finale del registry
**Repo:** `scf-registry` | **Priorità:** Alta | **Eseguire:** prima o in parallelo con Fase 2

Questa è l'**ultima sincronizzazione manuale** prevista dall'architettura. Dopo questa fase, ogni aggiornamento è automatico.

#### Task 3.1 — Verificare stato attuale di `registry.json`

Aprire `scf-registry/registry.json` e verificare:
- `latest_version` di ogni pacchetto coincide con il `version` nel `package-manifest.json` del pacchetto
- `engine_min_version` di ogni pacchetto coincide con `min_engine_version` nel `package-manifest.json`
- Campo `updated_at` è recente

#### Task 3.2 — Eseguire `scf_verify_system` come test di accettazione

Dopo l'allineamento manuale, eseguire `scf_verify_system` su un workspace con almeno un pacchetto installato.

Risultato atteso:
```json
{
  "is_coherent": true,
  "issues": [],
  "packages_checked": 1
}
```

Se `is_coherent: false`, correggere le discrepanze riportate prima di procedere.

**Definizione di completamento Fase 3:**
- `registry.json` allineato con tutti i `package-manifest.json` dei pacchetti
- `scf_verify_system` restituisce `is_coherent: true`

---

### Fase 4 — Validazione end-to-end del sistema completo
**Scope:** tutti e tre i livelli | **Priorità:** Alta | **Eseguire:** dopo Fase 2 e 3

Questa fase non crea nuovo codice: verifica che il sistema funzioni come sistema integrato.

#### Task 4.1 — Test ciclo completo install/verify/remove

Su un workspace di test pulito (senza `.github/`):
1. `scf_list_available_packages()` → deve restituire almeno `scf-pycode-crafter`
2. `scf_get_package_info("scf-pycode-crafter")` → deve restituire metadati completi e lista file
3. `scf_install_package("scf-pycode-crafter")` → deve installare tutti i file nel `.github/` locale
4. `scf_list_installed_packages()` → deve mostrare il pacchetto installato con versione
5. `scf_verify_system()` → deve restituire `is_coherent: true`
6. `scf_remove_package("scf-pycode-crafter")` → deve rimuovere i file non modificati
7. `scf_list_installed_packages()` → deve mostrare lista vuota o solo file preservati

#### Task 4.2 — Test ciclo completo update

Su un workspace con un pacchetto installato in versione precedente:
1. `scf_update_packages()` → deve riportare `update_available`
2. `scf_apply_updates()` → deve aggiornare alla versione più recente
3. `scf_verify_system()` → deve restituire `is_coherent: true`

#### Task 4.3 — Test comportamento offline

Con accesso di rete bloccato temporaneamente:
1. `scf_list_available_packages()` → deve usare cache e rispondere normalmente
2. `scf_verify_system()` → deve restituire warning leggibili, non crash

**Definizione di completamento Fase 4:**
- Tutti e tre i task superati senza errori imprevisti
- Nessun crash, nessun dato silenziosamente inconsistente

---

### Fase 5 — Estensione protocollo di rilascio in scf-release-check
**Repo:** `spark-framework-engine` | **Priorità:** Media | **Eseguire:** dopo Fase 4

#### Task 5.1 — Aggiornare skill `scf-release-check`

Aggiungere alla skill i due passi descritti in SCF-CANONICAL-TRUTH-IMPL-PLAN.md (Level 4):

**Passo aggiuntivo 1:** Invocare `scf_verify_system` come gate obbligatorio. Se `is_coherent: false` o `issues` contiene `registry_stale`, il check deve riportare **CRITICAL** e bloccare il rilascio.

**Passo aggiuntivo 2:** Estendere la proposta tag con checklist post-tag:
- [ ] Verificare che la GitHub Action abbia aperto la PR su `scf-registry`
- [ ] Controllare che la PR sia stata mergiata
- [ ] Eseguire `scf_verify_system` post-merge per conferma finale
- [ ] Solo dopo: dichiarare rilascio completo

#### Task 5.2 — Bump minor e CHANGELOG

Aggiornamento skill = nuovo comportamento della skill → bump minor `1.4.0`.

**Definizione di completamento Fase 5:**
- Skill `scf-release-check` include gate `scf_verify_system`
- ENGINE_VERSION = 1.4.0
- CHANGELOG aggiornato

---

### Fase 6 — Ottimizzazioni e backlog (bassa priorità)

Questi task non bloccano nessuna altra fase e possono essere eseguiti in qualsiasi ordine futuro.

| Task | Repo | Descrizione | Motivazione |
|---|---|---|---|
| C1 — Caching FrameworkInventory | spark-framework-engine | Aggiungere cache in-memory con TTL per `list_agents()`, `list_skills()`, etc. | Performance su progetti con molti file SCF |
| Parallel fetch in `scf_verify_system` | spark-framework-engine | Sostituire loop sequenziale con `asyncio.gather` per fetch parallelo dei manifesti | Con N pacchetti, N chiamate HTTP in serie |
| Notifica failure GitHub Action | scf-pycode-crafter | Step `actions/github-script` che apre issue se `sync-registry.yml` fallisce | Evita registry silenziosamente stale su token scaduto/rate limit |
| Supporto registry privati (v2) | spark-framework-engine | Gestire URL non `raw.githubusercontent.com` con autenticazione opzionale | Pacchetti privati aziendali |

---

## Parte 4 — Architettura del Flusso Completo

### Flusso di rilascio di un pacchetto (dopo implementazione completa)

```
Developer (scf-pycode-crafter)
   │
   ├── [1] Modifica package-manifest.json
   │       (unica fonte canonica della versione pacchetto)
   │
   └── [2] Push su main
           │
           ▼
   GitHub Actions (sync-registry.yml)
           │
           ├── Legge: package, version, min_engine_version da manifest
           ├── Apre PR su scf-registry con registry.json aggiornato
           │
           ▼
   Admin (scf-registry)
           │
           └── [3] Merge PR
                   │
                   ▼
           registry.json aggiornato
                   │
                   ▼
   Utente (qualsiasi workspace)
           │
           ├── scf_verify_system() → is_coherent: true
           ├── scf_update_packages() → update_available per scf-pycode-crafter
           └── scf_apply_updates() → workspace aggiornato
```

### Flusso di installazione da zero

```
Utente (workspace vuoto)
   │
   ├── scf_list_available_packages()
   │       → HTTP GET registry.json (con fallback cache)
   │
   ├── scf_get_package_info(id)
   │       → HTTP GET package-manifest.json (sempre fresco)
   │
   └── scf_install_package(id)
           │
           ├── Verifica compatibilità engine
           ├── Verifica dipendenze e conflitti
           ├── Download file per file via raw URL
           ├── Guard: salta file user-modified
           └── Aggiorna .scf-manifest.json locale
```

---

## Parte 5 — Criteri di Completamento del Sistema

Il sistema SPARK è da considerarsi **completo per la v1** quando:

1. ✅ Motore funzionante con 23 tool e full package management *(già raggiunto)*
2. ✅ Agente maintainer con skill e istruzioni operative *(già raggiunto)*
3. ✅ Prompt slash command per il ciclo di vita dei pacchetti *(già raggiunto)*
4. ⏳ Documentazione allineata (CORRECTIVE-PLAN, PROJECT-DESIGN) *(Fase 1)*
5. ⏳ GitHub Action di sync registry attiva *(Fase 2)*
6. ⏳ registry.json manualmente allineato per l'ultima volta *(Fase 3)*
7. ⏳ Ciclo end-to-end install/verify/update validato *(Fase 4)*
8. ⏳ Skill `scf-release-check` con gate `scf_verify_system` *(Fase 5)*

**Definizione finale:** un developer che rilascia una nuova versione di un pacchetto SCF deve eseguire esattamente **tre azioni manuali** — modifica manifesto, push, merge PR. Tutto il resto è automatico, verificato e irreversibilmente tracciato.

---

## Dipendenze tra fasi

```
Fase 1 (doc)
    │
    ├── [indipendente da Fase 2/3]
    │
Fase 2 (sync) ──────┐
    │               │
Fase 3 (registry) ──┤
                    │
                    ▼
              Fase 4 (e2e)
                    │
                    ▼
              Fase 5 (release-check)
                    │
                    ▼
              Fase 6 (ottimizzazioni)
```

Fasi 1, 2 e 3 possono procedere in parallelo tra loro.
Fase 4 richiede Fasi 2 e 3 complete.
Fase 5 richiede Fase 4 completa.
Fase 6 è sempre opzionale.

---

*Documento creato il 2026-03-31 — analisi di convalida e piano tecnico post-validazione.*
*Documento di riferimento: `SCF-CANONICAL-TRUTH-IMPL-PLAN.md`*
*Stato sistema al momento della redazione: ENGINE_VERSION 1.3.0, Fase 1-2 di SCF-CANONICAL-TRUTH-IMPL-PLAN completate.*
