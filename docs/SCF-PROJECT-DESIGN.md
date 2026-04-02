# SCF — SPARK Code Framework
## Documento di Progettazione Logica — v0.2 — 30 marzo 2026
**Stato:** ✅ implementato
---

## Visione

SCF è un ecosistema aperto di strumenti AI-native per programmatori. Non è un’applicazione — è un’infrastruttura cognitiva che potenzia il modello AI rendendolo consapevole del progetto in cui opera. Si adatta autonomamente al contesto senza configurazioni manuali ripetute, è distribuibile su qualsiasi progetto e utente, e cresce attraverso pacchetti dominio indipendenti creati dalla community.

---

## Architettura Generale: Tre Livelli

### Livello 1 — Il Motore (`spark-framework-engine`)

Il server MCP universale. Legge qualsiasi `.github/` SCF-compatibile e serve agenti, skill, instruction e prompt on-demand al modello AI in Agent mode. Non conosce nessun dominio specifico — conosce solo la struttura SCF. Si installa una volta globalmente in VS Code e funziona su tutti i progetti automaticamente. Contiene il tool di installazione intelligente per bootstrap e aggiornamento dei pacchetti.

**Stato attuale:** funzionante e testato. File `spark-framework-engine.py` nel repo dedicato `spark-framework-engine`, registrato globalmente in VS Code come server `sparkFrameworkEngine`. Python 3.10+, 14 Resource e 13 Tool registrati. Duplicati slash command eliminati.

### Livello 2 — I Pacchetti Dominio (`scf-pack-*`)

Repo GitHub indipendenti che contengono collezioni di file `.github/` specializzati per un ambito. Ogni pacchetto rispetta il protocollo SCF ma è completamente autonomo — può essere creato da chiunque, aggiornato indipendentemente, installato selettivamente. Il motore li trova tramite il registry.

Esempi previsti: `scf-pack-gamedev`, `scf-pack-writer`, `scf-pack-backend`, `scf-pack-accessibility`.

### Livello 3 — Il Registry (`scf-registry`)

Indice centralizzato dei pacchetti pubblici. Read-only per gli utenti, modificabile solo dagli amministratori e dai creatori tramite Pull Request. Ogni voce contiene: nome identificativo, URL del repo, versione corrente, descrizione breve, compatibilità minima con il motore. La v1 supporta solo pacchetti pubblici; il supporto a pacchetti privati è previsto come estensione futura.

---

## Separazione dei Domini in VS Code

| Meccanismo | Gestito da | Quando si attiva | Chi lo invoca |
|---|---|---|---|
| Slash command `/scf-*` | VS Code nativo | Quando l’utente digita `/` | L’utente |
| Tool e Resource MCP | Server `spark-framework-engine` | On-demand in Agent mode | Il modello AI |

I due sistemi non si sovrappongono mai. I prompt files in `.github/prompts/` compaiono nel picker `/` una volta sola, gestiti nativamente da VS Code senza passare per il server MCP.

---

## Il Protocollo SCF

Il protocollo è il contratto che tutti i partecipanti all’ecosistema rispettano. Definisce quattro tipi di file, ognuno con frontmatter standard. Il campo `type` è l’unico universalmente obbligatorio — senza di esso il file non esiste per il sistema.

### Agente

Rappresenta un’identità cognitiva specializzata — la metafora è il dipendente con un ruolo preciso.

- **Obbligatori:** `type: agent` — `name` — `role`
- **Opzionali:** `domain` — `skills` — `model` — `version` — `author`

### Skill

Rappresenta una capacità tecnica atomica e riusabile — la metafora è il corso di formazione disponibile a tutti.

- **Obbligatori:** `type: skill` — `name` — `domain`
- **Opzionali:** `input` — `output`

### Instruction

Rappresenta una regola sempre attiva nel contesto — la metafora è il regolamento interno sempre in vigore.

- **Obbligatori:** `type: instruction` — `name` — `scope`
- **Valori di `scope`:** `global` sempre presente — `agent` attiva solo con quell’agente — `domain` attiva per quell’ambito
- **Opzionali:** nessuno di critico

### Prompt

Rappresenta un workflow predefinito per l’utente — la metafora è la procedura operativa standard.

- **Obbligatori:** `type: prompt` — `name` — `description`
- **Opzionali:** `agent` per collegare il prompt a uno specialista specifico

---

## Degradazione Graziosa

Il motore gestisce file incompleti su tre scenari distinti senza mai crashare.

**Scenario 1 — Campo non critico mancante:** default silenzioso, zero impatto sul comportamento.

