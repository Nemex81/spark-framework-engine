# PROMPT — Analisi Full Decoupling Architecture v1.0

**Destinatario:** GitHub Copilot (Implementatore)
**Emesso da:** Perplexity AI (Coordinatore)
**Approvato da:** Nemex81 (Coordinatore Generale)
**Branch di lavoro:** `feature/dual-mode-manifest-v3.1`
**Documento di riferimento:** `docs/SPARK-DESIGN-FullDecoupling-v1.0.md`
**Priorità:** ALTA — blocca il proseguimento del branch corrente

---

## Contesto

Il branch `feature/dual-mode-manifest-v3.1` contiene il lavoro in corso per
la gestione dei deployment modes (Cat. A / Cat. B) nei pacchetti SPARK.
Prima di procedere con ulteriori modifiche su quel branch, il Coordinatore
ha proposto un cambio di approccio architetturale radicale descritto nel
documento `docs/SPARK-DESIGN-FullDecoupling-v1.0.md`.

Il tuo compito in questo task è esclusivamente **analisi e validazione**.
Non implementare nulla. Non modificare file di codice.

---

## Obiettivo del Task

Eseguire una validazione tecnica indipendente del design proposto rispetto
allo stato attuale del codebase. Al termine produrre uno dei due output
definiti nella sezione OUTPUT di questo prompt.

---

## Fase 1 — Lettura del Design Document

Leggi integralmente il file:

```
docs/SPARK-DESIGN-FullDecoupling-v1.0.md
```

Prendi nota delle sezioni critiche:

- §2: architettura a due livelli e flussi di chiamata
- §3: moduli nuovi da creare (`spark/plugins/` e relative firme)
- §4: moduli esistenti da modificare (`lifecycle.py`, `tools_packages_install.py`, `engine.py`)
- §5: invarianti architetturali (componenti da NON toccare)
- §6: strategia di migrazione a 3 passi
- §7: relazione con il lavoro già prodotto nel branch corrente

---

## Fase 2 — Analisi del Sistema Attuale

Per ogni file elencato qui sotto, leggi il contenuto attuale sul branch
`feature/dual-mode-manifest-v3.1` e cataloga:

- Funzioni/classi presenti
- Dipendenze importate
- Responsabilità effettive (non quelle dichiarate nei commenti, quelle reali)
- Punti di contatto con il filesystem del workspace utente
- Punti di contatto con lo store interno dell'engine

**File da analizzare:**

```
spark/boot/lifecycle.py
spark/boot/tools_packages_install.py
spark/boot/engine.py
spark/core/workspace_write_gateway.py
spark/core/manifest_manager.py
spark/core/registry_client.py
spark/core/framework_inventory.py
spark/core/workspace_locator.py
```

Se un file non esiste nel branch, annotalo e spiega l'impatto.

---

## Fase 3 — Validazione dell'Impatto

Per ciascuna delle modifiche proposte nel design doc, rispondi alle domande
seguenti con risposta binaria (COMPATIBILE / INCOMPATIBILE) e motivazione
testuale precisa:

### 3.1 Nuovo package `spark/plugins/`

- Il path `spark/plugins/` è libero nel codebase attuale?
- I 6 moduli proposti (`facade.py`, `registry.py`, `installer.py`,
  `remover.py`, `updater.py`, `schema.py`) hanno conflitti di nome con
  moduli esistenti?
- `PluginManagerFacade` può usare `WorkspaceWriteGateway` e `ManifestManager`
  come indicate in §5 senza modificarle?
- `RegistryClient` ha un'interfaccia pubblica sufficiente per essere
  riutilizzata in `spark/plugins/registry.py` senza modifiche?

### 3.2 Modifica `lifecycle.py`

- Le funzioni `_install_workspace_files_v3` e `_install_plugin_files_v3`
  esistono nel file attuale?
- Ci sono dipendenze inverse: altri moduli che chiamano queste funzioni
  direttamente (non tramite `lifecycle.py`)?
- Rimuovere queste funzioni da `lifecycle.py` rompe test esistenti?
  Se sì, quali test e come vanno aggiornati?

### 3.3 Modifica `tools_packages_install.py`

- Il tool `scf_install_package` contiene logica `plugin_files` inline?
- La firma proposta per `scf_install_plugin` (thin facade che chiama
  `_plugin_manager.install(pkg_id)`) è compatibile con il protocollo
  MCP FastMCP usato dall'engine?
- La distinzione `scf_install_package` (engine) vs `scf_install_plugin`
  (workspace) introduce ambiguità nel tool registry MCP?

### 3.4 Modifica `engine.py`

- Dove avviene attualmente l'inizializzazione dei componenti core
  (`WorkspaceLocator`, `ManifestManager`, ecc.)?
- L'aggiunta di `PluginManagerFacade` come dipendenza iniettata
  è compatibile con il pattern di inizializzazione esistente?
- Ci sono cicli di dipendenza potenziali tra `PluginManagerFacade`
  e i componenti già inizializzati in quel punto del boot?

### 3.5 Backward compatibility

