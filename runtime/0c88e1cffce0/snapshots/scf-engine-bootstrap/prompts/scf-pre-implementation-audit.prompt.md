---
description: Analisi pre-implementazione del piano. SOLO LETTURA. Nessuna scrittura su disco o su repository.
tools: ["github", "file_search", "semantic_search"]
scf_protected: false
scf_file_role: "prompt"
name: scf-pre-implementation-audit
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
mode: agent
type: prompt
spark: true
scf_owner: "spark-base"
---

# SPARK Pre-Implementation Audit

## REGOLA ASSOLUTA — READ-ONLY

**Sei in modalità ANALISI PURA. Questo prompt non ti autorizza a scrivere, modificare,
creare o cancellare nulla. Nessun file. Nessun commit. Nessuna PR. Nessun commento
su issue. Se hai il dubbio di stare per scrivere qualcosa, NON farlo.**

L'unico output ammesso è il **rapporto di analisi** in risposta a questo prompt.

---

## Obiettivo

Verificare che il piano di hardening descritto in SPARK-ECOSYSTEM-AUDIT-2026-04-13.md
sia corretto, compatibile e sicuro **prima** di qualsiasi implementazione.

Il rapporto finale deve rispondere a una domanda sola:
> "Il piano è sicuro da implementare così com'è, oppure ci sono incoerenze,
> rischi di regressione o incompatibilità che devono essere corretti prima?"

Se la risposta è negativa, elabora una strategia correttiva per il piano per garantire coerenza, compatibilità e completezza.

---

## Fase 1 — Lettura e mappatura del motore

Leggi `spark-framework-engine.py` per intero. Mappa i seguenti punti:

### 1.1 Firma e comportamento di `is_user_modified`

Trova il metodo `is_user_modified` nella classe `ManifestManager`.
Riporta:
- La firma esatta (parametri e tipo di ritorno)
- I tre possibili valori di ritorno con le condizioni che li producono
- Tutte le chiamate a questo metodo nel file (riga e contesto)

### 1.2 Loop principale di `scf_install_package`

Trova il blocco `for file_path in files:` dentro `scf_install_package`.
Riporta:
- Il numero di riga in cui inizia il loop
- La condizione attuale su `is_user_modified` (riga esatta)
- Cosa succede attualmente quando `is_user_modified` restituisce `None`
  e il file esiste già su disco: il file viene sovrascritto? saltato? errore?

### 1.3 Struttura del payload di ritorno

Elenca tutti i campi presenti nei payload `return {...}` di `scf_install_package`,
inclusi quelli nei rami di errore. Verifica che `removed_obsolete_files` e
`preserved_obsolete_files` siano presenti in **tutti** i rami (inclusi gli early return).
Riporta ogni campo mancante.

### 1.4 Dipendenze da non rompere

Elenca tutti i metodi pubblici di `ManifestManager` che vengono chiamati
da tool MCP diversi da `scf_install_package`. Per ognuno, riporta:
- Nome del metodo
- Tool che lo chiama
- Se la modifica proposta dal piano lo impatta

---

## Fase 2 — Verifica della struttura del manifest

Trova il file `.scf-manifest.json` nel workspace corrente (cerca in `.github/`).
Se esiste, riporta:
- La chiave top-level dell'array di entries (è `entries` o `installed_packages`?)
- Un esempio di entry con tutti i campi presenti
- Se la struttura corrisponde a quella documentata nel piano

Se il file non esiste, riporta "manifest non trovato" e continua.

---

## Fase 3 — Analisi documentale `scf-registry`

Cerca nel repo `scf-registry` il file `README.md`.
Riporta:
- Tutte le occorrenze del termine `installed_packages` (con il numero di riga
  o il contesto testuale circostante)
- Se il termine è usato come chiave JSON, come termine descrittivo generico,
  o entrambi
- Se esiste già una sezione che documenta la struttura del manifest

---

## Fase 4 — Verifica del documento di audit

Cerca in `scf-master-codecrafter` il file `docs/SPARK-ECOSYSTEM-AUDIT-2026-04-13.md`.
Riporta:
- Se il file esiste
- Se esiste già una sezione numerata "10)" o "Revision Notes"
- I finding contrassegnati con avviso e il loro stato attuale (risolto / pending)
- Se il file non esiste, riporta solo questo fatto

---

## Fase 5 — Valutazione del rischio di regressione

Per ciascuno dei 3 task del piano, esprimi un giudizio su:

### Task 1 — Preflight classification in `scf_install_package`
- Il parametro `conflict_mode: str = "abort"` è compatibile con la firma FastMCP?
  (FastMCP supporta parametri opzionali con default nei tool async?)
- L'aggiunta della preflight classification prima del loop rompe il flusso esistente
  per i casi già coperti (file tracciato, non modificato)?
- Il conflict report strutturato include tutti i campi attesi dai caller esistenti?
- Rischio complessivo: BASSO / MEDIO / ALTO — con motivazione

### Task 2 — Fix README `scf-registry`
- Il drift esiste davvero? (confermato dalla Fase 3)
- La modifica è limitata a testo documentale o tocca file che impattano il runtime?
- Rischio complessivo: BASSO / MEDIO / ALTO — con motivazione

### Task 3 — Append revision notes
- Il file esiste? Aggiungere in fondo è safe?
- C'è rischio che Copilot fraintenda "append" e riscriva l'intero documento?
- Rischio complessivo: BASSO / MEDIO / ALTO — con motivazione

---

## Fase 6 — Verdetto finale

Produci un blocco strutturato con il verdetto:

```
VERDETTO ANALISI PRE-IMPLEMENTAZIONE
=====================================

Task 1 — Preflight classification
  Stato: [APPROVATO / APPROVATO CON CORREZIONI / BLOCCATO]
  Note: <motivazione sintetica>

Task 2 — Fix README scf-registry
  Stato: [APPROVATO / APPROVATO CON CORREZIONI / BLOCCATO]
  Note: <motivazione sintetica>

Task 3 — Append revision notes
  Stato: [APPROVATO / APPROVATO CON CORREZIONI / BLOCCATO]
  Note: <motivazione sintetica>

Ordine sicuro di implementazione: <Task X -> Task Y -> Task Z>
Dipendenze tra task: <nessuna / descrizione>

RACCOMANDAZIONE FINALE:
[PROCEDERE / PROCEDERE CON MODIFICHE / BLOCCARE E RIESAMINARE]
```

---

## REMINDER FINALE

Non hai scritto nulla. Non hai modificato nulla.
Hai solo letto, analizzato e prodotto un rapporto.
Attendi istruzioni esplicite dall'utente prima di procedere con qualsiasi implementazione.
