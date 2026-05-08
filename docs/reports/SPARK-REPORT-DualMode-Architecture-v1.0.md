# SPARK Framework — Proposta Architetturale: Dual-Mode Package System

**Documento:** SPARK-REPORT-DualMode-Architecture-v1.0  
**Data:** 2026-05-08  
**Versione:** 1.0  
**Autore:** Perplexity AI — Ruolo: Coordinatore  
**Destinatario:** GitHub Copilot (Implementatore) — Approvazione: Luca / Nemex81  
**Stato:** Proposta — In attesa di approvazione del Coordinatore  

---

## Executive Summary

Il sistema SPARK attuale gestisce in modo implicito due comportamenti strutturalmente distinti: la fornitura di risorse tramite il protocollo MCP e la scrittura di file fisici nel workspace dell'utente finale. Questa dualità non è sbagliata — è già funzionante — ma non è dichiarata esplicitamente nello schema del manifest, risultando opaca all'utente finale e difficilmente estendibile.

Questa proposta formalizza la separazione in un modello **Dual-Mode** esplicito, introducendo un campo `plugin_files` nel `package-manifest.json` (schema v3.1) e aggiornando la logica di installazione per distinguere chiaramente tra risorse MCP pure e file plugin installati nel workspace. La modifica è minimale, non distruttiva, e compatibile con l'architettura esistente.

---

## 1. Contesto e Motivazione

### 1.1 Struttura Attuale dei Pacchetti

L'analisi diretta dei manifest dei pacchetti installati rivela la seguente distribuzione delle risorse:

**scf-master-codecrafter v2.6.0** — 19 file totali:

