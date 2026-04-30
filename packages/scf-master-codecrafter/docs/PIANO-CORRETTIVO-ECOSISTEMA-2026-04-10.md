# Piano Correttivo Ecosistema SCF - 2026-04-10

## Stato

- Ambito: remediation tecnica post-audit dell'ecosistema SCF
- Modalita: esecuzione autonoma, cross-repo, con validazione per fase
- Repo in scope: `spark-framework-engine`, `scf-master-codecrafter`, `scf-pycode-crafter`, `scf-registry`
- Repo fuori scope: codice applicativo utente, `tabboz-simulator-202`

---

## Obiettivo

Rendere l'ecosistema SCF coerente, aggiornabile e manutenibile senza dipendenze implicite tra documentazione, registry, workflow e motore MCP.

Il piano corregge quattro classi di problemi emerse dall'audit:

1. incoerenza tra contratti del registry e workflow di sync;
2. drift tra documentazione pubblica e comportamento reale del motore e dei package;
3. update package non dependency-aware dopo l'introduzione del layer master;
4. assenza di un ciclo di validazione unificato per release coerenti cross-repo.

---

## Principi di esecuzione

1. Il manifest e il codice runtime restano la source of truth; la documentazione deve allinearsi a loro, non il contrario.
2. Ogni modifica cross-repo deve avere criterio di uscita verificabile prima della fase successiva.
3. Le correzioni di contratto pubblico hanno priorita piu alta delle ottimizzazioni interne.
4. Nessuna fase deve introdurre regressioni nel package system esistente.
5. Le modifiche devono essere complementari: workflow, docs, test e tool MCP devono convergere sullo stesso modello operativo.

---

## Diagnosi sintetica

### D1. Contratto registry non allineato

- `scf-registry/registry.json` usa `status: stable` per `scf-master-codecrafter`.
- `spark-framework-engine/.github/workflows/registry-sync-gateway.yml` accetta solo `active` e `deprecated`.
- `scf-registry/README.md` documenta ancora il contratto vecchio.

Impatto operativo:
- un prossimo sync automatico puo fallire anche con payload corretto;
- il registry pubblica un modello che il gateway non accetta.

### D2. Documentazione pubblica stale

- `spark-framework-engine/README.md` non riflette correttamente il numero resource.
- `scf-pycode-crafter/README.md` descrive ancora il package pre-split.
- `scf-registry/README.md` espone versioni e semantica obsolete.

Impatto operativo:
- gli utenti ricevono istruzioni errate su installazione, compatibilita e contenuto dei package;
- Copilot e i maintainer hanno materiale pubblico incoerente rispetto allo stato reale.

### D3. Update package non dependency-aware

- `scf_apply_updates()` applica update disponibili senza ordinamento topologico esplicito.
- Il plugin Python ora dipende da `scf-master-codecrafter`.

Impatto operativo:
- futuri update multi-package possono applicarsi in ordine non robusto;
- manca una preview affidabile del piano di aggiornamento.

### D4. Validazione ecosistema incompleta

- La suite del motore copre bene safety e atomicita, ma non il nuovo modello multi-package master+plugin nel percorso di update.
- Manca una checklist di release coerente tra engine, registry e package docs.

Impatto operativo:
- il sistema e tecnicamente forte ma puo divergere nel tempo su contratti e flussi utente.

---

## Strategia correttiva

La remediation viene eseguita in sei fasi ordinate. Ogni fase produce un delta autonomo, coerente e complementare alle altre.

### Fase R0 - Baseline e freeze del contratto

Scopo:
- consolidare il modello pubblico dei package prima di cambiare logica o documentazione.

Azioni:
- definire il set valido degli `status` supportati dal registry;
- scegliere se `stable` diventa status ufficiale o viene ricondotto a `active`;
- allineare la semantica tra `registry.json`, workflow gateway e README del registry;
- esplicitare il contratto in un solo punto documentale canonico.

Criterio di uscita:
- stesso vocabolario `status` in dati, workflow e documentazione.

Validazione:
- controllo statico dei valori ammessi;
- validazione del workflow con payload compatibili ai package presenti.

### Fase R1 - Riallineamento documentazione pubblica

Scopo:
- eliminare il drift tra comportamento reale e README dei repo coinvolti.

Azioni:
- aggiornare `spark-framework-engine/README.md` su resource, runtime state e tool count;
- aggiornare `scf-pycode-crafter/README.md` al modello plugin-only con dipendenza dal master;
- aggiornare `scf-registry/README.md` a catalogo e schema reali;
- verificare che changelog e README non si contraddicano su versioni minime e contenuti.

Criterio di uscita:
- ogni README descrive solo funzionalita e versioni effettivamente presenti nel repo.

Validazione:
- review incrociata README vs manifest vs codice;
- grep mirato su versioni, status e nomi tool/resource pubblici.

### Fase R2 - Hardening del flusso update package

Scopo:
- rendere l'aggiornamento multi-package deterministicamente corretto.

Azioni:
- introdurre nel motore una risoluzione dell'ordine di update basata sulle dipendenze dichiarate;
- separare la fase di detection dalla fase di execution con un update plan esplicito;
- far emergere all'utente le dipendenze richieste e l'ordine di applicazione;
- mantenere l'attuale semantica safe: fetch-before-cleanup, ownership policy, preservation dei file utente modificati.

