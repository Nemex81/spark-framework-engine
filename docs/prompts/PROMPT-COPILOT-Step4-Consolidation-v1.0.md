# PROMPT COPILOT — Step 4: Analisi Approfondita e Strategia di Consolidamento Finale

**Autore:** Perplexity AI (Coordinatore SPARK Council)
**Data:** 2026-05-08
**Branch target:** `feature/dual-mode-manifest-v3.1`
**Approvazione:** Nemex81 (coordinatore umano)
**Versione prompt:** 1.0
** mode: agent **
** execute_mode: autonomus **

---

## CONTESTO — DOVE SIAMO

Lo Step 3 ha completato la separazione netta tra Universo A (Plugin Manager) e
Universo B (Server MCP puro). Il commit `fb0e96e` del 2026-05-08 dichiara 446 test
passanti, 9 saltati, 0 falliti. Le modifiche principali introdotte sono state:

- `PluginInstaller.install_from_store()` — copia file dall'engine store al workspace.
- `PluginRemover.remove_workspace_files()` — rimozione unificata workspace + plugin files.
- `_install_workspace_files_v3` e `_remove_workspace_files_v3` in `lifecycle.py` deprecati come stub.
- `PluginRegistry` rifattorizzato con dual-backend: manifest-based (preferito) + file-based (legacy).
- `PluginManagerFacade` ora istanziata in `SparkFrameworkEngine._init_runtime_objects()`.

Lo Step 4 ha un obiettivo diverso dagli step precedenti: **non implementa nuove feature**.
Analizza lo stato reale del sistema, identifica tutto il debito tecnico residuo, verifica
la coerenza interna, e produce la **strategia conclusiva** per rendere il branch pronto
a un merge su `main` definitivo, stabile e senza sorprese.

---

## CONTESTO OBBLIGATORIO DA LEGGERE PRIMA DI QUALSIASI AZIONE

Leggi integralmente i seguenti file in ordine prima di eseguire qualunque task:

1. `docs/reports/REPORT-Copilot-Step3-Final.md` — report conclusivo di Step 3 scritto da Copilot.
   Contiene la lista file modificati, test aggiornati e le "Decisioni aperte" non ancora risolte.
2. `docs/reports/REPORT-Copilot-FullDecoupling-Issues.md` — 8 problemi rilevati nella v1.0,
   tutti indirizzati. Usare come riferimento per verificare che nessuna regressione sia
   stata introdotta in Step 3.
3. `docs/reports/REPORT-Copilot-FullDecoupling-v2.0-Validation.md` — stato post-Step 1 e Step 2.
4. `docs/prompts/PROMPT-COPILOT-Step3-Separation-AB-v1.0.md` — prompt Step 3 originale,
   criteri di accettazione e architettura target approvata. Usare come reference normativa.
5. Tutti i file del modulo `spark/plugins/`:
   `__init__.py`, `facade.py`, `installer.py`, `remover.py`, `updater.py`, `registry.py`, `schema.py`
6. `spark/boot/lifecycle.py` — verifica stub deprecati e presenza di logica attiva residua.
7. `spark/boot/engine.py` — verifica init di `PluginManagerFacade` e assenza di scritture dirette workspace.
8. `spark/boot/tools_plugins.py` e `spark/boot/tools_packages_install.py` — entry point MCP
   per i due universi. Verificare la separazione delle responsabilità.
9. `spark/manifest/manifest.py` e `spark/manifest/gateway.py` — componenti invarianti.
   Verificare che non siano stati modificati indirettamente da Step 3.
10. Directory `tests/` — enumerare i file di test relativi a plugins, lifecycle, packages.
    Identificare quelli ancora da aggiornare e quelli già allineati.

**REGOLA ASSOLUTA:** usare esclusivamente i path reali approvati nella tabella ARCHITETTURA TARGET
del prompt Step3. Non usare mai path `spark/core/X`. Non creare file fuori dalla struttura
esistente senza approvazione esplicita di Nemex81.

