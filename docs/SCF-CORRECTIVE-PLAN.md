# SCF — Piano Correttivo
## Documento di Implementazione — v1.5 — 30 marzo 2026

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
      "id": "scf-pycode-crafter",
      "repo_url": "https://github.com/Nemex81/scf-pycode-crafter",
      "latest_version": "1.0.0",
      "description": "Pacchetto SCF per progetti Python",
      "engine_min_version": "1.0.0",
      "status": "active",
      "tags": ["python", "development", "copilot"]
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

**File da modificare:** `SCF-PROJECT-DESIGN.md`, `spark-framework-engine.py`
**Repo da creare:** `scf-registry`

**Stato:** ✅ completato

---

## BLOCCO B — Priorità Media

### B1 — Definire lo schema di versioning del motore

**Stato:** ✅ completato

---

## BLOCCO C — Priorità Bassa

### C1 — Aggiungere caching a FrameworkInventory

**Stato:** ⏳ da fare (Fase 4)

---

### C2 — Documentare il vincolo di portabilità dei prompt

**Stato:** ✅ completato

---

## BLOCCO D — Decisioni architetturali post-analisi

### D1 — Rimozione degli script dal framework SCF

**Stato:** ✅ completato

---

## BLOCCO E — Implementazione installazione pacchetti

> Aggiunto il 30 marzo 2026. Prerequisito: `scf-pycode-crafter` e `scf-registry` operativi.

### E1 — Creare `package-manifest.json` in ogni repo pacchetto

**Problema:** `scf_install_package` trova il pacchetto nel registry ma non sa quali file
scaricare, perché nessun repo pacchetto pubblica ancora un manifesto dei propri file.

**Intervento:**
- Creare `package-manifest.json` nella root di ogni repo pacchetto (es. `scf-pycode-crafter`).
- Il file elenca tutti i path relativi da installare nel `.github/` del workspace utente.

Schema:
```json
{
  "package": "scf-pycode-crafter",
  "version": "1.0.0",
  "files": [
    ".github/copilot-instructions.md",
    ".github/project-profile.md",
    ".github/AGENTS.md",
    ".github/agents/Agent-Analyze.md"
  ]
}
```

**File da creare:** `package-manifest.json` in ogni repo pacchetto

**Stato:** ⏳ da fare

---

### E2 — Implementare `RegistryClient.fetch_package_manifest(repo_url)`

**Problema:** il motore non ha un metodo per scaricare il manifesto dei file di un pacchetto
dato il suo `repo_url`.

**Intervento:**
- Aggiungere metodo `fetch_package_manifest(repo_url: str) -> dict` a `RegistryClient`.
- L'URL del manifesto si costruisce da `repo_url`:
  `repo_url.replace("github.com", "raw.githubusercontent.com") + "/main/package-manifest.json"`
- Stesso pattern di fetch con timeout e gestione errori già usato per il registry.
- Non cachare il manifesto del pacchetto (a differenza del registry index): va sempre scaricato
  fresco per garantire coerenza con la versione pubblicata.

**File da modificare:** `spark-framework-engine.py` — classe `RegistryClient`

**Stato:** ⏳ da fare

---

### E3 — Implementare download e scrittura file in `scf_install_package`

**Problema:** il body di `scf_install_package` contiene solo un `return` statico con
`success: False` e commento `# Pending until the first package repos are available`.

**Intervento:**
Sostituire il body stub con la logica reale:

```python
# 1. Fetch manifesto file del pacchetto
pkg_manifest = registry.fetch_package_manifest(pkg["repo_url"])
files = pkg_manifest.get("files", [])

# 2. Per ogni file nel manifesto:
installed = []
preserved = []
for file_path in files:
    raw_url = build_raw_url(pkg["repo_url"], file_path)
    content = fetch_raw_file(raw_url)  # nuovo metodo privato
    dest = ctx.workspace_root / file_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    # 3. Guard: non sovrascrivere file modificati dall'utente
    rel = str(Path(file_path).relative_to(".github"))
    if manifest.is_user_modified(rel) is True:
        preserved.append(file_path)
        continue
    dest.write_text(content, encoding="utf-8")
    manifest.upsert(rel, package_id, pkg["latest_version"], dest)
    installed.append(file_path)

return {
    "success": True,
    "package": package_id,
    "version": pkg["latest_version"],
    "installed": installed,
    "preserved": preserved,
}
```

**Nota:** `ctx` e `manifest` sono già disponibili nello scope di `register_tools()` [cite: righe ~340-350 del motore attuale].

**File da modificare:** `spark-framework-engine.py` — tool `scf_install_package`

**Stato:** ⏳ da fare

---

### E4 — Aggiungere tool `scf_remove_package`

**Problema:** il motore espone `scf_install_package` e `scf_update_packages` ma non
ha un tool per rimuovere un pacchetto installato.

**Intervento:**
- Aggiungere tool `scf_remove_package(package_id: str)` in `register_tools()`.
- Il `ManifestManager.remove_package()` esiste già ed è completo: rimuove le voci dal
  manifesto, cancella i file non modificati, preserva i file modificati dall'utente.
- Il tool MCP deve solo chiamarlo e formattare la risposta.

```python
@self._mcp.tool()
async def scf_remove_package(package_id: str) -> dict[str, Any]:
    """Rimuove un pacchetto SCF installato dal workspace."""
    preserved = manifest.remove_package(package_id)
    return {
        "success": True,
        "package": package_id,
        "preserved_user_modified": preserved,
    }
```

**File da modificare:** `spark-framework-engine.py` — `register_tools()`

**Stato:** ⏳ da fare

---

## Ordine di esecuzione BLOCCO E

| Step | Task | File coinvolto | Dipendenze |
|---|---|---|---|
| 1 | E1 | `package-manifest.json` in `scf-pycode-crafter` | nessuna |
| 2 | E2 | `RegistryClient.fetch_package_manifest()` | E1 |
| 3 | E3 | logica reale in `scf_install_package` | E2 |
| 4 | E4 | tool `scf_remove_package` | E3 |

---

## Stato avanzamento complessivo

| ID | Descrizione | Priorità | Stato |
|---|---|---|---|
| A1 | Aggiornare SCF-PROJECT-DESIGN.md | Alta | ✅ completato |
| A2 | Fix parser frontmatter + test | Alta | ✅ completato |
| A3 | Specifica e implementazione manifesto | Alta | ✅ completato |
| A4 | Specifica registry (motore) | Alta | ✅ completato |
| B1 | Schema versioning motore | Media | ✅ completato |
| C1 | Caching FrameworkInventory | Bassa | ⏳ da fare (Fase 4) |
| C2 | Note portabilità prompt | Bassa | ✅ completato |
| D1 | Rimozione script dal framework | Alta | ✅ completato |
| E1 | package-manifest.json in repo pacchetti | Alta | ⏳ da fare |
| E2 | RegistryClient.fetch_package_manifest() | Alta | ⏳ da fare |
| E3 | Logica reale scf_install_package | Alta | ⏳ da fare |
| E4 | Tool scf_remove_package | Media | ⏳ da fare |

---

*Documento aggiornato il 30 marzo 2026 — v1.5: aggiunto BLOCCO E (installazione pacchetti).*