Trade-off principale:
- maggiore complessita interna nel motore in cambio di update cross-package robusti e spiegabili.

Criterio di uscita:
- update master+plugin applicabili nello stesso run in ordine stabile e verificabile.

Validazione:
- test unitari su ordinamento dipendenze;
- test su caso `scf-master-codecrafter` -> `scf-pycode-crafter`;
- verifica che l'assenza di dipendenze mantenga il comportamento corrente.

### Fase R3 - Copertura test e quality gates ecosistema

Scopo:
- trasformare i finding sistemici in guardrail permanenti.

Azioni:
- aggiungere test sul contratto `status` del registry;
- aggiungere test sul piano di update dependency-aware;
- aggiungere controlli di coerenza tra contatori documentati e contatori runtime pubblici, dove sostenibile;
- valutare un test o script di coerenza docs-manifest-registry per le versioni minime dei package ufficiali.

Criterio di uscita:
- le regressioni sui contratti pubblici principali vengono intercettate localmente.

Validazione:
- suite completa `pytest` del motore verde;
- validazione JSON del registry;
- verifiche mirate dei manifest package.

### Fase R4 - Prompt e UX MCP per update guidati

Scopo:
- rendere il percorso utente e Copilot piu preciso, spiegabile e sicuro.

Azioni:
- rivedere i prompt SCF legati a installazione e update per riflettere il nuovo update plan;
- mostrare nei prompt dipendenze, precondizioni e impatto prima della conferma utente;
- distinguere chiaramente `check updates`, `preview plan`, `apply updates`.

Criterio di uscita:
- l'utente capisce prima della conferma cosa verra aggiornato, in quale ordine e perche.

Validazione:
- review dei prompt contro i tool MCP disponibili;
- verifica che nessun prompt richiami comportamenti non implementati.

### Fase R5 - Release readiness cross-repo

Scopo:
- chiudere il ciclo con una procedura di rilascio coerente.

Azioni:
- definire ordine di pubblicazione consigliato: engine, master, plugin, registry;
- riallineare changelog e note operative dove necessario;
- verificare worktree pulito o file intenzionalmente pendenti prima di PR/release;
- produrre checklist finale unica per manutenzione futura.

Criterio di uscita:
- esiste un percorso ripetibile per rilasci coerenti dell'ecosistema.

Validazione:
- check finale cross-repo;
- review di coerenza versioni minime, dipendenze e documentazione pubblica.

---

## Sequenza tecnica consigliata

1. Eseguire R0 prima di qualunque altra modifica.
2. Eseguire R1 subito dopo R0, per riallineare il contratto pubblico.
3. Eseguire R2 e R3 nello stesso ciclo di sviluppo del motore.
4. Eseguire R4 solo dopo che la logica di update e testata.
5. Chiudere con R5 come gate di rilascio.

Motivazione:
- prima si stabilizza il contratto, poi si riallinea la comunicazione, poi si rafforza il runtime, infine si rifinisce la UX e si prepara la release.

---

## File target previsti per la remediation

### Repo `spark-framework-engine`

- `spark-framework-engine.py`
- `README.md`
- `.github/workflows/registry-sync-gateway.yml`
- `tests/test_framework_versions.py`
- `tests/test_package_installation_policies.py`
- `tests/test_update_diff.py`
- eventuali nuovi test dedicati all'update planner
- prompt SCF sotto `.github/prompts/` se impattati dalla nuova UX

### Repo `scf-registry`

- `registry.json`
- `README.md`

### Repo `scf-pycode-crafter`

- `README.md`
- eventuale allineamento documentale secondario se emergono mismatch ulteriori

### Repo `scf-master-codecrafter`

- `docs/TODO.md`
- questo piano correttivo
- eventuale documentazione di coordinamento finale

---

## Rischi e mitigazioni

### Rischio 1

Rischio:
- introdurre una tassonomia `status` non retrocompatibile.

Mitigazione:
- mantenere mapping esplicito o accettazione backward-compatible nel gateway finche tutti i package ufficiali non sono riallineati.

### Rischio 2

Rischio:
- aumentare troppo la complessita di `scf_apply_updates()`.

Mitigazione:
- introdurre una funzione separata di planning e lasciare l'applicazione come fase distinta.

### Rischio 3

Rischio:
- documentazione aggiornata ma non protetta da test.

Mitigazione:
- aggiungere almeno i controlli minimi sui contratti pubblici stabili.

### Rischio 4

Rischio:
- rilascio di package con worktree sporco o file non tracciati.

Mitigazione:
- check release finale dedicato prima di PR o tag.

---

## Deliverable attesi

1. Contratto registry coerente tra dati, workflow e docs.
2. README pubblici allineati al comportamento reale del sistema.
3. Update package dependency-aware con preview del piano.
4. Test aggiuntivi sui nuovi invarianti ecosistema.
5. Checklist finale di release cross-repo.

---

## Definizione di completamento

Il piano si considera completato quando:

- i package ufficiali possono essere descritti, installati e aggiornati senza incoerenze tra codice, registry, workflow e documentazione;
- il motore MCP espone una UX di update chiara per Copilot e per l'utente;
- i principali contratti pubblici dell'ecosistema sono coperti da test o da validazioni automatiche locali.