# SPARK Framework — Proposta Strategica Implementativa

## SCF File Ownership & Workspace Merge System

**Versione:** 1.1.0-draft
**Data:** 17 Aprile 2026
**Autore:** Nemex81 / SPARK Architecture Team
**Stato:** Proposta corretta — Validazione superata con correzioni
**Repository di riferimento:** `spark-framework-engine`, `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`, `scf-registry`

---

## Indice

- Premessa e Obiettivo
- Parte 1 — Convenzione Universale di Ownership dei File
- Parte 2 — Schema a Marcatori per `copilot-instructions.md`
- Parte 3 — Preferenze Persistenti di Aggiornamento
- Parte 4 — Flusso Operativo Completo con Autorizzazione
- Parte 5 — Modalità di Aggiornamento
- Parte 6 — Architettura dei Tool nell'Engine
- Parte 7 — Fasi di Implementazione
- Appendice A — Note di Compatibilità con Engine Esistente
- Appendice B — Log di Validazione

---

## Premessa e Obiettivo

Il sistema SPARK distribuisce file nel workspace dell'utente attraverso pacchetti SCF (`.github/agents/`, `.github/instructions/`, `.github/skills/`, ecc.). Attualmente manca un meccanismo formale che regoli cosa accade a quei file quando un pacchetto viene installato, aggiornato o rimosso: non esiste tracciabilità di ownership, non esiste logica di merge, non esiste protezione delle personalizzazioni dell'utente.

Questa proposta definisce il sistema completo per risolvere il problema su tre livelli:

- **Ownership**: ogni file conosce il pacchetto di provenienza.
- **Merge**: i file aggregati (come `copilot-instructions.md`) si aggiornano per sezioni senza distruggere il contenuto utente.
- **Controllo**: l'utente sceglie come gestire gli aggiornamenti, con preferenze persistenti e autorizzazione esplicita alle operazioni sulla cartella protetta `.github/`.

---

## Parte 1 — Convenzione Universale di Ownership dei File

### Principio

Ogni file che un pacchetto SCF deposita nel workspace deve portare in sé la propria provenienza. Il sistema deve sapere sempre chi ha scritto cosa per gestire aggiornamenti, conflitti e rimozioni in modo deterministico. Questa convenzione si applica a **tutti** i file di **tutti** i pacchetti, non solo a `copilot-instructions.md`.

### Schema Front Matter per File `.md`

Ogni file `.md` deployato nel workspace da un pacchetto SCF porta questo front matter YAML obbligatorio:

```yaml
---
spark: true                       # OBBLIGATORIO — campo di riconoscimento per verify_integrity()
scf_owner: "scf-master-codecrafter"
scf_version: "1.0.0"
scf_file_role: "agent"          # agent | instruction | skill | prompt | config
scf_merge_strategy: "replace"   # replace | merge_sections | user_protected
scf_merge_priority: 20          # ordine composizione nei file aggregati
scf_protected: false            # true = mai sovrascrivibile senza conferma esplicita
---
```

> **Nota:** Il campo `spark: true` è obbligatorio per tutti i file `.md` gestiti dal framework. L'engine lo usa in `verify_integrity()` per distinguere file SCF orfani (`untagged_spark_files`) da file utente (`user_files`). I nuovi campi `scf_*` si aggiungono a `spark: true`, non lo sostituiscono.

Il campo `scf_merge_strategy` governa il comportamento del sistema ad ogni aggiornamento:

- `replace` — il file viene sostituito integralmente. Si usa per file il cui contenuto è interamente di competenza del pacchetto.
- `merge_sections` — attiva il sistema a marcatori `SCF:BEGIN/END` descritto nella Parte 2. Si usa per file aggregati come `copilot-instructions.md`.
- `user_protected` — dopo la prima installazione il file appartiene all'utente. Il pacchetto può solo proporre aggiornamenti, mai imporli. Ogni modifica richiede conferma esplicita indipendentemente dalla policy attiva.