**Scenario 2 — Campo semi-critico mancante** (`role` in un agente, `domain` in una skill): nota esplicita nel contenuto servito al modello, che può compensare chiedendo chiarimenti all’utente invece di assumere comportamenti arbitrari.

**Scenario 3 — File senza `type` riconoscibile:** ignorato completamente, non genera errori, non compare in nessuna lista.

**Regola fondamentale:** il motore trasporta il contenuto senza interpretarlo — è sempre il modello AI che interpreta. Il sistema non prende mai decisioni autonome sul contenuto.

---

## Gestione dei Pacchetti

### Due Livelli Separati

Il **registry globale** è read-only per gli utenti — aggiunta e rimozione solo tramite PR degli amministratori. Il **progetto locale** è sotto pieno controllo dell’utente — installa, disinstalla e aggiorna solo il suo `.github/`, senza mai toccare il registry condiviso.

### Stato dei Pacchetti nel Registry

- `active` — disponibile e supportato
- `deprecated` — ancora accessibile con avviso, nessun aggiornamento futuro, suggerito il successore

Un pacchetto deprecato non viene mai rimosso — garantisce che i progetti esistenti non si rompano mai improvvisamente.

---

## Modello di Aggiornamento

### Il Manifesto di Installazione

File leggero nascosto in `.github/` che registra per ogni file SCF: pacchetto di origine, versione di installazione, e se l’utente lo ha modificato. Gestito automaticamente dal motore, invisibile all’utente.

### Le Quattro Categorie di File all’Aggiornamento

**File invariato nel pacchetto:** nessun intervento indipendentemente dalle personalizzazioni utente.

**File aggiornato nel pacchetto, non toccato dall’utente:** aggiornamento automatico silenzioso.

**File aggiornato nel pacchetto, modificato dall’utente:** confronto esplicito presentato all’utente con tre opzioni — tenere la propria versione, adottare la versione del pacchetto, merge manuale selettivo.

**File nuovo nel pacchetto:** aggiunto sempre automaticamente — un file nuovo non può sovrascrivere nulla.

### Le Tre Policy di Aggiornamento

L’utente configura una policy di default per il suo progetto.

**Conservativa:** aggiorna solo i file mai toccati dall’utente. Per progetti stabili in produzione.

**Collaborativa** *(default)*: automatica dove sicuro, confronto esplicito dove c’è conflitto. Per la maggior parte dei progetti in sviluppo.

**Aggressiva:** adotta sempre la versione più recente del pacchetto, con backup automatico preventivo dell’intero `.github/`. Per chi vuole sempre l’ultima versione.

### Principio Unificante

Nessuna operazione distruttiva è mai irreversibile. Prima di qualsiasi sovrascrittura esiste un backup, prima di qualsiasi conflitto esiste una scelta esplicita, prima di qualsiasi deprecazione esiste un preavviso. L’utente mantiene sempre il controllo.

### Aggiornamento del Motore

Quando si aggiorna `spark-framework-engine`, al primo avvio il motore verifica la compatibilità dei file esistenti con il nuovo protocollo. I file con frontmatter di versione precedente vengono letti con degradazione graziosa e viene suggerita una migrazione assistita che aggiorna solo il frontmatter senza toccare il contenuto. Sempre opzionale, sempre reversibile.

---

## Manifesto di Installazione — Specifica Tecnica

**File:** `.github/.scf-manifest.json`
**Formato:** JSON object con `schema_version` e array `entries`. Ogni voce traccia un file SCF installato da pacchetto.

```json
{
  "schema_version": "1.0",
  "entries": [
    {
      "file": "agents/developer.md",
      "package": "scf-pack-gamedev",
      "package_version": "1.2.0",
      "installed_at": "2026-03-30T12:00:00Z",
      "sha256": "abc123..."
    }
  ]
}
```

**Campi di ogni voce `entries`:**
- `file`: percorso relativo alla root di `.github/` (stringa, obbligatorio)
- `package`: nome del pacchetto di origine (stringa, obbligatorio)
- `package_version`: versione del pacchetto all'installazione (semver, obbligatorio)
- `installed_at`: timestamp ISO 8601 UTC (stringa, obbligatorio)
- `sha256`: hash SHA-256 del contenuto del file all'installazione (stringa, obbligatorio)

**`user_modified`** è un valore calcolato on-demand confrontando l'hash salvato con l'hash corrente del file su disco. Non viene persistito nel manifesto.

**Rilevamento modifiche:** confronto SHA-256 on-demand. Il `mtime` del filesystem non viene usato (inaffidabile su Windows con cloud sync). Non viene usato `git diff` (dipendenza esterna non garantita).

