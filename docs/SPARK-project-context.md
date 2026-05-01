# SPARK MCP Server — Documento di Contesto di Progetto
> Versione: 1.1 — Data: 2026-05-01
> Autore: Luca (alias: Zio / Nemex81)
> Scopo: documento di handoff per riprendere il lavoro in nuove sessioni AI.
>        Contiene l'architettura completa, i problemi aperti e il lavoro recente.

---

## 1. Cos'è SPARK

**SPARK** (Server Protocol for Agentic Resource Knowledge) è un server MCP (Model Context Protocol)
scritto in Python 3.10+, costruito sopra la libreria **FastMCP**, comunicante via trasporto **stdio**.

L'obiettivo fondamentale è trasformare la cartella `.github/` di qualsiasi progetto VS Code in una
**base di conoscenza dinamica**, accessibile da Copilot Agent Mode (e qualsiasi client MCP), che
espone agenti, skill, prompt e istruzioni in modo strutturato e versionato tramite URI schema
proprietari:

- `agents://` — agenti Copilot (.agent.md)
- `skills://` — skill riutilizzabili (SKILL.md / .skill.md)
- `prompts://` — template di prompt (.prompt.md)
- `instructions://` — istruzioni contestuali (.instructions.md)
- `scf://` — singleton di stato engine (scf://status, scf://version, etc.)

Il server gira **in locale** come processo separato. Non esiste componente cloud.
Non usa `print()` su stdout (corromperebbe il canale JSON-RPC). Tutto il logging va su stderr.

---

## 2. Origini e Idea Iniziale

Il progetto nasce dalla necessità pratica di un programmatore non vedente (Windows 11 con NVDA)
di avere un sistema di orchestrazione AI che:

1. Fosse **navigabile interamente da tastiera**, compatibile con screen reader (NVDA, JAWS, VoiceOver)
2. Permettesse di gestire **contesti diversi tra progetti diversi** senza configurazione manuale
3. Centralizzasse le "istruzioni di comportamento" per Copilot in un unico posto,
   versionato con Git e portabile tra macchine

L'idea iniziale era semplice: un server MCP che leggesse i `.md` da `.github/` e li esponesse
come risorse. Struttura piatta, nessun pacchetto, nessun registry, nessuna versione.

---

## 3. Evoluzione Naturale

### Fase 1 — Server monolitico (pre-v2.x)

Un singolo file Python che scansionava `.github/` e rispondeva a chiamate MCP.
I file venivano copiati manualmente nel workspace. Nessuna gestione versioni.

### Fase 2 — Introduzione dei pacchetti (v2.x)

Nasce il concetto di **pacchetto SCF** (SPARK Code Framework): un repository GitHub con struttura
`.github/` definita e un `package-manifest.json`. Il bootstrap copiava i file del pacchetto nel
workspace. Problemi: idempotenza fragile, conflitti di merge tra versioni, stato di runtime
mescolato con le risorse di configurazione.

### Fase 3 — Registry, store centralizzato e lifecycle v3 (v3.x, attuale)

Componenti introdotti:

- `scf-registry`: registro JSON centralizzato dei pacchetti disponibili su GitHub
- `PackageResourceStore`: store in `engine_dir/packages/{pkg_id}/` — i pacchetti non vengono
  più copiati nel workspace, risiedono nell'engine e vengono serviti via MCP
- `McpResourceRegistry`: indice in-memory URI→path con priorità override>engine>package
- `ManifestManager`: tracciamento SHA-256 per rilevare modifiche utente
- `MergeEngine`: 3-way merge testuale con marker `<<<<<<< YOURS / >>>>>>> OFFICIAL`
- `WorkspaceLocator`: risoluzione workspace a cascata (argv → env → CWD scan)

In questa fase il sistema ha acquisito solidità strutturale ma ha sviluppato una
**tensione architetturale non risolta**: le risorse non sanno con certezza se devono
vivere nel filesystem del workspace o essere servite via MCP (modello push vs pull).

---

## 4. Repository del Sistema

### 4.1 spark-framework-engine — Motore MCP

- **Repo**: <https://github.com/Nemex81/spark-framework-engine>
- **Versione**: 3.1.0
- **File chiave**:
  - Engine principale: <https://github.com/Nemex81/spark-framework-engine/blob/main/spark-framework-engine.py>
  - Init/setup wizard: <https://github.com/Nemex81/spark-framework-engine/blob/main/spark-init.py>
  - Manifest engine: <https://github.com/Nemex81/spark-framework-engine/blob/main/engine-manifest.json>
  - Config MCP esempio: <https://github.com/Nemex81/spark-framework-engine/blob/main/mcp-config-example.json>
  - CLAUDE.md (già presente): <https://github.com/Nemex81/spark-framework-engine/blob/main/CLAUDE.md>
  - CHANGELOG: <https://github.com/Nemex81/spark-framework-engine/blob/main/CHANGELOG.md>
  - README: <https://github.com/Nemex81/spark-framework-engine/blob/main/README.md>
  - Setup Windows (PowerShell): <https://github.com/Nemex81/spark-framework-engine/blob/main/setup.ps1>
  - Setup Unix (bash): <https://github.com/Nemex81/spark-framework-engine/blob/main/setup.sh>
  - Directory pacchetti store: <https://github.com/Nemex81/spark-framework-engine/tree/main/packages>
  - Directory test: <https://github.com/Nemex81/spark-framework-engine/tree/main/tests>
  - Docs: <https://github.com/Nemex81/spark-framework-engine/tree/main/docs>
- **Classi core** (tutte in spark-framework-engine.py):
  - `WorkspaceLocator` — risoluzione workspace
  - `FrameworkInventory` — discovery .github/
  - `ManifestManager` — SHA-256, tracking modifiche utente
  - `McpResourceRegistry` — indice in-memory risorse MCP (URI→path)
  - `PackageResourceStore` — store centralizzato pacchetti v3
  - `RegistryClient` — fetch registry con cache locale e timeout 5s
  - `MergeEngine` — 3-way merge testuale
  - `SparkFrameworkEngine` — classe principale, espone i tool MCP
- **Agenti engine-managed** (solo MCP, non nel workspace):
  - spark-assistant, spark-engine-maintainer, spark-guide, spark-welcome
- **Istruzioni che atterrano fisicamente nel workspace** (via bootstrap):
  - `.github/instructions/framework-guard.instructions.md`
  - `.github/instructions/personality.instructions.md`
  - `.github/instructions/verbosity.instructions.md`
  - `.github/instructions/workflow-standard.instructions.md`
  - `.github/instructions/git-policy.instructions.md`
  - `.github/instructions/model-policy.instructions.md`
- **Tool MCP implementati**: ~27, tool 28 (`scf_bootstrap_workspace`) in sviluppo
- **Sentinella bootstrap**: `.github/agents/spark-assistant.agent.md`

### 4.2 scf-registry — Registro pacchetti

- **Repo**: <https://github.com/Nemex81/scf-registry>
- **File principale**: <https://github.com/Nemex81/scf-registry/blob/main/registry.json>
- **Schema**: 2.0
- **Pacchetti registrati**: 3 (tutti status: stable, min_engine_version: 3.1.0)

### 4.3 spark-base — Layer fondazionale

- **Repo**: <https://github.com/Nemex81/spark-base>
- **Versione**: 1.6.1
- **Manifest**: <https://github.com/Nemex81/spark-base/blob/main/package-manifest.json>
- **Contenuto .github/**: agenti base (Agent-Orchestrator, Agent-Git, Agent-Analyze,
  Agent-Welcome, Agent-Docs, Agent-Helper, spark-assistant, spark-guide),
  prompts, skills e instructions general-purpose
- **Prerequisito di**: scf-master-codecrafter

### 4.4 scf-master-codecrafter — Plugin core CORE-CRAFT

- **Repo**: <https://github.com/Nemex81/scf-master-codecrafter>
- **Versione**: 2.4.1
- **Manifest**: <https://github.com/Nemex81/scf-master-codecrafter/blob/main/package-manifest.json>
- **Contenuto**: design, code routing, code UI, contesto MCP
- **Dipende da**: spark-base
- **Problema noto**: directory `runtime/` dentro `.github/` contiene stato di runtime
  (snapshot, merge-sessions, backups, orchestrator-state.json)

### 4.5 scf-pycode-crafter — Plugin Python

- **Repo**: <https://github.com/Nemex81/scf-pycode-crafter>
- **Versione**: 2.2.1
- **Manifest**: <https://github.com/Nemex81/scf-pycode-crafter/blob/main/package-manifest.json>
- **Contenuto**: agenti, skill e instruction specializzate per sviluppo Python con Copilot Agent mode

---

## 5. Problemi Critici Aperti (identificati 2026-05-01)

### P1 — Bug di tipo in `_install_package_v3_into_store` (BLOCCANTE)

Il metodo di classe chiama `RegistryClient.fetch_raw_file` su un'istanza di `McpResourceRegistry`
invece che su un `RegistryClient`. Lancia `AttributeError` silenzioso al runtime.
La funzione standalone omonima fuori dalla classe è corretta; il metodo di classe è un
duplicato difettoso non allineato al refactoring.

### P2 — Boot registry non sequenziato (CAUSA PRINCIPALE distribuzione risorse)

`populate_mcp_registry()` riceve i `package_manifests` come parametro ma non è chiaro
il punto di boot che carica tutti i `package-manifest.json` dallo store PRIMA di chiamarla.
Al boot a freddo, il registry risulta vuoto finché non si esegue un'operazione di installazione.
Questo spiega i problemi di distribuzione risorse segnalati dall'utente.

### P3 — `spark-welcome` orfano nel manifest engine (MEDIA)

`engine-manifest.json` dichiara `spark-welcome` come agente engine-managed,
ma `spark-welcome.agent.md` non è verificabile nel repo.
`scf_get_agent("spark-welcome")` restituisce `None` silenzioso.

### P4 — SHA-256 mancanti per workspace_files engine (MEDIA)

I `files_metadata` in `engine-manifest.json` non hanno campo `sha256`.
`ManifestManager.verify_integrity()` non può rilevare modifiche utente
a questi file specifici.

### P5 — Tool 28 `scf_bootstrap_workspace` incompleto (BASSA-MEDIA)

La logica Phase 6 genera `AGENTS-{plugin}.md` separati invece di consolidare
in `AGENTS.md` con marker SCF, in contrasto con la strategia Gateway Pattern.

### P6 — `runtime/` in `.github/` (ARCHITETTURALE)

Snapshot, merge-sessions, backups e `orchestrator-state.json` risiedono sotto
`.github/runtime/`. Stato di runtime che dovrebbe stare in `engine_dir/cache/`
o nella cache utente, non nella cartella di configurazione del workspace.

---

## 6. Strategia di Refactoring: Gateway Pattern a Tre Layer

Elaborata nelle sessioni del 2026-04-30 e 2026-05-01.

Il principio fondamentale: modello **push** (bootstrap copia risorse nel workspace)
→ modello **pull** (gateway in `.github/` chiede all'MCP le risorse che servono).

### Layer 0 — Presenza fisica minima in `.github/`

Regola di ammissione: se una risorsa può essere recuperata via MCP, non sta qui.

File ammessi nel workspace fisico:

- `.github/copilot-instructions.md` — entry point Copilot Agent Mode
  (identità progetto, come avviare MCP, URI schema. Solo puntatori, zero logica)
- `.github/agents/spark-assistant.agent.md` — sentinella bootstrap (idempotenza)
- `.github/agents/spark-guide.agent.md` — gateway agent, interroga MCP per il resto
- `.github/instructions/` — le 6 instruction engine (devono funzionare anche senza MCP)

### Layer 1 — Store MCP (repository di conoscenza)

L'engine serve via MCP, su richiesta, qualunque risorsa dei pacchetti installati.
Gli agenti del Layer 0 fanno richieste esplicite usando gli URI schema definiti.

### Layer 2 — Pacchetti opzionali via registry

Installazione tramite `scf_install_package`. Ogni pacchetto aggiunge capacità al Layer 1.
Il Layer 0 non cambia al variare dei pacchetti installati.

### `CLAUDE.md` in radice

Il file esiste già in spark-framework-engine (vedi link sopra).
Va valutato e aggiornato in linea con la strategia Gateway Pattern.
Struttura corretta: manifest di connessione (come avviare MCP, URI schema, dove trovare
le risorse), NON un duplicato di `copilot-instructions.md`.
I due file servono pubblici diversi (Claude vs Copilot) con lo stesso endpoint MCP.

---

## 7. Tabella Valutazione Solidità / Efficacia

| Area | Solidità | Efficacia | Criticità |
|---|---|---|---|
| Motore classi core | alta | alta | Bug P1 latente |
| Registry JSON | alta | alta | Nessuna |
| engine-manifest.json | alta | media | P3 orfano, P4 SHA mancanti |
| Agenti gateway | alta | media | Tool names non validati vs codice |
| Bootstrap workspace | media | bassa-media | Tool 28 incompleto, Phase 6 da allineare |
| Distribuzione risorse MCP | media | bassa-media | P2 boot non sequenziato |
| runtime/ in .github | bassa | bassa | P6 architetturale |

---

## 8. Lavoro delle Ultime Sessioni

### 2026-04-30

- Analisi architetturale completa di tutti e 5 i repository
- Identificazione della tensione architetturale push vs pull delle risorse
- Elaborazione della strategia Gateway Pattern a tre layer
- Proposta `CLAUDE.md` (poi scoperto che esiste già nell'engine)
- Identificazione problema `runtime/` in `.github/`

### 2026-05-01 (sessione 1:09–1:31 AM CEST)

- Analisi di solidità e efficacia punto per punto su tutti i componenti
- Identificazione P1: bug di tipo in `_install_package_v3_into_store`
- Identificazione P2: boot registry non sequenziato come causa principale distribuzione risorse
- Identificazione P3: `spark-welcome` orfano in engine-manifest
- Identificazione P4: SHA-256 mancanti per workspace_files
- Scoperta struttura completa repo engine: `CLAUDE.md`, `packages/`, `tests/`, `docs/`, `scripts/`
- Valutazione tabellare per area
- Generazione di questo documento di handoff

---

## 9. Priorità di Intervento (ordine)

1. **P1** — Fix chirurgico nel metodo `_install_package_v3_into_store` nella classe
   `SparkFrameworkEngine` — allineare al `RegistryClient` come fa la funzione standalone
2. **P2** — Identificare e correggere la sequenza di boot che carica i `package-manifest.json`
   installati dallo store e li passa a `populate_mcp_registry` prima di esporre i tool
3. **P5** — Implementare tool 28 `scf_bootstrap_workspace` secondo il Gateway Pattern:
   Layer 0 minimo (2 agenti gateway + 6 instruction), nessun `AGENTS-{plugin}.md` ridondante
4. **P6** — Spostare `runtime/` da `.github/` a `engine_dir/cache/` o cartella utente
5. **P3** — Verificare o creare `spark-welcome.agent.md` nel repo engine
6. **P4** — Popolare SHA-256 in `engine-manifest.json` per i workspace_files

---

*Fine documento — generato dalla sessione di analisi SPARK 2026-05-01*