---

## ARCHITETTURA TARGET DI RIFERIMENTO (invariante)

| Componente | Path reale | Classe |
|---|---|---|
| WorkspaceWriteGateway | `spark/manifest/gateway.py` | `WorkspaceWriteGateway` |
| ManifestManager | `spark/manifest/manifest.py` | `ManifestManager` |
| RegistryClient | `spark/registry/client.py` | `RegistryClient` |
| FrameworkInventory | `spark/inventory/framework.py` | `FrameworkInventory` |
| WorkspaceLocator | `spark/workspace/locator.py` | `WorkspaceLocator` |
| PluginManagerFacade | `spark/plugins/facade.py` | `PluginManagerFacade` |
| PluginInstaller | `spark/plugins/installer.py` | `PluginInstaller` |
| PluginRemover | `spark/plugins/remover.py` | `PluginRemover` |
| PluginUpdater | `spark/plugins/updater.py` | `PluginUpdater` |
| PluginRegistry | `spark/plugins/registry.py` | `PluginRegistry` |

---

## TASK SEQUENZIALI — ESEGUIRE IN ORDINE

### TASK-1 — Analisi approfondita dello stato attuale (sola lettura)

**Obiettivo:** ottenere una fotografia precisa e completa del sistema post-Step 3,
senza assumere che il commit message sia accurato al 100%.

**Azioni:**

1. **Verifica stub lifecycle.py.**
   Leggi `spark/boot/lifecycle.py` integralmente. Per ogni metodo del mixin `_V3LifecycleMixin`:
   - Classifica come: `stub_deprecato` (solo commento, nessuna logica attiva) oppure `attivo_residuo` (contiene ancora logica di scrittura file).
   - Se trovi metodi `attivo_residuo`, elencali con numero di riga.

2. **Verifica dual-backend PluginRegistry.**
   Leggi `spark/plugins/registry.py` integralmente. Rispondi a queste domande precise:
   - Il metodo `register()` usa `ManifestManager.upsert()` come backend primario?
   - Esiste ancora un path di codice che scrive un file `.spark-plugins` separato?
   - Il backend legacy (file-based) ha una condizione di attivazione esplicita o è sempre attivo?
   - Quando viene rimosso il backend legacy? È previsto un meccanismo di migrazione automatica?

3. **Verifica coerenza PluginManagerFacade in engine.py.**
   Leggi `spark/boot/engine.py`, funzione `_init_runtime_objects()`:
   - `PluginManagerFacade` è istanziata e assegnata a `self._plugin_manager`?
   - I parametri di inizializzazione corrispondono allo snippet approvato nel prompt Step3?
   - Esistono altre istanziazioni o riferimenti a `PluginInstaller` / `PluginRemover` diretti
     nell'engine (fuori da `facade.py`)? Se sì, sono anomalie da eliminare.

4. **Verifica separazione in tools_plugins.py e tools_packages_install.py.**
   - `scf_install_plugin` delega a `self._plugin_manager` oppure chiama ancora
     metodi di `lifecycle.py` direttamente?
   - `scf_install_package` (tool v2 legacy) chiama ancora `_install_standalone_files_v3`
     oppure delega correttamente?
   - I due tool hanno responsabilità chiaramente separate e non si sovrappongono?

5. **Censimento debito tecnico residuo.**
   Elenca in forma strutturata tutto ciò che, al termine della lettura, risulta:
   - Pienamente allineato con l'architettura target (VERDE).
   - Funzionalmente corretto ma con codice legacy da pulire (GIALLO — non urgente).
   - Incoerente o potenzialmente fonte di bug (ROSSO — da risolvere prima del merge).

6. **Verifica "Decisioni aperte" da Step3-Final.**
   Leggi la sezione "Decisioni aperte" in `docs/reports/REPORT-Copilot-Step3-Final.md`.
   Per ciascuna decisione aperta, indica se è stata risolta implicitamente durante Step 3
   o se rimane pendente per Nemex81.

