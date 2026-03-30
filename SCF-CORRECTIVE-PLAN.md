# SCF — Piano Correttivo
## Documento di Implementazione — v1.3 — 30 marzo 2026

Questo documento descrive tutte le anomalie identificate nell'analisi critica del progetto SCF
e il piano operativo per risolverle prima di procedere ai Livelli 2 e 3.

---

## Contesto dell'analisi

L'analisi ha esaminato `SCF-PROJECT-DESIGN.md` (documento logico) e `spark-framework-engine.py`
(implementazione attuale del Livello 1). Sono state identificate **7 aree di intervento**:
2 anomalie logiche, 3 lacune architetturali, e 2 aree progettuali superficiali.

---

## BLOCCO A — Priorità Alta (prerequisiti per Livelli 2 e 3)

### A1 — Aggiornare il documento di design

**Problema:** `SCF-PROJECT-DESIGN.md` contiene informazioni obsolete. La sezione "Stato attuale"
riporta ancora il vecchio nome del file (`scf-mcp-server.py`) e la vecchia collocazione nel repo
`solitario-classico-accessibile`. La sezione "Prossimi Passi" elenca attività già completate come
se fossero future.

**Intervento:**
- Aggiornare la sezione "Stato attuale" del Livello 1 con i dati reali: file rinominato in
  `spark-framework-engine.py`, repo dedicato `spark-framework-engine`, server registrato
  globalmente come `sparkFrameworkEngine`.
- Rimuovere dalla sezione "Prossimi Passi" i punti già completati (punto 1 e punto 5 parzialmente).
- Aggiungere data di revisione in fondo al documento.

**File da modificare:** `SCF-PROJECT-DESIGN.md`

**Stato:** ✅ completato

---

### A2 — Correggere il parser frontmatter per i campi lista

**Problema:** `parse_markdown_frontmatter()` in `spark-framework-engine.py` gestisce solo valori
scalari (stringa, booleano, intero). I campi YAML lista come `skills: [python, gamedev]` o
`skills:\n  - python\n  - gamedev` vengono restituiti come stringa grezza o ignorati.
Il protocollo SCF definisce `skills` negli agenti come campo opzionale di tipo lista — il contratto
tra protocollo e parser è rotto in silenzio.

**Intervento:**
- Estendere `parse_markdown_frontmatter()` per riconoscere due formati lista YAML:
  1. Inline: `skills: [python, gamedev]` → `["python", "gamedev"]`
  2. Block: chiave seguita da righe con `  - valore` → `["valore1", "valore2"]`
- Usare `unittest` (standard library) come framework di test, senza introdurre dipendenze esterne.
- Aggiungere test unitari per entrambi i formati.
- Coprire nei test anche input malformati e frontmatter assente o incompleto.
- Non introdurre dipendenza da `PyYAML` o librerie esterne per mantenere il motore leggero.
  Parsing manuale con regex è sufficiente per il sottoinsieme YAML usato da SCF.

**File da modificare:** `spark-framework-engine.py`
**File da creare:** `tests/test_frontmatter_parser.py`

**Stato:** ✅ completato

---

### A3 — Definire la specifica del manifesto di installazione

**Problema:** Il documento di design descrive il manifesto di installazione a livello concettuale
ma non fornisce una specifica tecnica. Senza di essa il tool di installazione intelligente non
può essere implementato in modo coerente.

**1) Specifica (validabile nel repo corrente):**

**Nome file:** `.github/.scf-manifest.json`
**Formato:** JSON array di oggetti, uno per file SCF installato.

Schema di ogni voce:
```json
{
  "schema_version": "1.0",
  "file": "agents/developer.md",
  "package": "scf-pack-gamedev",
  "package_version": "1.2.0",
  "installed_at": "2026-03-30T12:00:00Z",
  "sha256": "abc123..."
}
```

**Campi:**
- `schema_version`: versione dello schema del manifesto (stringa, obbligatorio)
- `file`: percorso relativo alla root di `.github/` (stringa, obbligatorio)
- `package`: nome identificativo del pacchetto di origine (stringa, obbligatorio)
- `package_version`: versione del pacchetto al momento dell'installazione (stringa semver, obbligatorio)
- `installed_at`: timestamp ISO 8601 UTC (stringa, obbligatorio)
- `sha256`: hash SHA-256 del contenuto del file al momento dell'installazione (stringa, obbligatorio)
- `user_modified`: valore calcolato on-demand confrontando l'hash salvato nel manifesto con l'hash corrente del file su disco; non viene persistito nel file

