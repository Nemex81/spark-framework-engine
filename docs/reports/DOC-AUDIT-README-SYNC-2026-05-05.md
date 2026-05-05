# SPARK Framework Engine — Rapporto Audit Documentazione

**Tipo:** Audit di sincronizzazione documentazione/codice
**Versione engine analizzata:** 3.1.0
**Data:** 2026-05-05
**Autore:** Perplexity AI — Coordinatore Consiglio AI
**Destinatario:** GitHub Copilot — Implementatore
**Approvazione richiesta da:** Luca (Nemex81) — Coordinatore generale

---

## 1. Scopo del documento

Questo rapporto è la base di partenza operativa per Copilot.
Descrive lo stato attuale della documentazione pubblica (`README.md`) confrontata con
il codice reale del repository dopo il completamento del ciclo di refactoring
modulare (Fasi 0–5 + Fase 4-BIS, completato 2026-05-02).

Il rapporto è strutturato per permettere a Copilot di elaborare e implementare
una strategia correttiva senza ambiguità: ogni divergenza è classificata per
gravità, contiene il riferimento esatto al file e alla riga da modificare,
e il comportamento corretto atteso.

**Regola operativa per Copilot:** nessuna modifica fuori dallo scope di questo
rapporto. Nessuna correzione logica, nessun refactoring aggiuntivo. Solo
aggiornamento documentale. Se durante l'implementazione emerge qualcosa fuori
scope, annotarlo come task futuro e non implementarlo.

---

## 2. Contesto: stato del refactoring

Il ciclo di refactoring modulare ha trasformato il monolite originale
(`spark-framework-engine.py`, ~361 KB) in un sistema modulare distribuito
nel package `spark/`. Le fasi sono tutte completate e certificate:

- **Fase 0** — Modularizzazione (9 step, 0 failure)
- **Fase 1** — Stabilizzazione (8 step, fix 27 failure pre-esistenti)
- **Fase 2** — Boot deterministico (`validation.py`, `SPARK_STRICT_BOOT`)
- **Fase 3** — Separazione runtime (directory engine-local isolata per workspace)
- **Fase 4** — Gateway e workspace minimale (`WorkspaceWriteGateway`)
- **Fase 5** — Consolidamento finale
- **Fase 4-BIS** — Chiusura INVARIANTE-4 (forward writes tracciati)

**Baseline test post-refactoring:** 0 failed / 296 passed / 8 skipped
(commit `a2a32ac`, 2026-05-01).

Il `todo.md` e `REFACTORING-DESIGN.md` sono sincronizzati con il codice reale.
La documentazione interna di processo è di buona qualità e non richiede intervento.

Il problema è esclusivamente nel **README.md pubblico**, che è rimasto
cristallizzato alla v3.0.0 del 28 aprile 2026 e non riflette nessuna delle
modifiche introdotte nelle Fasi 2–5 e 4-BIS.

---

## 3. Divergenze identificate

### DIV-01 — Versione engine hardcodata nel README (CRITICA)

**File:** `README.md`, riga contenente il badge versione
**Testo attuale:** `> **Versione corrente:** 3.0.0 (28 aprile 2026).`
**Testo corretto:** `> **Versione corrente:** 3.1.0 (05 maggio 2026).`

**Evidenza nel codice:**

- `spark/core/constants.py` → `ENGINE_VERSION = "3.1.0"`
- `engine-manifest.json` → `"version": "3.1.0"`

**Nota per Copilot:** aggiornare anche la data. Il riferimento alla
`docs/MIGRATION-GUIDE-v3.md` nella stessa riga va gestito separatamente
(vedi DIV-07).

---

### DIV-02 — Conteggio tool errato (MEDIO-ALTA)

**File:** `README.md`, sezione "Tools Disponibili (35)"
**Problema:** il README dichiara 35 tool. Il boot log in
`spark/boot/sequence.py` registra `"Tools registered: 44 total"` (fix
applicato in Step 1.5, commit documentato in `todo.md`).

**Azione richiesta a Copilot:**

1. Leggere `spark/boot/engine.py` e contare i tool effettivamente registrati
   con `@mcp.tool` o equivalente per verificare il numero esatto.
2. Aggiornare l'intestazione della sezione da `(35)` al numero reale.
3. Aggiungere alla lista i tool mancanti con la loro firma, rispettando
   il formato già presente nel README (una riga per tool, con firma completa
   inclusi i parametri).