**Output atteso TASK-1:** sezione `## Analisi Stato Attuale` nel report finale (vedi TASK-3).

---

### TASK-2 — Strategia conclusiva di consolidamento

**Condizione:** eseguire dopo TASK-1, basandosi esclusivamente sui risultati dell'analisi.

**Obiettivo:** definire la sequenza minima di interventi necessari a portare il branch
in stato di merge-ready su `main`, senza introdurre nuove feature o refactoring non necessari.

**Azioni:**

1. **Per ogni voce ROSSA** identificata nel censimento TASK-1 punto 5:
   - Descrivi l'intervento correttivo minimo necessario.
   - Indica il file e il punto esatto di modifica (numero di riga se possibile).
   - Stima l'impatto sui test esistenti (nessuno / aggiornamento mock / riscrittura fixture).
   - Assegna una priorità: `BLOCCANTE` (deve essere risolto prima della PR) oppure
     `POST-MERGE` (può essere tracciato come issue separato).

2. **Per ogni voce GIALLA** con codice legacy:
   - Valuta se il cleanup è semplice abbastanza da includerlo in questo branch
     (massimo 15 righe di modifica per voce) oppure va tracciato come issue separato.
   - Se incluso: descrivi la modifica. Se rinviato: scrivi il titolo dell'issue da aprire.

3. **Verifica test coverage post-Step3.**
   - Tutti i test dichiarati passanti nel commit Step3 coprono i nuovi path di codice
     (`install_from_store`, `remove_workspace_files`, dual-backend registry)?
   - Esistono path critici non coperti da alcun test? Se sì, elencali.
   - Se mancano test su path critici, proponi i titoli dei test da aggiungere
     (senza scriverli — la decisione di includerli spetta a Nemex81).

4. **Verifica PR-readiness.**
   Controlla i criteri di accettazione del prompt Step3 (sezione CRITERI DI ACCETTAZIONE FINALI)
   uno per uno e indica per ciascuno: `SODDISFATTO` / `PARZIALMENTE SODDISFATTO` / `NON SODDISFATTO`.
   Per quelli non pienamente soddisfatti, indica cosa manca esattamente.

5. **Proponi la strategia conclusiva** come piano in step ordinati:
   - Step A: interventi BLOCCANTI (se esistono).
   - Step B: cleanup GIALLI inclusi nel branch (se valutati semplici).
   - Step C: apertura issue per debito tecnico rinviato.
   - Step D: apertura PR su main con checklist.
   
   Se nessun intervento BLOCCANTE è emerso dall'analisi, dichiara esplicitamente:
   *"Il branch è merge-ready. Nessuna anomalia bloccante rilevata."*
   e procedi direttamente con Step D.

**Output atteso TASK-2:** sezione `## Strategia di Consolidamento` nel report finale (vedi TASK-3).

---

### TASK-3 — Produzione del report conclusivo

**Condizione:** eseguire dopo TASK-2.

**Azioni:**

Scrivi il file `docs/reports/REPORT-Copilot-Step4-Consolidation.md` con la seguente struttura:

```
# REPORT Step 4 — Analisi e Strategia di Consolidamento
## Metadati
## Executive Summary
## Analisi Stato Attuale
  ### Stub lifecycle.py
  ### Dual-backend PluginRegistry
  ### PluginManagerFacade in engine.py
  ### Separazione tool MCP
  ### Censimento debito tecnico (VERDE / GIALLO / ROSSO)
  ### Decisioni aperte da Step 3
## Strategia di Consolidamento
  ### Interventi BLOCCANTI (se presenti)
  ### Cleanup GIALLI inclusi nel branch (se presenti)
  ### Issue da aprire (debito tecnico rinviato)
  ### Verifica PR-readiness (checklist criteri Step 3)
  ### Piano conclusivo step A→D
## Conclusione
  ### Dichiarazione di merge-readiness (o lista pendenze)
  ### Decisioni che richiedono approvazione di Nemex81
```