Il campo `scf_merge_priority` determina l'ordine delle sezioni nei file aggregati: valori bassi appaiono prima. `spark-base` usa priorità 10, `scf-master-codecrafter` usa 20, i plugin specializzati usano 30 e oltre.

Il campo `scf_protected: true` è una protezione assoluta hard-coded: il sistema non sovrascrive mai silenziosamente un file con questo flag attivo, nemmeno in modalità automatica. È la linea di difesa finale contro la perdita di dati involontaria.

### Tracciamento dei File Non-Markdown

Per i file non-Markdown (JSON di configurazione, file `.agent.md` senza front matter standard, risorse binarie), la ownership viene tracciata esclusivamente nel `package-manifest.json` del pacchetto con gli stessi metadati in forma di record JSON:

```json
{
  "files": [
    {
      "path": ".github/runtime/orchestrator-state.json",
      "scf_owner": "scf-master-codecrafter",
      "scf_version": "1.0.0",
      "scf_file_role": "config",
      "scf_merge_strategy": "user_protected",
      "scf_protected": true
    }
  ]
}
```

### Scope di Applicazione per Pacchetto

Questa normalizzazione va eseguita sui seguenti repo prima di qualsiasi modifica all'engine:

- `spark-base` — tutti i file `.md` in `.github/` (76 file, già hanno `spark: true`)
- `scf-master-codecrafter` — tutti i file `.md` in `.github/` inclusi i 4 agent file in `.github/agents/` (13 file, già hanno `spark: true`)
- `scf-pycode-crafter` — tutti i file `.md` esistenti (12 file); creazione ex novo di `copilot-instructions.md` con sezione contribuita

> **Nota:** `scf-registry` è escluso dalla normalizzazione. È un repository dati (contiene solo `registry.json` e `README.md`) e non è un pacchetto SCF deployabile nel workspace utente.

---

## Parte 2 — Schema a Marcatori per `copilot-instructions.md`

### Principio

Il file `copilot-instructions.md` nel workspace dell'utente è un file **aggregato**: non appartiene a nessun singolo pacchetto ma raccoglie contributi di tutti quelli installati. Il sistema a marcatori consente aggiornamenti chirurgici per blocchi senza toccare il resto del file.

### Struttura del File nel Workspace Utente

```markdown
<!-- SCF:HEADER — generato da SPARK Framework Engine -->
<!-- NON modificare i marker SCF. Il contenuto tra i marker è gestito dal sistema. -->
<!-- Il testo fuori dai marker è tuo: SPARK non lo tocca mai in nessuna modalità. -->

# Copilot Instructions — Workspace

<!-- Le tue istruzioni custom personali vanno QUI, sopra i blocchi SCF -->

<!-- SCF:BEGIN:spark-base@1.0.0 -->
## Regole Base — spark-base
... contenuto estratto e normalizzato da spark-base ...
<!-- SCF:END:spark-base -->

<!-- SCF:BEGIN:scf-master-codecrafter@1.0.0 -->
## Istruzioni Master CodeCrafter
... contenuto ...
<!-- SCF:END:scf-master-codecrafter -->

<!-- SCF:BEGIN:scf-pycode-crafter@2.0.0 -->
## Istruzioni Python Crafter
... contenuto ...
<!-- SCF:END:scf-pycode-crafter -->
```

### Regole dei Marcatori

Il marker di apertura ha la forma `<!-- SCF:BEGIN:{package_id}@{version} -->`. Il marker di chiusura ha la forma `<!-- SCF:END:{package_id} -->`. La regex di ricerca per trovare un blocco esistente è tollerante sulla versione: usa `<!-- SCF:BEGIN:{package_id}@[^\s>]+ -->` per il match, così un aggiornamento da `1.0.0` a `1.1.0` (o anche `2.0.0-beta.1`) trova e sostituisce correttamente il blocco precedente. Il pattern `[^\s>]+` è compatibile con SemVer completo incluse versioni pre-release e build metadata.