**Rilevamento modifiche:** confronto SHA-256 tra hash salvato nel manifesto e hash corrente del file
su disco. Il calcolo avviene on-demand al momento dell'aggiornamento, non continuamente.
Il mtime del filesystem non viene usato (inaffidabile su Windows con OneDrive/cloud sync).

**Comportamento dei casi speciali:**
- **File rimosso localmente:** la voce resta nel manifesto fino al prossimo aggiornamento o verifica esplicita, dove viene marcata come file mancante e trattata come divergenza da risolvere.
- **File rinominato localmente:** non viene inferito automaticamente come rename; il vecchio percorso risulta mancante e il nuovo file risulta non gestito finché l'utente o il tool non aggiorna il manifesto esplicitamente.
- **Disinstallazione di pacchetto:** il motore rimuove dal manifesto tutte le voci associate al pacchetto e cancella solo i file ancora allineati all'hash installato; i file modificati dall'utente vengono preservati e segnalati come residui locali.

**Perché non git diff:** richiederebbe che il workspace sia un git repo e che il motore abbia
accesso a git — dipendenza esterna non garantita. SHA-256 è self-contained.

**2) Implementazione locale (nel motore):**
- Aggiungere la specifica del manifesto a `SCF-PROJECT-DESIGN.md` come nuova sezione.
- Implementare `ManifestManager` in `spark-framework-engine.py`: lettura, scrittura,
  aggiornamento di singole voci, calcolo SHA-256 e valutazione on-demand di `user_modified`.

**3) Infrastruttura esterna (repo o servizi separati):**
- Nessuna infrastruttura esterna richiesta per la v1 del manifesto.
- Criterio di accettazione indipendente: il formato deve essere documentato e implementabile interamente nel repo del motore, senza dipendenze su servizi remoti.

**File da modificare:** `SCF-PROJECT-DESIGN.md`, `spark-framework-engine.py`

**Stato:** ✅ completato

---

### A4 — Definire la specifica del formato registry

**Problema:** Il documento di design descrive il registry come "indice centralizzato" ma non
definisce il formato del file indice, lo schema dei campi, il protocollo di interrogazione
del motore, né il comportamento in caso di mancata connessione.

**1) Specifica (validabile nel repo corrente):**

**Repo:** `scf-registry` (GitHub, pubblico, read-only per utenti)
**File indice:** `registry.json` nella root del repo

Schema del file indice:
```json
{
  "schema_version": "1.0",
  "updated_at": "2026-03-30T12:00:00Z",
  "packages": [
    {
      "id": "scf-pack-gamedev",
      "repo_url": "https://github.com/Nemex81/scf-pack-gamedev",
      "latest_version": "1.0.0",
      "description": "Pacchetto dominio per sviluppo videogiochi",
      "engine_min_version": "1.0.0",
      "status": "active",
      "tags": ["gamedev", "unity", "pygame"]
    }
  ]
}
```

**Protocollo di interrogazione v1:** HTTP GET sul raw URL di GitHub
(`https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json`).
Nessun clone locale, nessuna autenticazione richiesta per lettura. La v1 supporta solo
pacchetti pubblici raggiungibili senza credenziali.

**Comportamento offline:** se la richiesta fallisce (timeout 5s), il motore usa l'ultima
copia locale cachata in `.github/.scf-registry-cache.json`. Se non esiste nemmeno quella,
restituisce errore esplicito senza crashare.

**Repo privati:** fuori scope per la v1. Il supporto a registry o pacchetti privati resta
un'estensione futura documentata ma non implementata. Se l'utente fornisce una URL privata
senza autenticazione valida, il motore deve restituire errore esplicito e non deve tentare
in modo implicito l'accesso a raw URL privati.

**2) Implementazione locale (nel motore):**
- Aggiungere la specifica del registry a `SCF-PROJECT-DESIGN.md`.
- Implementare `RegistryClient` in `spark-framework-engine.py`: fetch con timeout, cache locale,
  fallback offline.

**3) Infrastruttura esterna (repo o servizi separati):**
- Creare il repo `scf-registry` con `registry.json` iniziale (vuoto con schema valido).
- Trattare `scf-registry` come milestone esterna con criteri di accettazione indipendenti dal motore.
- Criterio di accettazione indipendente: il motore deve funzionare anche in assenza del repo, restituendo un errore esplicito o usando la cache locale se disponibile.