- 2 file in `workspace_files` (editor-binding fisici nel workspace)
- 11 agenti in `mcp_resources.agents` (serviti via `agents://`)
- 3 skill in `mcp_resources.skills` (serviti via `skills://`)
- 1 istruzione in `mcp_resources.instructions` (servita via `instructions://`)
- 2 skill in `engine_provided_skills` (fornite direttamente dall'engine, non dal repo del pacchetto)

**scf-pycode-crafter v2.2.1** — 13 file totali:

- 3 file in `workspace_files` (editor-binding fisici nel workspace)
- 5 agenti in `mcp_resources.agents`
- 2 istruzioni in `mcp_resources.instructions`
- 1 file workflow GitHub Actions (`.github/workflows/notify-engine.yml`) — caso speciale

### 1.2 Il Problema della Classificazione Implicita

Osservando i `files_metadata` di entrambi i pacchetti, emergono tre nature distinte di file che oggi vengono gestite con lo stesso meccanismo (`scf_file_role` + `scf_merge_strategy`), senza che il sistema dichiari esplicitamente la loro modalità di delivery:

| Natura del file | Esempi | Dipendenza fisica | Modalità corretta |
|---|---|---|---|
| **Editor-binding** | `copilot-instructions.md`, `AGENTS-*.md`, `*.yml` workflows | Obbligatoria — VS Code, Copilot e GitHub Actions leggono dal filesystem | Plugin fisico nel workspace |
| **On-demand operative** | Agenti `code-Agent-*`, `py-Agent-*`, skill, istruzioni MCP | Nessuna — Copilot li richiede via URI MCP | Risorsa MCP pura |
| **Reference static** | Changelog, README, profili di progetto, reference errori | Nessuna — documentazione ispezionabile | Plugin fisico opzionale o MCP |

Il sistema attuale colloca tutti i file nello store dell'engine e poi decide quali copiare nel workspace tramite `workspace_files`. Questa logica è corretta ma non è comunicata all'utente e non è governabile dal manutentore del pacchetto con granularità sufficiente.

### 1.3 Il Caso `notify-engine.yml`

Il file `.github/workflows/notify-engine.yml` presente in `scf-pycode-crafter` rappresenta un caso diagnostico rilevante: ha `scf_file_role: "config"` come molti altri file, ma la sua natura è fondamentalmente diversa — è un trigger GitHub Actions che deve obbligatoriamente vivere nel filesystem del workspace per essere eseguito. Con lo schema attuale, questa distinzione non è esplicita nel manifest.

---

## 2. Il Modello Dual-Mode Proposto

### 2.1 Definizione dei Due Binari

Il modello introduce due binari di delivery che un pacchetto può usare simultaneamente per file diversi:

**Binario 1 — MCP Service Mode**

Il pacchetto viene caricato nello store interno dell'engine. Le risorse sono servite esclusivamente tramite URI MCP (`agents://`, `skills://`, `instructions://`, `prompts://`). Nessun file viene scritto nel workspace dell'utente. Il ciclo di vita (installazione, aggiornamento, rimozione) è gestito interamente dall'engine tramite i tool MCP esistenti.

- Dipendenza: engine in esecuzione
- Aggiornamenti: automatici al riavvio dell'engine
- Portabilità: nulla — le risorse non esistono offline
- Use case ideale: agenti di sistema, skill di framework, istruzioni operative che l'utente non deve modificare

**Binario 2 — Plugin Mode**

Il pacchetto scrive file fisici nella cartella `.github/` del workspace dell'utente. L'utente possiede questi file, può modificarli, versioinarli con git e portarli in qualsiasi ambiente senza dipendere dall'engine. `ManifestManager` e `WorkspaceWriteGateway` continuano a governare la scrittura, la protezione e il tracciamento esattamente come oggi.

- Dipendenza: nessuna (una volta installati, i file esistono autonomamente)
- Aggiornamenti: manuali via `scf_update_package`, con protezione dei file modificati dall'utente
- Portabilità: massima — il workspace è autocontenuto
- Use case ideale: file editor-binding, workflow CI/CD, profili di progetto, istruzioni personalizzabili

### 2.2 Coesistenza dei Binari

Un singolo pacchetto usa entrambi i binari contemporaneamente. La separazione avviene a livello di singolo file, non di pacchetto. Esempio concreto con `scf-master-codecrafter`:

```
scf-master-codecrafter
├── MCP Service Mode (Binario 1)
│   ├── agents://code-Agent-Analyze
│   ├── agents://code-Agent-Code
│   ├── agents://code-Agent-CodeRouter
│   ├── ... (8 agenti rimanenti)
│   ├── skills://clean-architecture
│   ├── skills://code-routing
│   ├── skills://docs-manager
│   └── instructions://mcp-context
│
└── Plugin Mode (Binario 2)
    ├── .github/copilot-instructions.md   [editor-binding, merge_sections]
    └── .github/instructions/mcp-context.instructions.md  [editor-binding, replace]
```

---

## 3. Specifiche Tecniche della Modifica

### 3.1 Aggiornamento Schema Manifest — v3.0 → v3.1

La modifica al manifest è chirurgica: si aggiunge un campo `plugin_files` a livello root, in parallelo all'esistente `workspace_files`.

**Schema v3.0 attuale:**

```json
{
  "workspace_files": [
    ".github/copilot-instructions.md",
    ".github/instructions/mcp-context.instructions.md"
  ]
}
```

**Schema v3.1 proposto:**

```json
{
  "workspace_files": [
    ".github/copilot-instructions.md",
    ".github/instructions/mcp-context.instructions.md"
  ],
  "plugin_files": []
}
```

**Semantica dei due campi:**

- `workspace_files` — invariato. Continua a elencare i file editor-binding che devono essere scritti nel workspace. Compatibilità retro garantita: i manifest v3.0 che non dichiarano `plugin_files` funzionano senza modifiche.
- `plugin_files` — nuovo. Elenca i file che il manutentore del pacchetto intende distribuire come plugin fisici nel workspace anche se non sono strettamente editor-binding. Può includere changelog, profili, reference, workflow CI/CD.

**Nota:** `notify-engine.yml` di `scf-pycode-crafter` andrebbe spostato da `workspace_files` a `plugin_files` aggiornando il manifest di quel pacchetto a v3.1. La differenza semantica è che `workspace_files` è riservato ai file obbligatori per il funzionamento dell'editor, mentre `plugin_files` include tutto il resto che deve essere fisico nel workspace.

### 3.2 Aggiornamento `package-manifest.json` — scf-master-codecrafter

```json
{
  "schema_version": "3.1",
  "workspace_files": [
    ".github/copilot-instructions.md",
    ".github/instructions/mcp-context.instructions.md"
  ],
  "plugin_files": []
}
```

Nessuna variazione funzionale per questo pacchetto — `plugin_files` vuoto equivale al comportamento attuale.

### 3.3 Aggiornamento `package-manifest.json` — scf-pycode-crafter

```json
{
  "schema_version": "3.1",
  "workspace_files": [
    ".github/copilot-instructions.md",
    ".github/instructions/python.instructions.md",
    ".github/instructions/tests.instructions.md"
  ],
  "plugin_files": [
    ".github/workflows/notify-engine.yml",
    ".github/python.profile.md",
    ".github/skills/error-recovery/reference/errors-python.md"
  ]
}
```

In questo caso la modifica è sostanziale: il workflow e i file di profilo/reference vengono dichiarati esplicitamente come plugin, separandoli dagli editor-binding puri.

### 3.4 Modifica al Codice Engine — File Coinvolti

La modifica al codice dell'engine è localizzata in tre punti. Il principio è non riscrivere la logica esistente, ma estenderla per leggere il nuovo campo.

**Punto 1 — `lifecycle.py`, funzione `_install_standalone_files_v3`**

Attualmente questa funzione legge i file da `deployment_modes.standalone_files`. Deve essere estesa per leggere anche da `plugin_files` del manifest, iterando sulla lista e chiamando `WorkspaceWriteGateway.write_file()` per ciascun file, con la stessa logica di protezione dei file utente già implementata.

Pseudocodice della modifica (snippet da integrare nella funzione esistente):

```python
# Legge plugin_files dal manifest, default lista vuota per compatibilità v3.0
plugin_files = manifest.get("plugin_files", [])

for file_path in plugin_files:
    # Recupera metadata dal files_metadata per strategia di merge e priorità
    file_meta = _get_file_metadata(manifest, file_path)
    # Delega alla WriteGateway già esistente — nessuna logica nuova
    result = workspace_write_gateway.write_file(
        path=file_path,
        source=store_path / file_path,
        merge_strategy=file_meta.get("scf_merge_strategy", "replace"),
        merge_priority=file_meta.get("scf_merge_priority", 10),
        protected=file_meta.get("scf_protected", False)
    )
    # Logging su stderr — mai su stdout
    print(f"[SPARK-ENGINE][INFO] Plugin file written: {file_path}", file=sys.stderr)
```

**Punto 2 — `tools_packages_install.py`, formatter del response**

Il response di `scf_install_package` deve distinguere le due categorie. Modifica al formatter del risultato:

```python
# Struttura response attuale (da sostituire)
# "installed": [lista_file]

# Struttura response proposta
{
    "package": package_id,
    "version": version,
    "mcp_services_activated": [lista_uri_mcp],        # Binario 1
    "workspace_files_written": [lista_editor_binding], # Binario 2 - workspace_files
    "plugin_files_installed": [lista_plugin],           # Binario 2 - plugin_files
    "status": "success"
}
```

**Punto 3 — `schemas/package-manifest.schema.json`**

Aggiungere `plugin_files` alla definizione formale dello schema JSON:

```json
"plugin_files": {
  "type": "array",
  "items": { "type": "string" },
  "default": [],
  "description": "File fisici da installare nel workspace come plugin. Non editor-binding. Gestiti da WorkspaceWriteGateway."
}
```

---

## 4. Analisi dei Rischi e Mitigazioni

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Manifest v3.0 esistenti smettono di funzionare | Bassa | Alto | `plugin_files` ha default `[]` — compatibilità retro garantita |
| `notify-engine.yml` rimosso da `workspace_files` rompe workflow esistenti | Media | Medio | Aggiornare manifest pycode-crafter contestualmente alla patch engine |
| Duplicazione logica tra `workspace_files` e `plugin_files` | Alta | Basso | Documentare chiaramente la semantica distinta nel README schema |
| Utente non capisce la differenza tra i due campi | Media | Basso | Response `scf_install_package` aggiornato rende la distinzione visibile |

---

## 5. Compatibilità e Migrazione

### 5.1 Backward Compatibility

La modifica è pienamente compatibile con i manifest schema v3.0 esistenti. La regola è: se `plugin_files` è assente, il sistema si comporta esattamente come oggi. Nessun pacchetto esistente richiede aggiornamento obbligatorio per continuare a funzionare.

### 5.2 Percorso di Migrazione Raccomandato

La migrazione è volontaria e graduale:

1. **Step 1 — Engine patch**: implementare le modifiche ai tre file elencati in §3.4. Nessuna modifica ai manifest dei pacchetti.
2. **Step 2 — Aggiornamento pycode-crafter**: spostare `notify-engine.yml`, `python.profile.md` e `errors-python.md` in `plugin_files`. Bumping manifest a schema_version 3.1.
3. **Step 3 — Aggiornamento master-codecrafter**: schema_version 3.1, `plugin_files: []`. Sostanzialmente cosmetico, serve a dichiarare la conformità allo schema nuovo.
4. **Step 4 — Aggiornamento spark-base**: analisi separata, fuori scope di questa proposta.

---

## 6. Benefici Attesi

**Per l'utente finale:**

- Comprensione immediata di cosa viene installato: strumenti MCP vs file nel progetto
- Separazione netta tra risorse di sistema (non modificare) e plugin di progetto (personalizzabili)
- Workspace git-committable senza dipendenze oscure dall'engine

**Per il manutentore dei pacchetti (Nemex81):**

- Controllo granulare sulla delivery di ogni file senza hack su `deployment_modes`
- Schema auto-documentante — il manifest dichiara esplicitamente l'intenzione di ogni file
- Base solida per future funzionalità: flag `--plugin-only`, `--mcp-only` in `scf_install_package`

**Per l'engine:**

- Riduzione dell'ambiguità logica interna — ogni percorso di scrittura ha una sorgente dichiarata
- Logging più preciso e diagnostica migliorata
- Percorso naturale verso l'ottimizzazione delle risorse MCP pure (zero-footprint workspace)

---

## 7. Istruzioni per Copilot — Task di Implementazione

Questa sezione è indirizzata a GitHub Copilot come istruzioni operative per l'implementazione.

### Prerequisiti

- Repository: `spark-framework-engine`
- Branch di lavoro: creare `feature/dual-mode-manifest-v3.1` da `main`
- Dipendenze: nessuna libreria esterna aggiuntiva

### Task 1 — Aggiornamento Schema JSON

**File:** `schemas/package-manifest.schema.json` (verificare path esatto nel repo)

Aggiungere il campo `plugin_files` alla definizione delle proprietà root:

```json
"plugin_files": {
  "type": "array",
  "items": { "type": "string" },
  "default": [],
  "description": "File fisici da installare nel workspace come plugin. Distinti da workspace_files (editor-binding). Gestiti da WorkspaceWriteGateway con le stesse regole di protezione."
}
```

### Task 2 — Estensione `_install_standalone_files_v3` in `lifecycle.py`

**File:** localizzare la funzione `_install_standalone_files_v3` in `lifecycle.py`.

Dopo l'iterazione esistente su `deployment_modes.standalone_files`, aggiungere un blocco che:

1. Legge `manifest.get("plugin_files", [])` — default lista vuota per retro-compatibilità
2. Per ogni path nella lista, recupera i metadata da `files_metadata`
3. Chiama `WorkspaceWriteGateway.write_file()` con la stessa firma già usata per `workspace_files`
4. Logga ogni operazione su `sys.stderr` con formato `[SPARK-ENGINE][INFO] plugin_file written: {path}`
5. Aggiunge i path scritti alla struttura di risultato sotto la chiave `plugin_files_installed`

**CRITICO:** Non usare mai `print()` su `stdout`. Solo `sys.stderr`.

### Task 3 — Aggiornamento Response Formatter in `tools_packages_install.py`

**File:** localizzare il tool `scf_install_package` e il suo formatter di risposta.

Sostituire la chiave `"installed"` con la struttura tripartita:

- `"mcp_services_activated"` — lista degli URI MCP attivati (`agents://...`, `skills://...`, etc.)
- `"workspace_files_written"` — lista dei file scritti da `workspace_files`
- `"plugin_files_installed"` — lista dei file scritti da `plugin_files`

Mantenere la chiave `"installed"` come alias deprecato (lista unificata dei due) per eventuali client che la leggono, con un campo `"_deprecated_note": "Use workspace_files_written and plugin_files_installed instead"`.

### Task 4 — Aggiornamento Manifest `scf-pycode-crafter`

**Repository:** `scf-pycode-crafter`  
**File:** `package-manifest.json`

Modifiche:

- `schema_version`: `"3.0"` → `"3.1"`
- Aggiungere campo `plugin_files` con i seguenti path:
  - `.github/workflows/notify-engine.yml`
  - `.github/python.profile.md`
  - `.github/skills/error-recovery/reference/errors-python.md`
- Verificare che `workspace_files` contenga solo i file editor-binding stretti

### Task 5 — Aggiornamento Manifest `scf-master-codecrafter`

**Repository:** `scf-master-codecrafter`  
**File:** `package-manifest.json`

Modifiche:

- `schema_version`: `"3.0"` → `"3.1"`
- Aggiungere campo `plugin_files: []` (lista vuota — nessuna variazione funzionale, solo dichiarazione di conformità allo schema 3.1)

### Criteri di Accettazione

- [ ] Schema JSON aggiornato con `plugin_files`, campo opzionale con default `[]`
- [ ] `_install_standalone_files_v3` elabora correttamente `plugin_files` senza rompere il comportamento su `workspace_files`
- [ ] Manifest v3.0 (senza `plugin_files`) continuano a funzionare senza errori
- [ ] Response di `scf_install_package` distingue le tre categorie
- [ ] Logging esclusivamente su `sys.stderr`
- [ ] Nessuna eccezione Python non gestita propagata su `stdout`
- [ ] Manifest di `scf-pycode-crafter` e `scf-master-codecrafter` aggiornati a schema_version 3.1
- [ ] Nessun regression test fallisce sui pacchetti esistenti

---

## 8. Conclusione

La proposta Dual-Mode non ridisegna l'architettura SPARK — la rende esplicita. Il sistema ha già la distinzione tra risorse MCP e file workspace incorporata nella logica di `_install_workspace_files_v3` e `_install_mcp_resources_v3`. Ciò che manca è la dichiarazione formale di questa distinzione nello schema del manifest e la sua visibilità nel response dei tool.

Il costo implementativo è stimato in 3-4 ore di lavoro Copilot su file di dimensione contenuta. Il guadagno è strutturale: uno schema manifest auto-documentante, un sistema di installazione che comunica chiaramente all'utente cosa sta ricevendo, e una base solida per tutte le evoluzioni future del Plugin Manager senza refactoring additivi.

**Approvazione richiesta da:** Luca / Nemex81  
**Prima dell'implementazione da parte di:** GitHub Copilot  

---

*Documento generato da Perplexity AI nel ruolo di Coordinatore del Consiglio SPARK.*  
*Versione 1.0 — 2026-05-08*