Il testo dell'utente che si trova **fuori** da qualsiasi marcatore `SCF:BEGIN/END` è **intoccabile** in qualunque modalità operativa, inclusa quella Sostitutiva. Questa è la garanzia assoluta di non-distruzione del contenuto personalizzato.

Quando un pacchetto viene rimosso, il suo intero blocco marcato — dal `SCF:BEGIN` al `SCF:END` corrispondente — viene eliminato dal file. Il resto rimane invariato.

### Contenuto dei `copilot-instructions.md` nei Pacchetti

Ogni pacchetto espone nel proprio `copilot-instructions.md` **solo la propria sezione contribuita**, non un file completo. Il front matter indica i campi di merge:

```yaml
---
spark: true
scf_owner: "scf-master-codecrafter"
scf_version: "1.0.0"
scf_file_role: "config"
scf_merge_strategy: "merge_sections"
scf_merge_priority: 20
scf_protected: false
---

## Istruzioni SCF Master CodeCrafter

... solo il contenuto pertinente da iniettare nel workspace ...
```

---

## Parte 3 — Preferenze Persistenti di Aggiornamento

### Principio

L'utente può configurare una policy di aggiornamento persistente che il sistema rispetta ad ogni operazione successiva, eliminando la necessità di scegliere ogni volta. La policy è salvata in un file dedicato nel workspace e modificabile in qualsiasi momento.

### File di Configurazione: `spark-user-prefs.json`

Posizione nel workspace: `.github/runtime/spark-user-prefs.json`

Questo file è separato dall'`orchestrator-state.json` che gestisce lo stato operativo delle sessioni. Il `ManifestManager` lo tratta come file `user_protected: true`: non viene mai sovrascritto da aggiornamenti di pacchetti.

```json
{
  "update_policy": {
    "auto_update": false,
    "default_mode": "ask",
    "mode_per_package": {},
    "mode_per_file_role": {},
    "last_changed": "",
    "changed_by_user": true
  }
}
```

Il campo `auto_update` è il booleano principale. Se `false`, il sistema si comporta sempre in modo interattivo: mostra il riepilogo e aspetta la scelta dell'utente indipendentemente da tutto il resto. Se `true`, usa `default_mode` senza chiedere nulla, salvo le protezioni implicite descritte più avanti.

Il campo `default_mode` accetta i valori `"ask"` (equivale a `auto_update: false`), `"integrative"`, `"replace"`, `"conservative"`. La modalità `"selective"` non può essere impostata come default automatico perché richiede interazione per definizione: se l'utente tenta di impostarla, il sistema la riporta a `"ask"` con un avviso esplicito.

### Override Granulari

I campi `mode_per_package` e `mode_per_file_role` consentono override rispetto al `default_mode` globale:

```json
"mode_per_package": {
    "scf-pycode-crafter": "ask"
},
"mode_per_file_role": {
    "agent": "conservative",
    "instruction": "integrative"
}
```

La priorità di risoluzione è: `mode_per_package` batte `mode_per_file_role` che batte `default_mode` globale.

### Protezioni Implicite Non Disattivabili

Anche con `auto_update: true` e `default_mode: "replace"`, il sistema non sovrascrive mai silenziosamente:

- File con `scf_protected: true` nel front matter o nel manifest — richiede sempre conferma esplicita.
- File modificati dall'utente in modalità `replace` automatica — richiede conferma puntuale per quel singolo file. La modifica viene rilevata confrontando il SHA-256 corrente con quello registrato nel manifest al momento dell'ultima installazione.

### Tool MCP di Gestione Policy

**`scf_get_update_policy()`** — legge e restituisce il contenuto di `spark-user-prefs.json` in formato leggibile. Nessun effetto collaterale.

**`scf_set_update_policy(auto_update, default_mode, mode_per_package, mode_per_file_role)`** — scrive la policy nel file. Tutti i parametri tranne `auto_update` sono opzionali: se non passati, i valori attuali non vengono modificati. Valida che `default_mode` non sia `"selective"` e in quel caso corregge con avviso. Aggiorna `last_changed` con timestamp ISO e imposta `changed_by_user: true`.

