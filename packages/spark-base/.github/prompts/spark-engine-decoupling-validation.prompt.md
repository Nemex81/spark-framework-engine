---
name: spark-engine-decoupling-validation-v1.0
description: >
  Analisi, validazione iterativa e pianificazione tecnica completa
  per il disaccoppiamento dei componenti non operativi di spark-base
  verso il nuovo pacchetto spark-engine. Copilot deve prima leggere,
  analizzare e convalidare la strategia proposta; se la convalida
  fallisce, deve analizzare ulteriormente il sistema, proporre una
  strategia alternativa e ripetere il ciclo finché non ottiene PASS.
  Solo dopo la convalida finale deve produrre un piano correttivo
  implementativo completo, diviso in fasi, da salvare in docs.
mode: agent
execute_mode: autonomus
tools:
  - read_file
  - write_file
  - insert_edit_into_file
  - create_file
  - semantic_search
  - grep_search
  - file_search
  - run_terminal_command
spark: true
scf_owner: spark-framework-engine
scf_file_role: prompt
scf_merge_strategy: replace
scf_merge_priority: 10
scf_protected: false
version: 1.0.0
---

# SPARK — Validazione Strategia di Disaccoppiamento verso spark-engine
## Branch: `feature/dual-mode-manifest-v3.1`
## Emesso da: Perplexity AI (Coordinatore). Approvato da: Nemex81.
## Prompt version: 1.0.0 — 2026-05-09

---

## OBIETTIVO

Valutare la proposta di disaccoppiare ulteriormente il sistema SPARK
spostando in `spark-engine` (nuovo package in `packages/`) i componenti
di `spark-base` che non sono strettamente connessi alle attività operative
dell'utente.

L'idea di base è questa:

- `spark-base` deve restare leggero e orientato all'interazione utente
- `spark-engine` deve diventare il pacchetto di basso livello che
  governa funzionamento interno del sistema e del progetto
- le skills informative comuni non devono essere duplicate: vanno
  aggiornate una volta sola nel livello corretto
- `spark-welcome` può diventare un dispatcher/orchestratore se e solo
  se la verifica del sistema conferma che la responsabilità è stabile
  e non introduce ambiguità

Il tuo compito non è approvare a priori questa idea. Il tuo compito è
analizzarla contro il codice reale, verificarne la fattibilità, la
coerenza e l'impatto, e poi convalidarla o bocciarla con evidenza.

---

## REGOLA D'ORO

Prima leggi. Poi analizzi. Poi validi.
Nessuna modifica, nessuna proposta operativa, nessun piano tecnico
prima della convalida. Se la strategia proposta non passa, non forzarla:
devi analizzare ulteriormente il sistema, formulare una strategia
migliore, e ripetere il ciclo fino a quando ottieni una convalida
solida oppure individui un blocco architetturale reale.

---

## FASE 1 — LETTURA OBBLIGATORIA

Leggi nell'ordine esatto. Non modificare nulla.

### 1.1 — Mappa del perimetro attuale

1. `README.md` root — come viene presentato il sistema oggi
2. `docs/architecture.md`
3. `docs/api.md`
4. `docs/reports/SPARK-REPORT-DualUniverse-Consolidation-v1.0.md`
5. `docs/reports/SPARK-REPORT-LegacyInitAudit-v1.0.md`
6. `CHANGELOG.md`
7. `docs/SPARK-DESIGN-FullDecoupling-v2.0.md`

### 1.2 — Pacchetti e manifest

8. `packages/spark-base/package-manifest.json`
9. `packages/spark-base/.github/agents/spark-assistant.agent.md`
10. `packages/spark-base/.github/agents/spark-guide.agent.md`
11. `packages/spark-base/.github/agents/Agent-Welcome.md`
12. `packages/spark-base/.github/prompts/` (lista file)
13. `packages/spark-base/.github/skills/` (lista file)
14. Ogni file `package-manifest.json` presente sotto `packages/`

### 1.3 — Core engine

15. `spark-framework-engine.py` (intestazione e registrazione tool)
16. `spark/boot/engine.py`
17. `spark/boot/onboarding.py`
18. `spark/boot/tools_bootstrap.py`
19. `spark/core/constants.py`
20. `spark/plugins/` (se presente)
21. `spark/registry/` (se presente)

### 1.4 — Ricerca mirata