**Tool già documentati nel README (35):** vedere sezione "Tools Disponibili"
del README attuale — questi vanno mantenuti e i 9 mancanti aggiunti.

---

### DIV-03 — Conteggio resources errato (MEDIA)

**File:** `README.md`, sezione "Resources Disponibili (15)"
**Problema:** il numero 15 è statico e risale a una snapshot precedente.
Il sistema di resources è dinamico: le resources engine-proprie sono definite
in `engine-manifest.json` (4 agenti + 3 instruction), il resto dipende dai
pacchetti installati.

**Azione richiesta a Copilot:**

1. Verificare le resources statiche registrate in `spark/boot/engine.py`
   tramite `register_resources()`.
2. Aggiornare il conteggio con il numero di resources engine-side registrate
   staticamente.
3. Aggiungere una nota esplicativa che il numero effettivo a runtime dipende
   dai pacchetti installati nel workspace.

---

### DIV-04 — Path file runtime obsoleto (MEDIA)

**File:** `README.md`, sezione "Gestione Update Workspace"
**Problema:** il README descrive i file runtime sotto `.github/runtime/`:

```
- spark-user-prefs.json per la policy del workspace
- orchestrator-state.json per l'autorizzazione sessione
- backups/<timestamp>/ per i backup automatici
```

La Fase 3 del refactoring ha spostato snapshot, sessioni di merge e backup
in una directory engine-local isolata per workspace. La migrazione avviene
via `_migrate_runtime_to_engine_dir` in `spark/boot/sequence.py` con marker
`.runtime-migrated`. La directory target è calcolata da `resolve_runtime_dir`
in `spark/boot/validation.py` e può essere sovrascritta con la variabile
d'ambiente `SPARK_RUNTIME_DIR` (costante in `spark/core/constants.py`).

**Azione richiesta a Copilot:**

1. Leggere `spark/boot/validation.py` per recuperare la logica esatta di
   `resolve_runtime_dir` e il path default calcolato.
2. Aggiornare la sezione "Gestione Update Workspace" del README con i path
   corretti, distinguendo:
   - File che rimangono in `.github/` (es. `user-prefs.json`)
   - File spostati nella directory engine-local (snapshot, merge-sessions, backups)
3. Aggiungere una riga sulla variabile `SPARK_RUNTIME_DIR` per utenti avanzati.

---

### DIV-05 — Nome file preferenze utente errato (BASSA-MEDIA)

**File:** `README.md`, sezione "Gestione Update Workspace" e FAQ
**Problema:** il README usa il nome `spark-user-prefs.json`.
Il codice usa `user-prefs.json` (costante `_USER_PREFS_FILENAME` in
`spark/core/constants.py`) e il percorso è `.github/user-prefs.json`
(senza il prefisso `runtime/`), come risulta anche dalla logica di
migrazione in `spark/boot/sequence.py`.

**Azione richiesta a Copilot:**

Cercare con grep tutte le occorrenze di `spark-user-prefs.json` nel README
e sostituire con `user-prefs.json`. Cercare tutte le occorrenze del path
`.github/runtime/spark-user-prefs.json` e sostituire con `.github/user-prefs.json`.

---

### DIV-06 — `scf_bootstrap_workspace` — anomalie P4/P5 non documentate (MEDIA)

**File:** `README.md`, sezione documentazione `scf_bootstrap_workspace`
**Problema:** il README descrive il comportamento del tool come uniforme.
Il `todo.md` documenta due anomalie aperte in backlog:

- **P4:** logica di loop bootstrap duplicata nel corpo della funzione
  (eredità del path pre-patch). Impatto: leggibilità e manutenibilità, non funzionale.
- **P5:** payload di ritorno non uniforme tra i rami (rami vivi vs rami
  policy/authorization). I campi del dizionario di ritorno variano tra i
  percorsi di esecuzione.

**Azione richiesta a Copilot:**

Aggiungere una nota nella documentazione del tool `scf_bootstrap_workspace`
nel README che avverta che il payload di ritorno può variare tra i rami di
esecuzione (autorizzazione richiesta vs esecuzione diretta), specificando
quali campi sono garantiti in tutti i rami e quali sono presenti solo in
alcuni. Questa nota va basata sull'analisi del codice reale in
`spark/boot/engine.py`.

---

### DIV-07 — Link rotto a `docs/MIGRATION-GUIDE-v3.md` (BASSA)

**File:** `README.md`, prima sezione dopo il titolo
**Testo attuale:**
`> Per la migrazione da 2.x consultare [`docs/MIGRATION-GUIDE-v3.md`](docs/MIGRATION-GUIDE-v3.md).`