Il report deve essere auto-consistente: un lettore che non ha letto i report precedenti
deve poter capire lo stato del sistema e le decisioni necessarie.

**Tono:** tecnico, preciso, senza giudizi soggettivi. Fatti, numeri di riga, nomi di funzione.

---

### TASK-4 — Esecuzione interventi BLOCCANTI (solo se necessario)

**Condizione:** eseguire SOLO se TASK-2 ha identificato interventi classificati come BLOCCANTI.
Se nessun intervento BLOCCANTE è emerso, saltare questo task e passare a TASK-5.

**Azioni:**

1. Esegui in sequenza gli interventi BLOCCANTI descritti nella strategia di TASK-2.
2. Dopo ogni modifica, verifica che i test correlati passino (`pytest` sul sottoinsieme rilevante).
3. Se durante un intervento emerge un'anomalia non prevista, sospendi e applica
   la procedura GESTIONE ANOMALIE descritta più avanti.
4. Al termine, aggiorna la sezione "Interventi BLOCCANTI" del report TASK-3 con:
   - Stato finale: `ESEGUITO` per ogni intervento completato.
   - Numero di righe modificate per file.
   - Risultato test: `N passed, M skipped, 0 failed`.

---

### TASK-5 — Apertura PR su main

**Condizione:** eseguire SOLO se tutti i test passano e nessun intervento BLOCCANTE è rimasto aperto.

**Azioni:**

1. Apri la PR da `feature/dual-mode-manifest-v3.1` → `main` con:
   - **Titolo:** `feat: Full Decoupling Architecture v2.0 — Consolidamento finale post-Step 3`
   - **Corpo:** vedi template qui sotto.

2. **Template corpo PR:**

```markdown
## Descrizione

Consolida la separazione netta tra Universo A (Plugin Manager) e Universo B (Server MCP puro),
introdotta in Step 3. Questo branch rappresenta lo stato finale dell'architettura
Full Decoupling v2.0 approvata dal SPARK Council.

## Report di riferimento

- [Analisi problemi v1.0](docs/reports/archiviati/REPORT-Copilot-FullDecoupling-Issues.md)
- [Validazione v2.0](docs/reports/archiviati/REPORT-Copilot-FullDecoupling-v2.0-Validation.md)
- [Step 3 — Final](docs/reports/REPORT-Copilot-Step3-Final.md)
- [Step 4 — Consolidamento](docs/reports/REPORT-Copilot-Step4-Consolidation.md)

## Criteri di accettazione Step 3 — Stato finale

- [ ] `spark/plugins/installer.py` contiene logica scrittura file (ex lifecycle v3)
- [ ] `spark/plugins/remover.py` contiene logica rimozione file (ex lifecycle v3)
- [ ] `spark/boot/lifecycle.py` contiene solo stub deprecati
- [ ] `spark/boot/engine.py` inizializza `PluginManagerFacade` in `_init_runtime_objects()`
- [ ] `spark/boot/tools_plugins.py` delega a `self._plugin_manager`
- [ ] `spark/plugins/registry.py` usa `ManifestManager.upsert()` / `remove_entry()`
- [ ] Tutti i test passano (0 failures)
- [ ] `REPORT-Copilot-Step3-Final.md` scritto con conferme esplicite
- [ ] `REPORT-Copilot-Step4-Consolidation.md` scritto con strategia conclusiva

## Decisioni aperte

<!-- Lista delle decisioni che richiedono approvazione di Nemex81 prima o dopo il merge -->

## Issue aperti (debito tecnico rinviato)

<!-- Lista dei titoli issue da aprire dopo il merge -->

## Test

`pytest` — N passed, M skipped, 0 failed
```