**File da modificare:** `SCF-PROJECT-DESIGN.md`, `spark-framework-engine.py`
**Repo da creare:** `scf-registry`

**Stato:** ✅ completato (motore) — ⏳ repo `scf-registry` da creare

---

## BLOCCO B — Priorità Media

### B1 — Definire lo schema di versioning del motore

**Problema:** Il documento promette "verifica della compatibilità dei file esistenti con il nuovo
protocollo" e "migrazione assistita", ma non separa chiaramente la versione interna del motore
dalla versione del protocollo SCF usata dal workspace. Senza questa distinzione, il concetto di
compatibilità resta ambiguo.

**Schema proposto:** semver standard (`MAJOR.MINOR.PATCH`) applicato separatamente a
`engine_version` e `protocol_version`.

**Versioni distinte:**
- `engine_version`: versione interna di `spark-framework-engine`, vive nel repo del motore come costante Python `ENGINE_VERSION` in `spark-framework-engine.py`.
- `protocol_version`: versione del protocollo SCF dichiarata dal workspace e dai pacchetti, vive in `.github/FRAMEWORK_CHANGELOG.md` del workspace.

**Semantica di `engine_version`:**
- `PATCH`: bugfix o miglioramenti interni del server, nessun cambio al contratto di protocollo.
- `MINOR`: nuove capacità del motore compatibili all'indietro, senza richiedere migrazione dei file SCF esistenti.
- `MAJOR`: cambi strutturali del motore o dell'API locale del server che possono richiedere adeguamenti nel codice del motore o nei tool che lo integrano.

**Semantica di `protocol_version`:**
- `PATCH`: chiarimenti o correzioni senza impatto sul formato SCF.
- `MINOR`: nuovi campi opzionali o nuovi tipi di file con degradazione graziosa automatica.
- `MAJOR`: campi obbligatori rinominati, tipi di file rimossi o struttura cartelle cambiata; richiede migrazione assistita o adattamento esplicito.

**Regola di compatibilità:** la compatibilità va verificata confrontando la `protocol_version`
richiesta dal pacchetto con la `protocol_version` del workspace, non con la versione interna del server.
La `engine_version` serve a tracciare l'evoluzione del motore, ma non definisce da sola la compatibilità
dei file SCF installati.

**Intervento:**
- Aggiungere la sezione versioning a `SCF-PROJECT-DESIGN.md`.
- Introdurre `ENGINE_VERSION` in `spark-framework-engine.py` come costante esplicita del motore.
- Usare `.github/FRAMEWORK_CHANGELOG.md` come riferimento per la `protocol_version` del workspace
  e dei pacchetti, non come contenitore della versione interna del motore.

**File da modificare:** `SCF-PROJECT-DESIGN.md`
**File da modificare in implementazione successiva:** `spark-framework-engine.py`, `.github/FRAMEWORK_CHANGELOG.md`

**Stato:** ✅ completato

---

## BLOCCO C — Priorità Bassa

### C1 — Aggiungere caching a FrameworkInventory

**Problema:** Ogni tool call o resource request ridiscorre tutto il filesystem. Non critico ora,
ma non scalabile con molti file SCF installati.

**Intervento:**
- Trattare questo intervento come ottimizzazione successiva, non come prerequisito architetturale.
- Basare la cache su snapshot `stat()` dei percorsi radice rilevanti (`.github/` e sottocartelle SCF),
  così da invalidarla quando cambia lo stato del filesystem.
- Non affidare l'invalidazione al solo tool di installazione: modifiche manuali nel workspace devono
  poter invalidare la cache alla chiamata successiva.
- La cache resta opzionale e può essere implementata dopo la Fase 3.

**File da modificare:** `spark-framework-engine.py`

**Stato:** ⏳ da fare (Fase 4)

---

### C2 — Documentare il vincolo di portabilità dei prompt

**Problema:** La scelta di non registrare i prompt come MCP Prompts nativi è corretta per
VS Code ma introduce un vincolo implicito di portabilità: client MCP diversi da VS Code
(Claude Desktop, altri IDE) vedranno i prompt solo come risorse testuali generiche.

**Intervento:**
- Aggiungere una nota esplicita nella docstring di `list_prompts()` e `register_resources()`
  nel codice.
- Aggiungere una sezione "Limiti noti e vincoli di portabilità" a `SCF-PROJECT-DESIGN.md`.

