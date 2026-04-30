---
task: razionalizzazione-agenti-comuni
agent: Agent-Orchestrator
status: DRAFT
date: 2026-04-23
repositories:
  - spark-base
  - scf-master-codecrafter
---

# Piano Tecnico — Razionalizzazione Agenti Comuni 2026-04-23

## Executive Summary

La richiesta originale non e validabile in esecuzione diretta.
L'audit read-only mostra che gli 11 agenti dichiarati come "comuni"
non sono identici tra `spark-base` e `scf-master-codecrafter`: tutti i file
risultano divergenti per contenuto, struttura o entrambi.

Questo rende non sicura la sequenza "allinea se serve e poi elimina subito"
senza una fase intermedia di riconciliazione semantica file-per-file.

## Esito convalida del piano originale

### Esito

FAIL

### Motivi bloccanti

1. Tutti gli 11 agenti comuni risultano divergenti, non identici.
2. `Agent-Orchestrator.md` e `Agent-Research.md` hanno la stessa lunghezza tra i due package ma hash diversi, quindi non sono alias sicuri.
3. `Agent-Git.md` e `Agent-Welcome.md` nel master sono molto piu compatti rispetto a `spark-base`, quindi una rimozione immediata cambierebbe il contratto documentale senza prima scegliere un canone unico.
4. Le modifiche richieste ricadono sotto `.github/**` in entrambi i repository e sono attualmente protette da `framework_edit_mode: false`.

## Audit sintetico confermato

### Agenti comuni confrontati

- `Agent-Analyze.md` — divergente
- `Agent-Docs.md` — divergente
- `Agent-FrameworkDocs.md` — divergente
- `Agent-Git.md` — divergente
- `Agent-Helper.md` — divergente
- `Agent-Orchestrator.md` — divergente
- `Agent-Plan.md` — divergente
- `Agent-Release.md` — divergente
- `Agent-Research.md` — divergente
- `Agent-Validate.md` — divergente
- `Agent-Welcome.md` — divergente

### Agenti esclusivi master da preservare e poi rinominare

- `code-Agent-Code.md`
- `code-Agent-CodeRouter.md`
- `code-Agent-CodeUI.md`
- `code-Agent-Design.md`

### File master da aggiornare se la migrazione prosegue

- `.github/AGENTS.md`
- `.github/AGENTS-master.md`
- `.github/copilot-instructions.md`
- `.github/prompts/**` con riferimenti agli agenti comuni o agli agenti esclusivi da rinominare

## Strategia correttiva validabile

### Fase A — Matrice di riconciliazione semantica

Per ciascuno degli 11 agenti comuni:

1. confrontare sezioni, trigger, output e regole operative tra `spark-base` e `scf-master-codecrafter`;
2. stabilire il canone finale in `spark-base`;
3. migrare in `spark-base` solo le parti del master che aggiungono comportamento reale e non duplicano contenuto gia presente.

Gate di uscita:

- tutti gli 11 agenti comuni in `spark-base` hanno contenuto finale approvato;
- per ciascun file esiste una decisione esplicita: `keep-base`, `merge-master-into-base` oppure `escalate`.

### Fase B — Rimozione duplicati solo dopo parita documentale

Solo dopo la Fase A:

1. rimuovere dal master gli 11 agenti comuni diventati davvero duplicati;
2. aggiornare `AGENTS.md`, `AGENTS-master.md`, `copilot-instructions.md` e i prompt che li referenziano;
3. verificare che non restino riferimenti al path rimosso.

Gate di uscita:

- nessun riferimento residuo agli agenti comuni rimossi;
- nessuna perdita di contenuto operativo rispetto alla baseline combinata.

### Fase C — Rinomina agenti esclusivi del master

Solo dopo la Fase B:

1. rinominare i quattro agenti esclusivi con prefisso `code-`;
2. riallineare tutti i riferimenti testuali nei file `.github/**` del master;
3. verificare che non esistano riferimenti rotti ai vecchi nomi.

Gate di uscita:

- nessun riferimento ai vecchi nomi file in `.md` del repository;
- naming coerente tra file, indice agenti e prompt.

### Fase D — Changelog e chiusura

1. aggiornare il changelog del master con le operazioni effettivamente completate;
2. eseguire validazione finale sui file modificati;
3. delegare eventuali commit ad Agent-Git;
4. non eseguire push senza conferma esplicita `PUSH`.

## Prerequisiti obbligatori

Prima della prima scrittura su `.github/**`:

1. aprire una finestra `#framework-unlock` per `spark-base`;
2. aprire una finestra `#framework-unlock` per `scf-master-codecrafter`;
3. limitare il batch ai file realmente toccati dal delta approvato.

## Convalida della strategia correttiva

### Esito finale

PASS, con prerequisiti.

### Condizioni di esecuzione

- la strategia e sicura se eseguita in due step distinti: riconciliazione contenuti, poi rimozione/rinomina;
- l'implementazione resta bloccata finche `framework_edit_mode` rimane `false` nei due repository;
- commit locali ammessi solo via Agent-Git; push esclusi fino a conferma esplicita.

## Output atteso alla ripresa operativa

Alla ripresa con unlock attivo, il task dovra produrre:

- allineamento contenutistico dei common agent in `spark-base`;
- rimozione dei duplicati reali dal master;
- rinomina `code-*` degli agenti esclusivi;
- aggiornamento di indici, prompt e changelog;
- validazione finale senza riferimenti rotti.