### Configurazione alla Prima Esecuzione

Il primo avvio di `scf_bootstrap_workspace`, prima che esista qualsiasi preferenza, restituisce un risultato strutturato che include la richiesta di configurazione. L'agente (Copilot) presenta le opzioni all'utente in chat:

> **Nota MCP:** I tool MCP non supportano prompt interattivi nativi. Tutti i "dialoghi" descritti in questo documento sono return value strutturati che l'agente di chat interpreta e presenta all'utente. Il tool restituisce `{"action_required": "configure_update_policy", "options": [...]}` e l'agente formula la domanda.

```json
{
  "action_required": "configure_update_policy",
  "options": [
    {"key": "ask", "label": "Chiedimi ogni volta (default sicuro)", "recommended": true},
    {"key": "integrative", "label": "Automatico integrativo"},
    {"key": "conservative", "label": "Automatico conservativo"},
    {"key": "ask_later", "label": "Sceglier\u00f2 in seguito"}
  ]
}
```

La risposta viene salvata in `spark-user-prefs.json` tramite `scf_set_update_policy()` prima di procedere. Se l'utente non risponde o annulla, il sistema salva `auto_update: false` e continua: il fail-safe punta sempre verso la modalit\u00e0 interattiva.

---

## Parte 4 — Flusso Operativo Completo con Autorizzazione

Ogni operazione che modifica file nel workspace (install, update, bootstrap) esegue sempre questa sequenza in ordine rigido. Nessun passo può essere saltato.

### Step 1 — Lettura Policy

Il sistema legge `spark-user-prefs.json`. Se il file non esiste (prima esecuzione), esegue la configurazione iniziale descritta nella Parte 3 prima di procedere.

### Step 2 — Generazione Riepilogo Pre-Operazione

Il tool `_scf_diff_workspace()` confronta il manifest del pacchetto con lo snapshot corrente del workspace e genera il riepilogo. Ogni file viene classificato con uno di questi status: `new` (non esiste nel workspace), `updated_clean` (esiste, non modificato dall'utente), `updated_user_modified` (esiste, l'utente l'ha modificato rispetto all'originale), `unchanged` (identico alla versione installata, nessuna azione necessaria).

```
[SPARK] Riepilogo operazione: install scf-master-codecrafter@1.0.0
────────────────────────────────────────────────────────────────────
File da gestire nel tuo workspace (.github/):

  1. copilot-instructions.md        → sezione da aggiungere/aggiornare
  2. agents/Agent-Orchestrator.md   → NUOVO (non esiste nel workspace)
  3. agents/Agent-Code.md           → ESISTENTE, versione installata: 0.9.0
  4. instructions/python.md         → ESISTENTE, modificato da te (*)

(*) Il file risulta modificato rispetto alla versione originale del pacchetto.
```

I file con status `unchanged` non compaiono nel riepilogo: non c'è nulla da fare su di loro.

### Step 3 — Avviso Cartella Protetta e Autorizzazione

Immediatamente dopo il riepilogo, prima di qualsiasi scrittura su disco, il sistema presenta l'avviso obbligatorio:

```
[SPARK] ⚠ Avviso — Operazione su cartella protetta

Le operazioni che stai per eseguire modificano la cartella .github/,
che VS Code considera protetta da scrittura non autorizzata.

Per procedere è richiesta un'autorizzazione esplicita. Scegli:

  [1] Autorizza ora — digita "confermo" in chat
  [2] Usa il prompt /framework-unlock — attiva la sessione sbloccata
       tramite il prompt spark-base: framework-unlock.prompt.md
  [3] Annulla operazione

Senza autorizzazione il sistema non scrive alcun file.
```

L'autorizzazione viene registrata nel campo `github_write_authorized: true` dell'`orchestrator-state.json` e vale **solo per la sessione attiva corrente**. Non persiste oltre la sessione: ogni nuova sessione di lavoro richiede una nuova autorizzazione consapevole. Questo è corretto by design.

### Step 4 — Scelta Modalità o Esecuzione Automatica