**File da modificare:** `spark-framework-engine.py`, `SCF-PROJECT-DESIGN.md`

**Stato:** ✅ completato

---

## BLOCCO D — Decisioni architetturali post-analisi

### D1 — Rimozione degli script dal framework SCF

**Decisione approvata il 30 marzo 2026.**

Il motore SCF è un sistema di contesto cognitivo per il modello AI: serve agenti, skill,
instruction e prompt. Non è un runner di script. La gestione degli script (`ScriptExecutor`,
`scf_run_script`, `scf_list_scripts`, resource `scripts://list` e `scripts://{name}`) era
nata nel contesto specifico del progetto `solitario-classico-accessibile` ed è incompatibile
con la filosofia dichiarata del motore universale.

**Motivazioni:**
- Un motore che esegue script arbitrari (anche con allowlist hardcoded) è un vettore di
  rischio di sicurezza che cresce con ogni pacchetto aggiunto.
- L'allowlist era composta da script di dominio specifico, in contraddizione con il
  principio "il motore non conosce nessun dominio specifico".
- I pacchetti `scf-pack-*` non devono mai dipendere dalla capacità di eseguire script
  nel progetto dell'utente.
- Se un pacchetto necessita di automazione, quella logica appartiene a uno script separato
  che l'utente esegue coscientemente, non a qualcosa che Copilot in Agent mode può invocare
  autonomamente.

**Perimetro della rimozione:**
- Classe `ScriptExecutor` rimossa dal motore.
- Tool `scf_run_script` e `scf_list_scripts` rimossi (tool count: 15 → 13).
- Resource `scripts://list` e `scripts://{name}` rimosse (resource count: 16 → 14).
- Riferimento a `scripts_root` rimosso da `WorkspaceContext` e `WorkspaceLocator`.
- Riferimento a `script_count` rimosso da `build_workspace_info()`.
- `C1` aggiornato: il caching non include più `scripts/` tra i percorsi monitorati.

**Regola permanente:** nessun pacchetto `scf-pack-*` può introdurre dipendenze da
capacità di esecuzione script nel motore. Gli script di supporto di un pacchetto,
se necessari, devono essere documentati come strumenti separati da eseguire manualmente.

**File da modificare:** `spark-framework-engine.py`, `SCF-PROJECT-DESIGN.md`, `README.md`

**Stato:** ⏳ da implementare (prossimo passo)

---

## Prossimi passi operativi

```
Passo 1 — Rimozione script dal motore (D1):
  → Rimuovere ScriptExecutor, scf_run_script, scf_list_scripts
  → Rimuovere resource scripts://list e scripts://{name}
  → Aggiornare WorkspaceContext, WorkspaceLocator, build_workspace_info
  → Aggiornare contatori in log, commenti e README
  → Aggiornare SCF-PROJECT-DESIGN.md

Passo 2 — Creare repo scf-registry:
  → Repo pubblico con README e registry.json iniziale (schema valido, packages: [])
  → Da questo momento RegistryClient trova il file senza errori di rete

Passo 3 — Creare il primo scf-pack-*:
  → Scegliere dominio (gamedev o accessibility)
  → Struttura .github/ completa con agenti, skill, instruction, prompt
  → Aggiungere voce in registry.json

Passo 4 — Ottimizzazioni (Fase 4):
  → C1: caching FrameworkInventory con snapshot stat()
```

---

## Stato avanzamento complessivo

| ID | Descrizione | Priorità | Stato |
|---|---|---|---|
| A1 | Aggiornare SCF-PROJECT-DESIGN.md | Alta | ✅ completato |
| A2 | Fix parser frontmatter + test | Alta | ✅ completato |
| A3 | Specifica e implementazione manifesto | Alta | ✅ completato |
| A4 | Specifica registry (motore) | Alta | ✅ completato |
| A4 | Repo scf-registry da creare | Alta | ⏳ prossimo passo |
| B1 | Schema versioning motore | Media | ✅ completato |
| C1 | Caching FrameworkInventory | Bassa | ⏳ da fare (Fase 4) |
| C2 | Note portabilità prompt | Bassa | ✅ completato |
| D1 | Rimozione script dal framework | Alta | ⏳ prossimo passo |

---

*Documento aggiornato il 30 marzo 2026 — v1.3: aggiunta decisione D1 rimozione script, aggiornati prossimi passi operativi.*
