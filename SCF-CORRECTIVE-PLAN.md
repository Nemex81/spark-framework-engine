# SCF — Piano Correttivo
## Documento di Implementazione — v1.0 — 30 marzo 2026

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
- Aggiungere test unitari per entrambi i formati.
- Non introdurre dipendenza da `PyYAML` o librerie esterne per mantenere il motore leggero.
  Parsing manuale con regex è sufficiente per il sottoinsieme YAML usato da SCF.

**File da modificare:** `spark-framework-engine.py`
**File da creare:** `tests/test_frontmatter_parser.py`

---

### A3 — Definire la specifica del manifesto di installazione

**Problema:** Il documento di design descrive il manifesto di installazione a livello concettuale
ma non fornisce una specifica tecnica. Senza di essa il tool di installazione intelligente non
può essere implementato in modo coerente.

**Specifica proposta:**

**Nome file:** `.github/.scf-manifest.json`
**Formato:** JSON array di oggetti, uno per file SCF installato.

Schema di ogni voce:
```json
{
  "file": "agents/developer.md",
  "package": "scf-pack-gamedev",
  "package_version": "1.2.0",
  "installed_at": "2026-03-30T12:00:00Z",
  "sha256": "abc123...",
  "user_modified": false
}
```

**Campi:**
- `file`: percorso relativo alla root di `.github/` (stringa, obbligatorio)
- `package`: nome identificativo del pacchetto di origine (stringa, obbligatorio)
- `package_version`: versione del pacchetto al momento dell'installazione (stringa semver, obbligatorio)
- `installed_at`: timestamp ISO 8601 UTC (stringa, obbligatorio)
- `sha256`: hash SHA-256 del contenuto del file al momento dell'installazione (stringa, obbligatorio)
- `user_modified`: true se il file è stato modificato rispetto all'hash di installazione (booleano)

**Rilevamento modifiche:** confronto SHA-256 tra hash salvato nel manifesto e hash corrente del file
su disco. Il calcolo avviene on-demand al momento dell'aggiornamento, non continuamente.
Il mtime del filesystem non viene usato (inaffidabile su Windows con OneDrive/cloud sync).

**Perché non git diff:** richiederebbe che il workspace sia un git repo e che il motore abbia
accesso a git — dipendenza esterna non garantita. SHA-256 è self-contained.

**Intervento:**
- Aggiungere la specifica del manifesto a `SCF-PROJECT-DESIGN.md` come nuova sezione.
- Implementare `ManifestManager` in `spark-framework-engine.py`: lettura, scrittura,
  aggiornamento di singole voci, calcolo SHA-256, rilevamento `user_modified`.

**File da modificare:** `SCF-PROJECT-DESIGN.md`, `spark-framework-engine.py`

---

### A4 — Definire la specifica del formato registry

**Problema:** Il documento di design descrive il registry come "indice centralizzato" ma non
definisce il formato del file indice, lo schema dei campi, il protocollo di interrogazione
del motore, né il comportamento in caso di mancata connessione.

**Specifica proposta:**

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

**Protocollo di interrogazione:** HTTP GET sul raw URL di GitHub
(`https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json`).
Nessun clone locale, nessuna autenticazione richiesta per lettura.

**Comportamento offline:** se la richiesta fallisce (timeout 5s), il motore usa l'ultima
copia locale cachata in `.github/.scf-registry-cache.json`. Se non esiste nemmeno quella,
restituisce errore esplicito senza crashare.

**Scoperta diretta (pacchetti privati):** il motore accetta anche URL diretto al `registry.json`
di un repo privato come parametro al tool di installazione, bypassando il registry centrale.

**Intervento:**
- Aggiungere la specifica del registry a `SCF-PROJECT-DESIGN.md`.
- Creare il repo `scf-registry` con `registry.json` iniziale (vuoto con schema valido).
- Implementare `RegistryClient` in `spark-framework-engine.py`: fetch con timeout, cache locale,
  fallback offline.

**File da modificare:** `SCF-PROJECT-DESIGN.md`, `spark-framework-engine.py`
**Repo da creare:** `scf-registry`

---

## BLOCCO B — Priorità Media

### B1 — Definire lo schema di versioning del motore

**Problema:** Il documento promette "verifica della compatibilità dei file esistenti con il nuovo
protocollo" e "migrazione assistita", ma non esiste uno schema di versioning del motore né una
definizione di cosa significa "incompatibile".