Esegui questi search sul codebase:
- `spark-welcome`
- `spark-assistant`
- `spark-guide`
- `framework-ops`
- `mcp.tool`
- `bootstrap`
- `onboarding`
- `dispatcher`
- `Agent-Orchestrator`
- `Agent-FrameworkDocs`
- `Agent-Release`

Per ogni risultato rilevante, apri il file completo o la funzione
completa se il risultato è parziale.

Al termine della Fase 1, compila internamente questa mappa:

```text
MAPPA DI STATO — FASE 1
Componenti in spark-base:
Componenti già tecnici:
Componenti già user-facing:
Componenti duplicati o sovrapposti:
Dipendenze attuali verso spark-engine:
Punti di possibile migrazione:
Punti che non devono muoversi:
```

---

## FASE 2 — ANALISI DELLA STRATEGIA PROPOSTA

La strategia da verificare è questa:

- spostare in `spark-engine` i componenti di `spark-base`
  non strettamente operativi per l'utente
- centralizzare le skills informative comuni
- lasciare a `spark-base` il ruolo di contatto leggero e user-facing
- eventualmente introdurre o specializzare `spark-welcome` come dispatcher

Analizza ogni punto con evidenza dal codice.

### 2.1 — Classificazione dei componenti

Per ogni componente trovato in `spark-base`, classificalo in una sola categoria:

- USER-FACING
- SYSTEM-FACING
- RUNTIME/BOOTSTRAP
- DOCUMENTATION
- ROUTING/DISPATCH
- DUPLICATO/DERIVATO
- NON MIGRABILE
- MIGRABILE

Per ogni file o cartella rilevante indica:

- file sorgente
- responsabilità attuale
- dipendenze dirette
- impatto se migrato
- rischio di disallineamento

### 2.2 — Verifica dell'idea di `spark-welcome`

Valuta se `spark-welcome` può davvero essere un dispatcher
senza diventare un agente ambiguo.

Verifica:

- sa solo orientare l'utente o contiene già logica di routing?
- deve vivere in `spark-base` o in `spark-engine`?
- duplicherà contenuti già presenti in `spark-assistant` o `spark-guide`?
- introduce dipendenze cognitive che richiedono aggiornamenti multipli?
- il suo perimetro può essere definito in modo stabile e corto?

Se il ruolo di `spark-welcome` non è netto, segnala il problema.
Non forzare l'idea solo perché sembra elegante.

### 2.3 — Verifica delle skills informative

Analizza le skills informative attuali e quelle potenziali.

Domande da risolvere:

- quali skills sono realmente comuni e condivisibili?
- quali invece sono specifiche del workspace utente?
- le skills informative possono essere centralizzate in `spark-engine`
  senza rompere il flusso user-facing?
- se una skill viene spostata, cambia il suo owner concettuale
  o solo il file di origine?
- attenzione: una skill usata da un agente che RESTA in spark-base
  NON può migrare senza creare dipendenza inversa

### 2.4 — Verifica impatti

Analizza l'impatto della migrazione su:

- onboarding nuovo utente
- bootstrap workspace vergine
- aggiornamento file preesistenti
- suite di test
- compatibilità con scf-master-codecrafter e scf-pycode-crafter
- naming conflict con spark-framework-engine

---

## FASE 3 — CONVALIDA DELLA STRATEGIA

Per ogni ipotesi di migrazione, compila questa scheda:

```text
CONVALIDA STRATEGIA — COMPONENTE X

Responsabilità attuale:
Categoria:
Migrazione proposta:
Impatto su spark-base:
Impatto su spark-engine:
Dipendenze nuove:
Dipendenze rimosse:
Rischio di duplicazione:
Rischio di disallineamento:
Impatto su onboarding:
Impatto su test:
Esito: PASS / FAIL / BLOCCO-ARCHITETTURALE
Motivo:
```

### Regole di convalida

- PASS: la migrazione è sensata, stabile, e non rompe i flussi
- FAIL: la migrazione è concettualmente debole o incompleta
- BLOCCO-ARCHITETTURALE: serve una decisione umana o una ridefinizione
  del perimetro prima di procedere

### Attenzione ai blocchi strutturali