Se `auto_update: false` (o `default_mode: "ask"`): il sistema aggiunge al riepilogo le opzioni di scelta e attende la risposta dell'utente.

Se `auto_update: true`: il sistema calcola la modalità effettiva applicando la logica di risoluzione degli override (package → file_role → default globale), stampa un messaggio di conferma con la modalità utilizzata, ed esegue direttamente senza attendere input.

```
[SPARK] Modalità automatica attiva: INTEGRATIVA
Procedendo con l'aggiornamento di 3 file...
```

In entrambi i casi, le protezioni implicite sui file `scf_protected` e sui file modificati dall'utente si applicano sempre, interrompendo l'esecuzione automatica solo dove necessario.

### Step 5 — Backup Automatico Pre-Esecuzione

Se la modalità selezionata (o determinata automaticamente) è **SOSTITUTIVA**, il sistema esegue automaticamente `_scf_backup_workspace()` prima di scrivere qualsiasi file. Il backup viene creato in `.github/runtime/backups/YYYYMMDD-HHMMSS/` e il percorso viene comunicato all'utente. Non è possibile perdere dati in modo irrecuperabile.

### Step 6 — Esecuzione e Log

Il sistema esegue le operazioni file per file secondo la modalità scelta. Al termine, produce un log di esecuzione compatto:

```
[SPARK] Operazione completata: install scf-master-codecrafter@1.0.0
  ✓ copilot-instructions.md      — sezione aggiunta (merge)
  ✓ agents/Agent-Orchestrator.md — creato
  ✓ agents/Agent-Code.md         — aggiornato
  ⚠ instructions/python.md       — saltato (modificato da te, preservato)
```

---

## Parte 5 — Modalità di Aggiornamento

### Modalità 1 — INTEGRATIVO (default raccomandato)

Per `copilot-instructions.md` e qualsiasi file con `scf_merge_strategy: merge_sections`: applica il sistema a marcatori `SCF:BEGIN/END`. Il contenuto dell'utente fuori dai marcatori rimane intatto.

Per i file con `scf_merge_strategy: replace`: sovrascrive solo i file con status `updated_clean`. I file con status `updated_user_modified` vengono **saltati** e segnalati nel log finale con avviso. L'utente mantiene il controllo sulle proprie personalizzazioni.

### Modalità 2 — SOSTITUTIVO

Sovrascrive tutti i file del pacchetto nel workspace, inclusi quelli modificati dall'utente. Richiede il backup automatico obbligatorio in `.github/runtime/backups/YYYYMMDD-HHMMSS/` prima di procedere. Anche in questa modalità, il testo dell'utente fuori dai marcatori SCF in `copilot-instructions.md` rimane intatto.

### Modalità 3 — CONSERVATIVO

Il pacchetto viene registrato nel manifest come "installato" ma nessun file nel workspace viene toccato. È la modalità giusta quando l'utente ha già versioni custom di tutti i file e vuole solo che il runtime SPARK riconosca il pacchetto come attivo per abilitare i suoi tool e le sue risorse MCP.

### Modalità 4 — SELETTIVO