**Schema proposto:** Semver standard (`MAJOR.MINOR.PATCH`).

**Semantica:**
- `PATCH`: bugfix, nessun impatto sul protocollo SCF → nessuna migrazione necessaria.
- `MINOR`: nuovi campi opzionali o nuovi tipi di file → degradazione graziosa automatica,
  nessuna migrazione obbligatoria.
- `MAJOR`: campi obbligatori rinominati, tipi di file rimossi, struttura cartelle cambiata
  → migrazione assistita proposta al primo avvio.

**Dove vive la versione del motore:** campo `engine_version` in
`.github/FRAMEWORK_CHANGELOG.md` (già letto dal motore) come prima riga con formato
`# [X.Y.Z] - YYYY-MM-DD`. Questo allinea il versioning del motore con il file già monitorato.

**Intervento:**
- Aggiungere la sezione versioning a `SCF-PROJECT-DESIGN.md`.
- Creare `.github/FRAMEWORK_CHANGELOG.md` nel repo `spark-framework-engine` come template
  di riferimento per i progetti che usano SCF.

**File da modificare:** `SCF-PROJECT-DESIGN.md`
**File da creare:** `.github/FRAMEWORK_CHANGELOG.md` (template)

---

## BLOCCO C — Priorità Bassa

### C1 — Aggiungere caching a FrameworkInventory

**Problema:** Ogni tool call o resource request ridiscorre tutto il filesystem. Non critico ora,
ma non scalabile con molti file SCF installati.

**Intervento:**
- Aggiungere un dizionario `_cache` e un flag `_cache_valid` a `FrameworkInventory`.
- Esporre un metodo `invalidate_cache()` chiamabile dal tool di installazione dopo
  modifiche al `.github/`.
- Nessuna invalidazione automatica basata su tempo: il motore è stateless tra sessioni,
  la cache vive solo per la durata del processo.

**File da modificare:** `spark-framework-engine.py`

---

### C2 — Documentare il vincolo di portabilità dei prompt

**Problema:** La scelta di non registrare i prompt come MCP Prompts nativi è corretta per
VS Code ma introduce un vincolo implicito di portabilità: client MCP diversi da VS Code
(Claude Desktop, altri IDE) vedranno i prompt solo come risorse testuali generiche.

**Intervento:**
- Aggiungere una nota esplicita nella docstring di `list_prompts()` e `register_resources()`
  nel codice: "questo comportamento è corretto per VS Code; client MCP alternativi non
  riceveranno i prompt come artefatti MCP Prompt nativi".
- Aggiungere una sezione "Limiti noti e vincoli di portabilità" a `SCF-PROJECT-DESIGN.md`.

**File da modificare:** `spark-framework-engine.py`, `SCF-PROJECT-DESIGN.md`

---

## Ordine di esecuzione raccomandato

```
Fase 1 (prerequisiti documentali):
  → A1: aggiorna SCF-PROJECT-DESIGN.md
  → A3: aggiungi specifica manifesto a SCF-PROJECT-DESIGN.md
  → A4: aggiungi specifica registry a SCF-PROJECT-DESIGN.md
  → B1: aggiungi sezione versioning a SCF-PROJECT-DESIGN.md

Fase 2 (correzioni al motore):
  → A2: fix parser frontmatter + test unitari
  → C1: caching FrameworkInventory
  → C2: note portabilità nel codice

Fase 3 (nuova infrastruttura):
  → A4 (parte 2): crea repo scf-registry con registry.json iniziale
  → A3 (parte 2): implementa ManifestManager nel motore
  → A4 (parte 3): implementa RegistryClient nel motore
  → tool di installazione intelligente (scf_install_package, scf_update_packages)
```

---

## Stato avanzamento

| ID | Descrizione | Priorità | Stato |
|---|---|---|---|
| A1 | Aggiornare SCF-PROJECT-DESIGN.md | Alta | ⬜ da fare |
| A2 | Fix parser frontmatter + test | Alta | ⬜ da fare |
| A3 | Specifica manifesto installazione | Alta | ⬜ da fare |
| A4 | Specifica e implementazione registry | Alta | ⬜ da fare |
| B1 | Schema versioning motore | Media | ⬜ da fare |
| C1 | Caching FrameworkInventory | Bassa | ⬜ da fare |
| C2 | Note portabilità prompt | Bassa | ⬜ da fare |

---

*Documento generato il 30 marzo 2026 — fase di analisi critica e pianificazione correttiva.*