Il principale blocco da verificare è questo:
Tutte le risorse MCP (agents, skills, instructions, prompts) di spark-base
e di un eventuale spark-engine sono servite dallo STESSO server MCP.
Dividere il catalogo tra due pacchetti non introduce separazione tecnica
reale, ma solo organizzativa. L'overhead di gestione (dipendenze, versioni,
test) deve essere giustificato dal beneficio concreto.

Secondo blocco: il nome "spark-engine" crea ambiguità con
"spark-framework-engine" (il server Python MCP). Verifica se è
necessario rinominare il pacchetto proposto (es. "spark-ops").

### Ciclo iterativo obbligatorio

Se anche un solo componente critico non passa la convalida:

1. ferma la validazione corrente
2. analizza ulteriormente il sistema
3. riformula la strategia
4. ripeti FASE 2 e FASE 3
5. continua finché la strategia non passa oppure emerge un blocco
   architetturale reale

Non chiedere conferme intermedie. Non andare avanti con una strategia
che non hai convalidato.

---

## FASE 4 — PIANO CORRETTIVO TECNICO

Solo dopo una convalida PASS complessiva,
produci un piano correttivo tecnico completo.

Il piano deve essere diviso in fasi, con ordine sicuro di esecuzione.

### Struttura obbligatoria del piano

```markdown
# Piano Tecnico — Disaccoppiamento spark-base -> spark-engine

## 1. Obiettivo
[descrizione sintetica]

## 2. Verdetto sulla strategia originale
[PASS / FAIL / BLOCCO + motivazione]

## 3. Strategia adottata
[originale o alternativa, con motivazione]

## 4. Componenti da migrare
[lista con motivazione per ciascuno]

## 5. Componenti da lasciare in spark-base
[lista con motivazione]

## 6. Nuovo pacchetto: perimetro e responsabilità
[nome, path, responsabilità, dipendenze]

## 7. Impatti previsti
[onboarding, bootstrap, documentazione, test, skills]

## 8. Fasi operative
### Fase 1 — Analisi e preparazione
### Fase 2 — Creazione package-manifest nuovo pacchetto
### Fase 3 — Spostamento componenti selezionati
### Fase 4 — Aggiornamento dipendenze pacchetti esistenti
### Fase 5 — Allineamento documentazione
### Fase 6 — Verifica test e regressioni
### Fase 7 — Validazione finale

## 9. Rischi e mitigazioni
[per ogni fase]

## 10. Dipendenze e prerequisiti
[lista]

## 11. Decisioni aperte
[solo se residue]

## 12. Conclusione tecnica
[verdetto finale]
```

Il piano deve essere realistico, sequenziale e implementabile.
Non deve contenere codice, solo strategia tecnica.

---

## FASE 5 — SALVATAGGIO DEL PIANO IN DOCS

Salva il piano nella cartella dedicata ai piani tecnici in `docs`.

Il file deve chiamarsi:

`docs/technical-plans/SPARK-PLAN-Engine-Decoupling-v1.0.md`

Se la cartella `docs/technical-plans/` non esiste, creala.
Se la cartella già esiste con un altro naming standard,
usa quello standard invece di inventarne uno nuovo.

---

## VINCOLI NON NEGOZIABILI

- Non modificare file senza aver prima completato la convalida
- Nessuna modifica a firme MCP esistenti
- Nessuna modifica ai file `.github/` protetti (framework_edit_mode: false)
- Nessuna dipendenza nuova senza motivazione esplicita
- Non introdurre duplicazioni di skills informative
- Non spostare nel core contenuti che devono restare user-facing
- Se il ruolo di un componente non è chiaro, segnalarlo
  come decisione aperta
- Se una migrazione indebolisce onboarding o bootstrap,
  fermati e rivaluta
- Se il blocco architetturale è reale, documentalo e non forzare

---

## OUTPUT ATTESO

Alla fine della sessione devi produrre:

1. un verdetto sulla strategia proposta
2. eventuale strategia alternativa se la prima non passa
3. il piano tecnico completo diviso in fasi
4. il file salvato in `docs/technical-plans/`
5. un report finale sintetico con:
   - cosa è stato validato
   - cosa resta aperto
   - perché la strategia è o non è raccomandata

---

## REGOLA FINALE

Se la strategia proposta non è abbastanza solida,
non cercare di farla passare.
Analizza meglio il sistema, correggi la strategia,
e ripeti il ciclo fino a ottenere una validazione vera.
Solo allora scrivi il piano tecnico.