3. **NON mergiare la PR.** La decisione di merge spetta esclusivamente a Nemex81.

---

## GESTIONE ANOMALIE IN CORSO D'OPERA

### Quando sospendere il task principale

Sospendi e apri un task parallelo di correzione se incontri:

- Import rotto che causa `ModuleNotFoundError` o `ImportError` all'avvio engine.
- Dipendenza circolare tra moduli `spark/plugins/` → `spark/boot/` → `spark/plugins/`.
- Test che fallisce per motivi non correlati allo step corrente (bug preesistente).
- File atteso dal codebase ma non presente nel repo.
- Entry duplicate o corrotte in `.spark-manifest.json` causate da conflitto
  tra `ManifestManager` e `PluginRegistry`.

### Procedura task parallelo

1. Documenta l'anomalia nella sezione `## Anomalie Rilevate` del report TASK-3
   (descrizione, file coinvolti, impatto).
2. Risolvi in isolamento senza toccare i file del task sospeso.
3. Verifica la correzione con i test rilevanti.
4. Riprendi il task principale dal punto di sospensione.

### Anomalie che non richiedono sospensione

Gestisci inline senza sospendere:

- Warning non bloccanti da `pytest`.
- Aggiornamento import path da `spark/core/X` al path reale (PROBLEMA-1 del report Issues).
- Correzione nome funzione errato (PROBLEMA-2).
- Aggiornamento snippet init (PROBLEMA-3).
- Attivazione/disattivazione logging `sys.stderr` non correlata alla logica business.

---

## LIMITI E DIVIETI

- **Non mergiare mai la PR senza approvazione esplicita di Nemex81.**
- **Non modificare** `spark/manifest/gateway.py`, `spark/manifest/manifest.py`,
  `spark/registry/client.py`, `spark/workspace/locator.py`, `spark/inventory/framework.py`.
  Sono invarianti architetturali — nessuna modifica, nemmeno di commenti.
- **Non modificare** la firma pubblica MCP (nome tool, parametri input/output JSON)
  di nessun tool esistente.
- **Non cancellare** i metodi stub deprecati in `lifecycle.py` — lasciarli con commento
  `# DEPRECATED` fino al cleanup esplicito approvato da Nemex81.
- **Non usare `print()` o scrivere su `stdout`** — il canale JSON-RPC è esclusivo.
  Logging esclusivamente su `sys.stderr` con formato `[SPARK-ENGINE][DEBUG/INFO/ERROR] Messaggio`.
- **Non prendere decisioni architetturali autonome.** Se trovi uno scenario non coperto
  da questo prompt, scrivi la domanda nella sezione "Decisioni che richiedono approvazione
  di Nemex81" del report e aspetta approvazione.
- **Non creare nuovi file di codice** non esplicitamente previsti da questo prompt.
  Questo step è di analisi e consolidamento, non di implementazione.

---

## CRITERI DI SUCCESSO DELLO STEP 4

Lo Step 4 è completato con successo quando:

- [ ] `docs/reports/REPORT-Copilot-Step4-Consolidation.md` è scritto e auto-consistente.
- [ ] Ogni componente del sistema è classificato come VERDE, GIALLO o ROSSO con motivazione.
- [ ] Tutti i criteri di accettazione Step 3 sono verificati e il loro stato è documentato.
- [ ] La strategia conclusiva (step A→D) è formulata in modo esplicito e azionabile.
- [ ] Se interventi BLOCCANTI esistevano: sono stati eseguiti, testati e documentati.
- [ ] PR aperta (non mergiata) su `main` con corpo completo e checklist aggiornata.
- [ ] Le "Decisioni aperte" sono enumerate chiaramente nel report e nel corpo PR.

---

*Prompt generato da Perplexity AI (Coordinatore SPARK Council) — approvato da Nemex81.*
*Basato su analisi post-Step3: commit fb0e96e, 446 test passanti, 2026-05-08.*