- Esistono workspace utente con file installati tramite `workspace_files`
  (schema v3.0) che verrebbero rotti dalla migrazione?
- Il meccanismo di ricostruzione di `.github/.spark-plugins` descritto
  in §6.1 è sufficiente a garantire la compatibilità?
- Il campo `workspace_files` deprecato nei manifest v3.0 è presente
  nei `package-manifest.json` dei repo `scf-master-codecrafter` e
  `scf-pycode-crafter`? Verifica entrambi i file.

---

## Fase 4 — Verifica Suite di Test

Analizza i file di test presenti nel branch:

```
tests/
```

Per ogni file di test che tocca le funzionalità impattate:

- Elenca i test case pertinenti con il loro nome
- Indica se il test passerebbe INVARIATO con la nuova architettura
- Se non passerebbe, descrivi la modifica minima necessaria al fixture o
  al mock, senza riscrivere il test completo

---

## Fase 5 — Decisione e Output

Dopo aver completato le fasi 1-4, determina:

### CASO A — Design valido, strategia approvata

Condizione: tutte le verifiche in Fase 3 risultano COMPATIBILI e la suite
di test in Fase 4 è recuperabile con modifiche minime.

Se questo è il caso, produci il file:

```
docs/reports/REPORT-Copilot-FullDecoupling-Strategy.md
```

Il report deve contenere:

1. **Esito validazione** — tabella riepilogativa delle 5 aree in §3
   con esito COMPATIBILE e nota sintetica
2. **Piano di implementazione Passo 1** (crea `spark/plugins/`)
   - Lista ordinata dei file da creare con responsabilità di ciascuno
   - Dipendenze da importare in ogni modulo
   - Ordine di creazione (quale file prima, quale dopo)
   - Stima righe di codice (indicativa)
3. **Piano di implementazione Passo 2** (collega tool MCP)
   - Lista esatta delle funzioni da modificare in `tools_packages_install.py`
   - Firma nuova vs firma attuale per ogni tool modificato
   - Gestione dei tool deprecated
4. **Piano di implementazione Passo 3** (rimozione logica ibrida)
   - Lista esatta delle funzioni da rimuovere da `lifecycle.py`
   - Verifica che nessuna dipendenza esterna rimanga sospesa
5. **Test da aggiornare** — lista file + modifica minima necessaria
6. **Domande aperte** — risposte alle 3 decisioni in §9 del design doc
   con la tua raccomandazione tecnica motivata

### CASO B — Design non valido o parzialmente incompatibile

Condizione: una o più verifiche in Fase 3 risultano INCOMPATIBILI o
la suite di test presenta problemi non recuperabili con modifiche minime.

Se questo è il caso, produci il file:

```
docs/reports/REPORT-Copilot-FullDecoupling-Issues.md
```

Il report deve contenere:

1. **Lista dei problemi** — per ogni area INCOMPATIBILE:
   - Descrizione precisa del conflitto (file, riga o funzione coinvolta)
   - Categoria del problema: ARCHITETTURALE / DIPENDENZA / TEST / NAMING
   - Gravità: BLOCCANTE / RILEVANTE / MINORE
2. **Analisi causa radice** — per ogni problema BLOCCANTE:
   - Perché il design doc non ha previsto questo conflitto
   - Cosa avrebbe dovuto rilevare in fase di analisi
3. **Proposta di correzione** — per ogni problema:
   - Modifica minimale al design doc sufficiente a renderlo compatibile
   - Modifica alternativa al codebase se la modifica al design non è
     praticabile senza stravolgere l'architettura
4. **Versione corretta del design** — se i problemi sono tutti di gravità
   RILEVANTE o MINORE, proponi una versione v1.1 del design doc con le
   sole sezioni modificate rispetto a v1.0
5. **Raccomandazione finale** — una delle tre opzioni:
   - PROCEDI CON CORREZIONI: il design è recuperabile, applica le
     modifiche proposte e ripresenta per approvazione
   - REVISIONE PROFONDA: i problemi BLOCCANTI richiedono un nuovo
     ciclo di design prima di qualsiasi implementazione
   - MANTIENI DUAL-MODE: l'approccio attuale del branch è superiore,
     con motivazione tecnica dettagliata

---

## Vincoli Operativi

- Non modificare alcun file di codice sorgente durante questo task.
- Non modificare il design doc `docs/SPARK-DESIGN-FullDecoupling-v1.0.md`.
- Non mergiare nulla su `main`.
- Tutti i file prodotti vanno su `feature/dual-mode-manifest-v3.1`.
- Il canale `stdout` del processo MCP deve rimanere pulito durante
  eventuali operazioni di lettura file: usa solo `stderr` per logging.
- Se un file da analizzare non è accessibile, documenta il problema nel
  report e procedi con le informazioni disponibili.

---

## Criterio di Completezza

Il task è completo quando esiste su `feature/dual-mode-manifest-v3.1`
esattamente uno tra i due file di report indicati nel CASO A o CASO B.
Nessun altro file deve essere creato o modificato.

Nemex81 leggerà il report prima di autorizzare qualsiasi implementazione.