**Problema:** il file `docs/MIGRATION-GUIDE-v3.md` non esiste nel repository.
La struttura reale di `docs/` contiene: `REFACTORING-DESIGN.md`, `todo.md`,
`archivio/`, `coding plans/`, `reports/`, `todolist/`.

**Azione richiesta a Copilot — due opzioni (scegliere la più appropriata):**

**Opzione A (preferita se il contenuto di migrazione non esiste altrove):**
Rimuovere il riferimento e sostituire con: `Per le note di migrazione
consultare il `CHANGELOG.md`.`

**Opzione B:**
Se esiste contenuto di migrazione da v2.x a v3.x nel `CHANGELOG.md` o in
`docs/archivio/`, aggiornare il link per puntare al file corretto.

---

## 4. File da NON modificare

- `spark/core/constants.py` — solo lettura per questo task
- `spark/boot/sequence.py` — solo lettura per questo task
- `spark/boot/engine.py` — solo lettura per questo task (usare solo per ricavare
  il conteggio tool e il comportamento di bootstrap)
- `engine-manifest.json` — solo lettura
- `docs/todo.md` — solo lettura
- `docs/REFACTORING-DESIGN.md` — solo lettura
- Qualsiasi file sotto `spark/` — nessuna modifica al codice

---

## 5. File da modificare

- `README.md` — target principale, tutte le 7 divergenze lo riguardano

---

## 6. Ordine di implementazione consigliato

Implementare le correzioni nel seguente ordine per ridurre il rischio di
regressioni documentali:

1. **DIV-07** — rimozione link rotto (atomica, zero rischio)
2. **DIV-01** — aggiornamento versione (atomica, zero rischio)
3. **DIV-05** — sostituzione nome file prefs (grep + replace, basso rischio)
4. **DIV-04** — aggiornamento sezione path runtime (richiede lettura codice)
5. **DIV-06** — nota payload bootstrap (richiede lettura codice)
6. **DIV-03** — aggiornamento conteggio resources (richiede lettura codice)
7. **DIV-02** — aggiornamento tool list completa (richiede lettura codice,
   il più laborioso)

---

## 7. Criterio di completamento

Il task è completato quando:

- `README.md` dichiara la versione `3.1.0`
- Il conteggio tool corrisponde al numero reale registrato in `engine.py`
- Il conteggio resources riflette le resources engine-side statiche con nota
  sul runtime dinamico
- I path runtime documentati sono coerenti con `spark/boot/validation.py`
  e `spark/core/constants.py`
- Il nome del file prefs è `user-prefs.json` ovunque nel README
- La nota sul payload di `scf_bootstrap_workspace` è presente
- Il link a `MIGRATION-GUIDE-v3.md` è rimosso o corretto
- La suite test non viene toccata (nessun file `.py` modificato)

---

## 8. Anomalie fuori scope (non implementare, solo registrare)

Le seguenti anomalie sono documentate nel `todo.md` come backlog e **non
rientrano nello scope di questo task correttivo**:

- **P4:** refactor logica loop duplicata in `scf_bootstrap_workspace`
- **P5:** normalizzazione payload di ritorno `scf_bootstrap_workspace`

Entrambe richiedono modifiche al codice Python e devono essere trattate
in un task dedicato con piano tecnico approvato da Luca.

---

## 9. Fonte dei dati di questo rapporto

Tutte le affermazioni di questo rapporto sono basate sull'analisi diretta
dei file del repository al commit `e8adf8be780b35ee47bbfff24f0dccde8180b855`:

- `README.md` (SHA: `5b70a612fa06370ff751155519d4f8e1ef42893e`)
- `spark/core/constants.py` (SHA: `055859cc238f0f2e99193db207062e167ba9dc73`)
- `engine-manifest.json` (SHA: `1e92dac38b2fcfbe1e36ad8dd3f5a0e963ac28b1`)
- `spark/boot/sequence.py` (SHA: `696217c63eb08b6ee5da95942a836b58c37ef591`)
- `spark/boot/engine.py` (SHA: `230bfe654a9b89fb7b7ab7f7a7ffc2bc0e7b6a80`)
- `docs/todo.md` (SHA: `7dbcab72e57b0ff7e3d9b555cf6a620f76fbfc1c`)
- `docs/REFACTORING-DESIGN.md` (SHA: `0963c6ebd9ae1339eb54463432e505413e40b6d2`)