**Gestione dei casi speciali:**
- **File rimosso localmente:** la voce resta nel manifesto; alla prossima operazione viene marcata come file mancante e trattata come divergenza da risolvere.
- **File rinominato localmente:** non inferito come rename automaticamente; il vecchio percorso risulta mancante, il nuovo non è gestito.
- **Disinstallazione di pacchetto:** cancellazione dei file con hash invariato; file modificati dall'utente preservati e segnalati come residui locali.

---

## Registry — Specifica Tecnica

**Repo:** `scf-registry` (GitHub, pubblico, read-only per utenti)
**File indice:** `registry.json` nella root del repo

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

**Protocollo di interrogazione v1:** HTTP GET sul raw URL di GitHub. Nessun clone locale, nessuna autenticazione. Supporta solo pacchetti pubblici raggiungibili senza credenziali.

**Raw URL del registry:** `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json`

**Comportamento offline:** se la richiesta fallisce (timeout 5s), il motore usa la cache in `.github/.scf-registry-cache.json`. Se non esiste nemmeno quella, errore esplicito senza crashare.

**Repo privati (fuori scope v1):** se l'utente fornisce una URL non `raw.githubusercontent.com`, il motore restituisce errore esplicito. Nessun accesso implicito a URL private. Supporto previsto come estensione futura.

---

## Versioning del Motore e del Protocollo

Sono gestite due versioni distinte con cicli di vita indipendenti.

### `ENGINE_VERSION` — versione del motore

Costante Python `ENGINE_VERSION` in `spark-framework-engine.py`. Segue semver `MAJOR.MINOR.PATCH`.

- `PATCH`: bugfix interni, nessun cambio al contratto di protocollo.
- `MINOR`: nuove capacità del motore compatibili all'indietro.
- `MAJOR`: cambio strutturale del server o dell'API locale che può richiedere adeguamenti.

### `protocol_version` — versione del protocollo SCF

Dichiarata per-pacchetto dai changelog dei singoli pacchetti installati, convenzionalmente in
`.github/changelogs/{package_id}.md`. In fase di runtime il motore legge le versioni dei pacchetti
dall'install manifest `.scf-manifest.json` e le espone come insieme di pacchetti installati.

- `PATCH`: chiarimenti o correzioni senza impatto sul formato SCF.
- `MINOR`: nuovi campi opzionali o nuovi tipi di file; degradazione graziosa automatica.
- `MAJOR`: campi obbligatori rinominati, tipi di file rimossi, struttura cartelle cambiata; richiede migrazione assistita.

### Regola di compatibilità

La compatibilità va verificata confrontando la `protocol_version` richiesta dal pacchetto con quella del workspace — **non** con la `ENGINE_VERSION` interna del server. La `ENGINE_VERSION` traccia l'evoluzione del motore; non definisce la compatibilità dei file SCF installati.

---

## Limiti noti e vincoli di portabilità

### Prompt come risorse testuali, non MCP Prompts nativi

I file `.github/prompts/*.prompt.md` non vengono registrati come artefatti MCP Prompt nativi. Questo è corretto per VS Code: i file compaiono già nel picker `/` come slash command nativi — registrarli di nuovo via MCP causerebbe duplicati.

**Implicazione per client alternativi:** client MCP diversi da VS Code (Claude Desktop, altri IDE) vedono i prompt solo come risorse testuali generiche tramite `prompts://list` e `prompts://{name}`, non come artefatti MCP Prompt invocabili nativamente. Vincolo strutturale consapevole della v1.

### Registry pubblico only in v1

Il supporto a registry o repository privati non è implementato. Qualsiasi URL non `raw.githubusercontent.com` fornita senza autenticazione produce un errore esplicito, mai un tentativo silenzioso.

---

## Prossimi Passi

1. ~~Estrarre `scf-mcp-server.py` dal repo `solitario-classico-accessibile` e portarlo in questo repo come motore principale~~ — **completato**
2. Implementare il tool di installazione intelligente con logica diff e manifesto di installazione
3. Creare repo `scf-registry` con file indice iniziale
4. Costruire il primo pacchetto dominio come riferimento per la community
5. Documentare il protocollo SCF come standard aperto nel repo — in corso (specifiche tecniche aggiunte in questo documento)

---

*Documento generato il 29 marzo 2026 — fase di progettazione logica completata.*
*Revisione del 30 marzo 2026 — aggiornati: A1 (stato attuale), A3 (manifesto), A4 (registry), B1 (versioning), C2 (limiti portabilità).*