Il sistema presenta ogni file del riepilogo uno alla volta con una descrizione leggibile delle differenze (non un diff tecnico). Esempio: "aggiunge la sezione Routing Agenti Python, modifica la versione engine minima da 1.9.0 a 2.1.0". Per ogni file l'utente sceglie tra tre azioni: **applica** (esegue l'operazione standard per quel file), **salta** (preserva il file corrente), **applica con note** (l'utente scrive testo libero che il sistema integra come commento nella sezione utente del file, fuori dai marcatori SCF).

La modalità Selettiva non può essere impostata come `default_mode` automatico. Se impostata, il sistema la riporta a `"ask"` con avviso.

---

## Parte 6 — Architettura dei Tool nell'Engine

La logica è distribuita in utility private e tool pubblici. Nessun monolite.

### Utility Private (non esposte come tool MCP)

**`_scf_diff_workspace(package_id, version)`** — Confronta il manifest del pacchetto con lo snapshot corrente del workspace. Ritorna lista di file con status: `new`, `updated_clean`, `updated_user_modified`, `unchanged`. Il rilevamento di `updated_user_modified` avviene confrontando SHA-256 corrente con quello registrato nel manifest all'ultima installazione. Chiamata da tutti i tool pubblici per generare il riepilogo.

**`_scf_section_merge(source_content, target_path, strategy, package_id, version)`** — Implementa le tre strategie di merge per i file a sezioni. Per `merge_sections`: regex tollerante sulla versione del marcatore, gestione di `merge_priority` per l'ordinamento delle sezioni nel file aggregato, preservazione garantita del testo utente fuori dai marcatori. **Non scrive su disco**: restituisce il contenuto finale al chiamante, che \u00e8 responsabile della scrittura. Questo mantiene il principio di separazione tra logica e I/O.

> **Nota:** Questa utility \u00e8 distinta da `MergeEngine.diff3_merge()` gi\u00e0 presente nell'engine. `MergeEngine` gestisce merge 3-way a livello di file (confronto riga per riga tra base/ours/theirs). `_scf_section_merge()` gestisce composizione per blocchi marcati `SCF:BEGIN/END` in file aggregati. Le due utility non si sovrappongono.

**`_scf_backup_workspace(package_id)`** — Crea snapshot datato in `.github/runtime/backups/YYYYMMDD-HHMMSS/` dei soli file che verranno modificati dall'operazione corrente. Chiamata automaticamente e obbligatoriamente prima di qualsiasi operazione in modalità Sostitutiva.

### Tool Pubblici Nuovi

**`scf_get_update_policy()`** — Legge e restituisce `spark-user-prefs.json` in formato leggibile. Nessun effetto collaterale.

**`scf_set_update_policy(auto_update, default_mode, mode_per_package, mode_per_file_role)`** — Scrive la policy. Parametri opzionali tranne `auto_update`. Valida `default_mode`, aggiorna `last_changed` e `changed_by_user`.

**`scf_bootstrap_workspace(mode)`** — Il 28° tool. Flusso completo in ordine: configurazione policy iniziale (se prima esecuzione) → riepilogo diff su tutti i file base di `spark-base` → avviso cartella protetta → autorizzazione → esecuzione con modalità scelta. Sentinella di idempotenza: `.github/agents/spark-assistant.agent.md`. Se già presente, il riepilogo mostra "workspace già inizializzato" e propone solo le differenze rispetto alla versione corrente installata.

### Tool Pubblici Esistenti da Aggiornare

**`scf_install_package(package_id, version, mode)`** e **`scf_update_package(...)`** — Il parametro `mode` diventa opzionale. Se assente, esegue l'intero flusso interattivo (Steps 1-6 della Parte 4). Se presente, legge comunque la policy per le protezioni implicite, poi esegue direttamente con il mode passato saltando la domanda di scelta.

---

## Parte 7 — Fasi di Implementazione

Le fasi sono strettamente sequenziali. Ogni fase è prerequisito della successiva. Non si inizia una fase se la precedente non è completata e testata.

### Fase A — Normalizzazione dei Pacchetti

**Scope:** tutti i repo dei pacchetti. Nessuna modifica all'engine.

Aggiungere il front matter SCF a tutti i file `.md` in `.github/` di `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`. Il campo `spark: true` gi\u00e0 presente va preservato; i nuovi campi `scf_*` si aggiungono dopo di esso. Creare `copilot-instructions.md` per `scf-pycode-crafter` con front matter e contenuto della sezione contribuita.

Aggiornare i `package-manifest.json` di ogni pacchetto portando lo schema a `2.1` e aggiungendo il campo `files_metadata` come array parallelo a `files`. Il campo `files` attuale (array di stringhe) resta invariato per backward compatibility. Il campo `files_metadata` contiene gli oggetti con metadati SCF:

```json
{
  "schema_version": "2.1",
  "files": [".github/agents/Agent-Code.md", "..."],
  "files_metadata": [
    {
      "path": ".github/agents/Agent-Code.md",
      "scf_file_role": "agent",
      "scf_merge_strategy": "replace",
      "scf_merge_priority": 20,
      "scf_protected": false
    }
  ]
}
```

> **Nota backward compatibility:** L'engine deve supportare sia schema `2.0` (senza `files_metadata`) che `2.1` (con `files_metadata`). Quando `files_metadata` \u00e8 assente, tutti i file vengono trattati con strategia `replace` e `scf_protected: false` come default.

Verificare la coerenza tra front matter dei file e voci nel manifest.

### Fase B — Tool di Policy e Utility Diff/Backup

**Scope:** `spark-framework-engine.py`. Nessuna modifica ai tool pubblici esistenti.

Creare il template di `spark-user-prefs.json` con schema e valori default. Implementare `scf_get_update_policy()` e `scf_set_update_policy()` con validazione. Implementare `_scf_diff_workspace()` con rilevamento SHA-256. Implementare `_scf_backup_workspace()`. Scrivere test unitari isolati prima del codice (approccio TDD light).

### Fase C — Utility di Merge

**Scope:** `spark-framework-engine.py`. Nessuna modifica ai tool pubblici esistenti.

Implementare `_scf_section_merge()` con tutte e tre le strategie. La strategia `merge_sections` \u00e8 la pi\u00f9 complessa e richiede: regex tollerante sulla versione nel marker di apertura (`[^\s>]+` per SemVer completo), ricostruzione del file rispettando `merge_priority`, preservazione assoluta del testo utente fuori dai marcatori, gestione del caso di rimozione pacchetto (eliminazione del blocco). Test unitari per ogni strategia, inclusi casi limite (file nuovo, file senza marcatori esistenti, blocco corrotto, versioni pre-release nei marker).

### Fase D — Integrazione Flusso nei Tool Pubblici

**Scope:** `spark-framework-engine.py`, tool `scf_install_package` e `scf_update_package`.

Agganciare la sequenza completa degli Step 1-6 della Parte 4 in entrambi i tool. Il nuovo parametro `update_mode` (opzionale, distinto da `conflict_mode`) accetta i valori `integrative|replace|conservative|selective`. Se assente, il sistema consulta la policy utente o chiede in chat. `conflict_mode` mantiene il ruolo attuale per la gestione dei conflitti file-level. Integrare l'avviso cartella protetta e il controllo `github_write_authorized` dall'`orchestrator-state.json`. Implementare la logica di risoluzione degli override della policy (`mode_per_package` → `mode_per_file_role` → `default_mode`). Test di integrazione end-to-end con workspace di test.

### Fase E — Estensione `scf_bootstrap_workspace`

**Scope:** `spark-framework-engine.py`, tool pubblico esistente.

Estendere il tool esistente (attualmente gestisce copia asset + installazione opzionale spark-base) aggiungendo il flusso policy/diff/auth descritto nella Parte 4. Il tool non introduce nuova logica: riusa le utility costruite nelle fasi precedenti. Preservare il comportamento attuale come sottoinsieme del flusso esteso. Verificare il comportamento idempotente con workspace gi\u00e0 inizializzato. Verificare il flusso completo dalla configurazione policy iniziale all'esecuzione finale.

### Fase F — Documentazione e Release

**Scope:** `spark-framework-engine.py`, `spark-base`, `scf-master-codecrafter`.

Aggiornare il `copilot-instructions.md` dell'engine per riflettere i nuovi tool e il nuovo sistema. Aggiornare il `CHANGELOG.md` con sezione dedicata alla feature. Bump versione engine secondo SemVer (feature aggiunta → minor version). Aggiornare `README.md` con sezione sulla gestione degli aggiornamenti del workspace.

### Fase G — Migrazione Workspace Esistenti

**Scope:** `spark-framework-engine.py`, documentazione utente.

Implementare la logica di migrazione per workspace già inizializzati con versioni precedenti del sistema. Il primo `scf_update_package` o `scf_bootstrap_workspace` su un workspace pre-esistente deve:
- Rilevare che `spark-user-prefs.json` non esiste e avviare la configurazione iniziale della policy.
- Riconoscere i file già installati senza front matter SCF e trattarli come `scf_merge_strategy: replace` (default retrocompatibile).
- Se `copilot-instructions.md` esiste senza marcatori SCF, **non** iniettare marcatori automaticamente: proporre all'utente la migrazione esplicita al formato a marcatori.
- Creare `spark-user-prefs.json` con policy default `ask` e registrare l'evento nel log.
- Documentare la procedura di migrazione nel README e in un prompt dedicato.

---

## Appendice A — Note di Compatibilità con Engine Esistente

### Componenti Riusabili

| Componente esistente | Ruolo attuale | Riuso nella proposta |
|---|---|---|
| `ManifestManager._is_user_modified()` | SHA-256 compare | Base per `_scf_diff_workspace()` classificazione `updated_user_modified` |
| `ManifestManager.verify_integrity()` | Audit workspace | Esteso con check coerenza front matter vs manifest |
| `SnapshotManager` | Snapshot BASE per 3-way merge | Riusato da `_scf_backup_workspace()` come infrastruttura |
| `MergeEngine.diff3_merge()` | 3-way merge file-level | Invariato — complementare a `_scf_section_merge()` |
| `_SUPPORTED_CONFLICT_MODES` | Validazione conflict_mode | Invariato — il nuovo `update_mode` è parametro separato |

### Invarianti Preservate

- `conflict_mode` parametro di `scf_install_package` e `scf_update_package`: invariato, stessa semantica
- Schema manifest runtime `.scf-manifest.json`: invariato (schema `1.0` entries con file/package/version/sha256)
- Schema registry `registry.json`: invariato (schema `2.0`)
- Comportamento `scf_bootstrap_workspace` attuale: preservato come sottoinsieme del flusso esteso
- `spark: true` come campo di riconoscimento: preservato, i nuovi campi `scf_*` si aggiungono

### Breaking Change Controllati

- `package-manifest.json` dei pacchetti: schema bump `2.0` → `2.1` (aggiunta `files_metadata`)
- Engine deve supportare entrambi gli schema durante il periodo di transizione
- `copilot-instructions.md` nei pacchetti: passa da file completo a sezione contribuita
- I pacchetti aggiornano il proprio `copilot-instructions.md` solo nella release che implementa questa proposta

---

## Appendice B — Log di Validazione

### Validazione v1.1.0 — 17 Aprile 2026

**Esito:** Superata con 13 correzioni applicate.

**Issue critiche risolte:**
1. ✅ Regex marker: `[^-]+` → `[^\s>]+` (compatibile SemVer pre-release)
2. ✅ `spark: true` aggiunto come campo obbligatorio nel front matter
3. ✅ Tool count corretto: bootstrap esiste già (33 tool), 2 nuovi → 35 totali
4. ✅ Schema `files` manifest: introdotto `files_metadata` parallelo per backward compat
5. ✅ MCP interaction model: prompt interattivi riformulati come return value strutturati

**Issue significative risolte:**
6. ✅ `_scf_merge_file` → `_scf_section_merge` per evitare collisione con `MergeEngine`
7. ✅ Aggiunta nota esplicita sulla relazione `conflict_mode` vs `update_mode`
8. ✅ `scf-registry` rimosso dalla normalizzazione (repo dati, non pacchetto)
9. ✅ Aggiunta Fase G per migrazione workspace esistenti

**Issue minori risolte:**
10. ✅ Tabella componenti riusabili in Appendice A
11. ✅ Chiarita complementarità `_scf_backup_workspace` vs `SnapshotManager`
12. ✅ Fase E riformulata come estensione del tool esistente
13. ✅ Sezione backward compatibility manifest in Fase A

---

*Documento generato nell'ambito della sessione di architettura SPARK del 17 Aprile 2026. Versione 1.1.0-draft: correzioni post-validazione applicate.*
