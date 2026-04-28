# SPARK Framework — Design Document v1.2
# Refactoring verso Architettura Dual-Client (Copilot + Cline/Roo)
#
# Stato: VERIFICATO E CORRETTO — include protezione risorse, migrazione v2→v3, onboarding e cold start
# Autore: Nemex81
# Versione target engine: 3.0.0
# Changelog v1.2.1 (2026-04-28, validazione automatica):
#   - D1 fix: tool count reale = 35 (engine v2.4.0); nuovi tool v3.0 = 5;
#     totale post-refactor = 40. scf_update_profile RIMOSSO dallo scope v3.0
#     (rimandato a v3.1 con onboarding evolution).
#   - D2 fix: engine-manifest.json dichiarato come deliverable obbligatorio
#     della Fase 1 (creazione + caricamento da EngineInventory).
#   - D3 fix: instruction engine sono 9 (non 8). Classificazione:
#     6 workspace (framework-guard, personality, verbosity, workflow-standard,
#     git-policy, model-policy) + 3 MCP (spark-assistant-guide,
#     spark-engine-maintenance, project-reset).
#   - D4 fix: spark-welcome creato come deliverable Fase 1
#     (agente engine-proprio, file .github/agents/spark-welcome.agent.md).
#   - W3 fix: schema URI unificato. engine-skills:// e engine-instructions://
#     mantenuti come ALIAS retrocompatibili che redirigono a skills:// e
#     instructions://. La distinzione engine-vs-pacchetto è in McpResourceRegistry,
#     non nello schema URI.
# Changelog v1.2:
#   - Sezione 3.1: note project-profile.md + agente spark-welcome
#   - Sezione 16: Garanzia contesto cold start (Copilot e Cline)
# Changelog v1.1:
#   - Sezione 13: Protezione risorse MCP — policy di modifica con workspace override
#   - Sezione 14: Migrazione workspace esistente v2.x → v3.0 (tool scf_migrate_workspace)
#   - Aggiornamento sezione 10 (fasi) con Fase 0 e Fase 8 (migrazione)

---

# 1. Contesto e Obiettivo

SPARK (Server Protocol for Agentic Resource Knowledge) è un framework MCP
(Model Context Protocol) FastMCP che potenzia gli agenti AI in VS Code
esponendo risorse strutturate — agenti, prompt, skill, istruzioni — ai client
collegati via stdio JSON-RPC.

Il trigger di questo refactoring è duplice:
- Il cambio billing GitHub Copilot (AI Credits dal 1 giugno 2026) rende
  necessaria una stack alternativa BYOK (Cline/Roo Code + OpenRouter).
- L'attuale architettura è accoppiata a Copilot come unico client:
  i file dei pacchetti vengono copiati fisicamente nel workspace utente
  (filesystem-push), e Cline/Roo non ha un meccanismo equivalente.

Obiettivo: rendere SPARK client-agnostico mantenendo piena compatibilità
con Copilot e aggiungendo supporto nativo per Cline/Roo Code via MCP pull.


# 2. Principio Architetturale

    SOURCE OF TRUTH CENTRALIZZATA NELL'ENGINE
    Proiezioni client-specifiche on-demand

I file dei pacchetti (agents, prompts, skills, instructions) vivono
una volta sola nella cartella dell'engine installato.

- Copilot riceve una proiezione filesystem-push MINIMA nel workspace:
  solo i file che carica automaticamente all'avvio sessione.
- Cline/Roo riceve tutto via MCP pull on-demand, senza file nel workspace.
- Nessuna duplicazione. Nessuna sincronizzazione da mantenere.
- Le risorse MCP sono IN SOLA LETTURA per default. La modifica segue
  il protocollo workspace-override (vedi sezione 13).


# 3. Classificazione dei File nel Workspace Utente

Criterio: un file sta nel workspace solo se il client lo carica
AUTOMATICAMENTE senza intervento utente, O se è stato scritto dall'utente.

## 3.1 File OBBLIGATORI nel workspace (rimangono)

  .github/
  ├── copilot-instructions.md         [generato da SPARK, merge_sections]
  ├── project-profile.md              [scritto dall'utente, mai toccato da SPARK]
  ├── AGENTS.md                       [generato dinamicamente da SPARK al bootstrap]
  ├── instructions/                   [copiati da workspace_files dei pacchetti]
  │   └── *.instructions.md
  ├── runtime/
  │   └── orchestrator-state.json     [stato sessione, locale per definizione]
  └── .scf-manifest.json              [stato installazione workspace]

Note critiche:
- AGENTS.md NON è più copiato dal pacchetto (rimozione da workspace_files).
  L'engine lo GENERA dinamicamente da McpResourceRegistry al bootstrap
  e lo aggiorna ad ogni install/remove pacchetto.
- AGENTS-{plugin}.md idem: generati dall'engine, non copiati.

## 3.1 Note su project-profile.md e flusso di inizializzazione

project-profile.md è l'unico file nel workspace che SPARK non genera
autonomamente e non modifica mai. Contiene il contesto specifico del
progetto utente: nome, stack, obiettivi, convenzioni locali.

SPARK scrive un TEMPLATE vuoto durante il bootstrap SE il file non esiste.
Da quel momento il file appartiene all'utente.

### Agente spark-welcome (responsabile dell'inizializzazione)

spark-welcome è un agente dedicato all'onboarding del workspace.
Si attiva tipicamente al primo bootstrap o su richiesta esplicita.

Responsabilità:
- Guida l'utente nella compilazione interattiva di project-profile.md
  tramite domande in chat (nome progetto, linguaggi, convenzioni, obiettivi)
- Aggiorna project-profile.md con i dati raccolti via tool MCP
  (unico caso in cui SPARK scrive su un file "utente": esplicita delegazione)
- Aggiorna copilot-instructions.md con la sezione SCF:BEGIN/PROJECT-PROFILE/END
  estraendo il sommario da project-profile.md
- Genera .clinerules con il contesto progetto se assente
- Verifica che i pacchetti necessari siano installati e suggerisce
  scf_install se mancano dipendenze dichiarate nel profilo

spark-welcome è dichiarato in engine-manifest.json come risorsa engine-propria:
  "mcp_resources": {
    "agents": ["spark-assistant", "spark-engine-maintainer",
               "spark-guide", "spark-welcome"],
    ...
  }

Flusso tipico primo avvio su workspace vergine:
  1. scf_bootstrap_workspace → crea template project-profile.md + workspace minimo
  2. Agente spark-welcome attivato (da Copilot: AGENTS.md lo indica come
     "primo passo consigliato"; da Cline: .clinerules lo menziona)
  3. spark-welcome compila project-profile.md via dialogo in chat
  4. spark-welcome aggiorna copilot-instructions.md e .clinerules
  5. Sistema operativo — sessioni successive non richiedono questo flusso

INVARIANTE: spark-welcome modifica project-profile.md SOLO durante
l'onboarding esplicito (primo avvio o reset esplicito dall'utente).
Non lo tocca mai durante le sessioni ordinarie di lavoro.

## 3.3 File che MIGRANO nell'engine (non più nel workspace)

  Da scf-master-codecrafter:
  - .github/agents/code-Agent-*.md       → agents://code-Agent-*
  - .github/prompts/*.prompt.md          → /mcp.spark-engine.*
  - .github/skills/*.skill.md            → skills://*
  - .github/changelogs/                  → non esposti via MCP (interni)
  - .github/prompts/README.md            → non esposto

## 3.4 File SPOSTATI fuori dal workspace

  .scf-registry-cache.json
  → engine_dir/cache/registry-cache.json
     oppure %APPDATA%\spark-engine\cache\registry-cache.json (Windows)
  Gestito da WorkspaceLocator.get_engine_cache_dir()

## 3.5 Instruction files dell'engine stesso

L'engine ha 9 instruction proprie in .github/instructions/ che NON
appartengono a nessun pacchetto. Classificazione per destinazione:

Nel workspace (glob automatico Copilot, 6 file):
  framework-guard, personality, verbosity, workflow-standard,
  git-policy, model-policy

Via MCP Resource (task-specific o agente-specifiche, 3 file):
  spark-assistant-guide, spark-engine-maintenance, project-reset

Le instruction nel workspace sono dichiarate nel manifest interno
dell'engine (engine-manifest.json, vedi sezione 5.4).


# 4. Aggiornamento Schema package-manifest.json — v2.1 → v3.0

## 4.1 Principio di migrazione

Lo schema v3.0 è ADDITIVO. Tutti i campi v2.1 rimangono per retrocompatibilità.
Engine v3.x legge manifest v2.1 senza errori (fallback su campo 'files').

## 4.2 Nuovi campi v3.0

  "schema_version": "3.0",

  "workspace_files": [
    ".github/copilot-instructions.md",
    ".github/instructions/mcp-context.instructions.md"
  ],
  // file da copiare fisicamente nel workspace al bootstrap/install
  // AGENTS*.md escluso: generato dinamicamente dall'engine

  "mcp_resources": {
    "agents":   ["code-Agent-Code", "code-Agent-Design",
                 "code-Agent-CodeRouter", "code-Agent-CodeUI"],
    "prompts":  ["framework-release", "framework-update",
                 "git-commit", "git-merge", "help",
                 "framework-unlock", "package-update"],
    "skills":   ["clean-architecture", "code-routing", "docs-manager"]
  },
  // risorse servite via MCP dall'engine — nomi senza estensione

## 4.3 Deprecazione engine_provided_skills

Il campo engine_provided_skills (v2.1) è DEPRECATO in v3.0.
I suoi valori migrano in mcp_resources.skills.
Engine v3.x: se trova engine_provided_skills e mcp_resources.skills
è assente, usa engine_provided_skills come fallback e logga warning:
  [SPARK-ENGINE][WARN] manifest v2.1: engine_provided_skills
  usato come fallback per mcp_resources.skills

## 4.4 Gestione files_metadata[]

files_metadata rimane nel manifest v3.0 con semantica biforcata:
- file in workspace_files: usato per merge_strategy e ownership nel workspace
- file in mcp_resources: usato dall'engine per integrità del deposito
  centralizzato (SHA-256, version tracking) — non rilevante per il workspace

Nessun campo viene rimosso. L'engine distingue il contesto d'uso
in base alla lista di appartenenza del file.


# 5. Nuovi Componenti dell'Engine

## 5.1 PackageResourceStore (nuova classe)

Responsabilità:
- Gestisce il deposito centralizzato dei file di pacchetto nell'engine
- Risolve path fisici: package_id + tipo + nome → Path assoluto
- Path base: engine_dir/packages/{package_id}/.github/{tipo}/

Metodi principali:
  resolve(package_id, resource_type, name) -> Path
  list_resources(package_id, resource_type) -> list[str]
  verify_integrity(package_id) -> dict  # SHA-256 check
  has_workspace_override(workspace, resource_type, name) -> bool

## 5.2 McpResourceRegistry (nuova classe)

Responsabilità:
- Indice in memoria URI → (path_engine, path_override_opt) per tutte le risorse
- Popolata al boot da FrameworkInventory (engine-manifest + pacchetti installati)
- Risoluzione con priorità: workspace-override > engine-store

Struttura interna:
  {
    "agents://code-Agent-Code": {
      "engine": Path(...),
      "override": Path(...) | None   # presente se utente ha una versione locale
    },
    ...
  }

Metodi principali:
  register(uri, engine_path)
  register_override(uri, override_path)
  resolve(uri) -> Path          # ritorna override se esiste, altrimenti engine
  resolve_engine(uri) -> Path   # ritorna sempre la versione canonica engine
  list_by_type(resource_type) -> list[str]
  has_override(uri) -> bool

## 5.3 Nuovi Tool MCP

scf_list_resources(resource_type: str, package_id: str = None) -> dict
  - Elenca risorse disponibili per tipo
  - Indica quali hanno un workspace-override attivo
  - Risposta: {
      "type": "agents",
      "items": [
        {"name": "code-Agent-Code", "has_override": false},
        {"name": "spark-assistant", "has_override": true}
      ]
    }

scf_read_resource(uri: str, source: str = "auto") -> dict
  - Legge contenuto di una risorsa
  - source: "auto" (override se esiste, altrimenti engine)
             "engine" (sempre versione canonica)
             "override" (solo override, errore se non esiste)
  - Risposta: {"uri": ..., "content": "...", "source": "engine|override",
               "package": ..., "version": ...}

scf_override_resource(uri: str, content: str) -> dict  [NUOVO]
  - Scrive una versione override nel workspace corrente
  - Vedi sezione 13 per il flusso completo
  - Risposta: {"uri": ..., "override_path": ..., "action": "created|updated"}

scf_drop_override(uri: str) -> dict  [NUOVO]
  - Rimuove il workspace-override, ripristina la versione engine
  - Risposta: {"uri": ..., "action": "dropped", "restored_to": "engine"}

scf_migrate_workspace() -> dict  [NUOVO]
  - Migrazione workspace v2.x → v3.0
  - Vedi sezione 14 per il flusso completo

NOTA TOOL COUNT (post-validazione 2026-04-28):
- Tool esistenti in engine v2.4.0: 35 (verificati via grep async def scf_)
- Nuovi tool v3.0: 5 (i quattro override + scf_migrate_workspace)
- Totale post-refactor: 40 tool registrati via @_register_tool
- scf_update_profile NON è in scope v3.0; verrà valutato in v3.1
  insieme all'evoluzione dell'agente spark-welcome.

## 5.4 Manifest interno dell'engine (engine-manifest.json) [NUOVO]

L'engine ha risorse proprie non appartenenti a nessun pacchetto installato.

Struttura: engine-manifest.json nella root dell'engine
  {
    "schema_version": "3.0",
    "package": "spark-framework-engine",
    "version": "3.0.0",
    "workspace_files": [
      ".github/instructions/framework-guard.instructions.md",
      ".github/instructions/personality.instructions.md",
      ".github/instructions/verbosity.instructions.md",
      ".github/instructions/workflow-standard.instructions.md",
      ".github/instructions/git-policy.instructions.md",
      ".github/instructions/model-policy.instructions.md"
    ],
    "mcp_resources": {
      "agents": ["spark-assistant", "spark-engine-maintainer",
                 "spark-guide", "spark-welcome"],
      "instructions": [
        "spark-assistant-guide",
        "spark-engine-maintenance",
        "project-reset"
      ],
      "prompts": [],
      "skills": []
    }
  }

STATO ATTUALE (verifica 2026-04-28):
- engine-manifest.json NON esiste ancora nel repo dell'engine.
- È deliverable OBBLIGATORIO della Fase 1 del piano implementativo.
- spark-welcome NON esiste ancora come file .github/agents/spark-welcome.agent.md.
  È deliverable della Fase 1 (creato contestualmente al manifest engine).
- Loader: EngineInventory (già presente alla riga 1308 dell'engine) viene
  esteso per leggere engine-manifest.json prima del bootstrap pacchetti.

FrameworkInventory carica engine-manifest.json prima dei pacchetti.

## 5.5 Decorator FastMCP dinamici

NOTA: i decorator dinamici @mcp.resource sono GIÀ il pattern in uso
nell'engine v2.4.0 (vedi helper _register_resource alla riga 2417 di
spark-framework-engine.py). La Fase 4 estende questo meccanismo,
non lo introduce ex novo.

SCHEMA URI UNIFICATO (post-W3, 2026-04-28):
Lo schema URI è singolo per tutte le risorse, indipendentemente da
proprietario (engine vs pacchetto). McpResourceRegistry distingue
internamente engine-owned vs package-owned tramite metadata.

  @mcp.resource("agents://{agent_name}")
  def resource_agent(agent_name: str) -> str:
      path = registry.resolve(f"agents://{agent_name}")
      return path.read_text(encoding="utf-8")

  @mcp.resource("skills://{skill_name}")
  def resource_skill(skill_name: str) -> str:
      path = registry.resolve(f"skills://{skill_name}")
      return path.read_text(encoding="utf-8")

  @mcp.resource("instructions://{instr_name}")
  def resource_instruction(instr_name: str) -> str:
      path = registry.resolve(f"instructions://{instr_name}")
      return path.read_text(encoding="utf-8")

RETROCOMPATIBILITÀ engine-skills:// e engine-instructions://:
Gli URI engine-skills:// e engine-instructions:// (presenti in v2.4.0,
righe 2474 e 2489) vengono mantenuti come ALIAS che redirigono allo
stesso resolver di skills:// e instructions://. Logging warning su stderr
alla prima invocazione:
  [SPARK-ENGINE][WARN] URI deprecato {engine-skills,engine-instructions}://
  → usare {skills,instructions}://. Alias rimosso in v4.0.

I prompt MCP vengono registrati dinamicamente iterando
McpResourceRegistry.list_by_type("prompts").


# 6. Modifiche alle Classi Esistenti

## 6.1 FrameworkInventory

Aggiunge:
- Caricamento engine-manifest.json alla startup (prima dei pacchetti)
- Costruzione McpResourceRegistry con scan workspace-overrides
- Path resolution duale: override > engine-store > errore

## 6.2 ManifestManager

Modifica:
- Traccia SHA-256 solo per file in workspace_files + file override utente
- files_metadata con distinzione workspace vs mcp (vedi 4.4)
- Gestione del sottodirectory .github/overrides/ (vedi sezione 13)

## 6.3 RegistryClient

Modifica:
- Cache: workspace/.scf-registry-cache.json → engine_dir/cache/registry-cache.json
- Usa WorkspaceLocator.get_engine_cache_dir()

## 6.4 WorkspaceLocator

Aggiunge:
- get_engine_cache_dir() -> Path
- get_override_dir(workspace, resource_type) -> Path
  Risolve .github/overrides/{resource_type}/, crea se non esiste
- --workspace CLI flag per override da Cline

## 6.5 scf_bootstrap_workspace (tool 28°) aggiornato

Logica aggiornata:
1. Verifica sentinella: project-profile.md
2. Copia workspace_files da engine-manifest + pacchetti installati
3. Genera AGENTS.md dinamicamente da McpResourceRegistry
4. Genera AGENTS-{plugin}.md per ogni pacchetto installato con agenti
5. Scrive project-profile.md template se non esiste
6. Genera .clinerules se assente (vedi sezione 7)
7. NON copia agents/, prompts/, skills/ nel workspace
8. Scansiona .github/overrides/ se esiste → registra override in McpResourceRegistry

Idempotenza:
- project-profile.md esistente → salta template
- workspace_file con SHA diverso → preserva (file modificato utente)


# 7. Integrazione Cline/Roo — .clinerules

## 7.1 Contenuto minimo .clinerules per progetto SPARK

  # SPARK Framework — Contesto Operativo

  ## Stack tecnica engine
  - Python 3.11+, FastMCP, stdio JSON-RPC
  - File principale: spark-framework-engine.py
  - Logging: solo stderr, formato [SPARK-ENGINE][LEVEL] msg
  - stdout: solo JSON-RPC, mai print()

  ## Tool MCP disponibili
  - scf_list_resources(type)       → lista risorse per tipo
  - scf_read_resource(uri)         → contenuto risorsa (auto/engine/override)
  - scf_override_resource(uri)     → crea versione locale modificabile
  - scf_drop_override(uri)         → ripristina versione canonica engine
  - scf_get_runtime_state()        → stato sessione
  - scf://agents-index             → indice agenti installati
  - agents://{name}                → contenuto agente
  - skills://{name}                → contenuto skill

  ## Routing agenti
  - Operazioni workspace → spark-assistant
  - Manutenzione engine  → spark-engine-maintainer
  - Orientamento         → spark-guide

  ## Classi core engine (v3.0)
  - WorkspaceLocator, FrameworkInventory, ManifestManager,
    RegistryClient, PackageResourceStore, McpResourceRegistry

scf_bootstrap_workspace genera .clinerules automaticamente se assente,
con il contenuto sopra + sezione project-profile estratta da
.github/project-profile.md.


# 8. Configurazione MCP per Cline/Roo

File: %APPDATA%\Code\User\GlobalStorage\saoudrizwan.claude-dev\
       settings\cline_mcp_settings.json

Contenuto:
  {
    "mcpServers": {
      "spark-engine": {
        "command": "python",
        "args": [
          "C:\path\assoluto\spark-framework-engine.py",
          "--workspace", "C:\path\assoluto\progetto-corrente"
        ],
        "env": {}
      }
    }
  }

Path SEMPRE assoluti. Compatibile con config Copilot (.vscode/mcp.json)
che usa WORKSPACE_FOLDER via env — i due meccanismi coesistono.


# 9. Matrice Compatibilità Client

Funzionalità              | Copilot Agent Mode           | Cline / Roo Code
--------------------------|------------------------------|---------------------------
Istruzioni sistema        | copilot-instructions.md auto | .clinerules auto
Instruction per file type | instructions/*.md glob auto  | scf_read_resource on-demand
Indice agenti             | AGENTS.md auto               | scf_list_resources("agents")
Contenuto agente          | agents://name MCP pull       | agents://name MCP (identico)
Prompt template           | /mcp.spark-engine.name       | MCP Prompt (identico)
Skill                     | skills://name MCP pull       | skills://name MCP (identico)
Modifica risorsa          | scf_override_resource(uri)   | scf_override_resource (identico)
Ripristino risorsa        | scf_drop_override(uri)       | scf_drop_override (identico)
Tool operativi            | scf_* (invocati da agente)   | scf_* (identici)
Stato runtime             | scf://runtime-state MCP      | scf://runtime-state (identico)
Registry cache            | engine_dir/cache/            | engine_dir/cache/ (identico)


# 10. Piano di Implementazione — Fasi

REGOLA: ogni fase è completamente testabile prima di procedere.
Nessuna fase rompe il funzionamento Copilot durante la transizione.

## Fase 0 — scf_migrate_workspace (priorità alta, serve PRIMA del deploy v3.0)
  Implementare il tool di migrazione PRIMA di rilasciare l'engine v3.0
  come strumento di preparazione. Vedi sezione 14 per la logica completa.
  Test: workspace v2.x migrato → workspace v3.0 minimo corretto

## Fase 1 — Schema manifest v3.0 (zero impatto runtime)
  - workspace_files[] e mcp_resources{} aggiunti a tutti i manifest
  - engine-manifest.json creato nella root engine
  - engine_provided_skills deprecato
  - Campo files v2.1 rimane attivo come fallback
  Test: engine v2.x legge manifest v3.0 senza errori

## Fase 2 — PackageResourceStore + McpResourceRegistry
  - Due nuove classi implementate
  - McpResourceRegistry supporta override (path duale engine+override)
  - FrameworkInventory carica engine-manifest.json al boot
  - FrameworkInventory scansiona .github/overrides/ se presente
  Test: McpResourceRegistry.resolve() ritorna override se esiste

## Fase 3 — Tool MCP: scf_list_resources, scf_read_resource,
              scf_override_resource, scf_drop_override
  - Quattro tool implementati
  - scf_read_resource rispetta source parameter
  - scf_override_resource scrive in .github/overrides/{type}/
  - scf_drop_override rimuove il file override
  Test: ciclo completo override → lettura → drop su agente di test

## Fase 4 — Decorator dinamici FastMCP
  - @mcp.resource e @mcp.prompt dinamici da McpResourceRegistry
  Test: Copilot può usare "Add Context > MCP Resources" e vedere agenti

## Fase 5 — WorkspaceLocator + RegistryClient cache relocation
  - get_engine_cache_dir(), get_override_dir()
  - --workspace CLI flag
  - Cache spostata fuori dal workspace
  Test: cache in posizione corretta; Cline avviato con --workspace funziona

## Fase 6 — scf_bootstrap_workspace (tool 28°) aggiornato
  - Logica alleggerita + generazione AGENTS.md + .clinerules
  - Scansione .github/overrides/ al bootstrap
  Test: bootstrap su workspace vergine → workspace minimo corretto
        bootstrap su workspace con overrides → override registrati

## Fase 7 — ManifestManager snellimento + smoke-test
  - Tracking SHA-256 solo per workspace_files + overrides
  SMOKE TEST COPILOT (obbligatorio prima del merge):
    1. Bootstrap workspace → AGENTS.md generato correttamente
    2. Copilot riconosce agenti in copilot-instructions.md
    3. Copilot può usare MCP Resources per agenti non nel workspace
    4. scf_override_resource crea file in .github/overrides/
    5. scf_read_resource ritorna override corretto
    6. scf_drop_override rimuove override, ritorna versione engine
    7. Install/remove pacchetto → AGENTS.md aggiornato automaticamente

## Fase 8 — Deploy e migrazione utenti esistenti
  - Rilascio engine v3.0.0
  - scf_migrate_workspace disponibile come tool attivo
  - Documentazione migrazione pubblicata
  Test: workspace v2.x migrato senza perdita dati utente


# 11. Invarianti del Sistema (Non Negoziabili)

1. CANALE STDIO PURO
   Zero print() su stdout. Solo JSON-RPC. Logging solo su stderr.

2. MANIFESTMANAGER GATE
   ManifestManager unico punto di scrittura sotto .github/.
   github_write_authorized verificato prima di ogni scrittura.

3. IDEMPOTENZA
   Bootstrap e install non sovrascrivono file utente modificati.
   Sentinella: project-profile.md

4. SOLA LETTURA RISORSE MCP PER DEFAULT
   Le risorse nell'engine non vengono mai modificate direttamente.
   La modifica passa sempre da scf_override_resource → .github/overrides/

5. GRACEFUL DEGRADATION
   Pacchetto senza mcp_resources → nessun crash, solo risorse non registrate.
   Manifest v2.1 → fallback su files, warning su stderr.
   URI non trovato → isError:true nel payload MCP, mai eccezione su stdout.

6. RETROCOMPATIBILITÀ CLIENT
   Engine v3.x serve correttamente Copilot senza modifiche al workspace
   utente esistente. La migrazione è opt-in, non forzata.

7. SEMANTIC VERSIONING
   Engine: 3.0.0
   min_engine_version nei manifest aggiornati: "3.0.0"
   Pacchetti con manifest v2.1 compatibili con engine v3.x.


# 12. Versioning e Dipendenze

  spark-framework-engine  2.x → 3.0.0  (questo refactoring)
  spark-base              1.5.0 → 1.6.0 (manifest v3.0)
  scf-master-codecrafter  2.3.0 → 2.4.0 (manifest v3.0)
  scf-pycode-crafter      2.1.0 → 2.2.0 (manifest v3.0)
  scf-registry            schema 2.0 (nessuna modifica necessaria)


# 13. Protezione Risorse MCP — Policy di Modifica con Workspace Override
#     [SEZIONE NUOVA v1.1]

## 13.1 Principio

Le risorse nell'engine (agents, prompts, skills, instructions) sono
IN SOLA LETTURA per definizione. Appartengono al pacchetto che le
dichiara, versionato e con integrità SHA-256 verificata.

NOTA TECNICA (post-W4, 2026-04-28):
FastMCP non espone primitive di scrittura su Resource. Lato client AI
l'unica strada per modificare una risorsa engine è invocare il tool
scf_override_resource. Il vincolo "sola lettura" si traduce quindi in:
- Nessun tool MCP accetta scritture dirette su URI agents://, skills://,
  prompts://, instructions:// pointing all'engine store.
- L'unico tool che produce side-effect su una risorsa è
  scf_override_resource e scrive ESCLUSIVAMENTE in
  .github/overrides/{type}/{name}.md del workspace corrente.
- scf_drop_override è l'unico tool che rimuove un override.

Qualsiasi tentativo di passaggio a tool diversi (es. richiesta agente
di modificare un file engine via filesystem-write) deve essere intercettato
dal layer applicativo dell'agente — non è enforced dall'engine MCP
perché FastMCP non lo permette.

## 13.2 Flusso Workspace Override

Quando un utente vuole personalizzare una risorsa:

  STEP 1 — Richiesta: l'utente (via chat) chiede di modificare
           agents://code-Agent-Code o prompts://git-commit

  STEP 2 — Override copy: l'engine esegue scf_override_resource(uri, content)
           che:
           a) Legge il contenuto CORRENTE dall'engine store
           b) Scrive una COPIA in .github/overrides/{type}/{name}.md
           c) Registra l'override in McpResourceRegistry
           d) Logga: [SPARK-ENGINE][INFO] Override creato: agents://code-Agent-Code
              → .github/overrides/agents/code-Agent-Code.md

  STEP 3 — Modifica: l'agente AI modifica il file override nel workspace
           (via tool filesystem standard o edit diretto).
           L'engine non è coinvolto in questa fase.

  STEP 4 — Lettura: da questo momento scf_read_resource("agents://code-Agent-Code")
           ritorna il contenuto dell'override, non quello dell'engine.
           La versione engine rimane accessibile con source="engine".

  STEP 5 — Ripristino (opzionale): scf_drop_override("agents://code-Agent-Code")
           rimuove il file override. La risorsa torna alla versione engine.

## 13.3 Struttura Directory Overrides nel Workspace

  .github/
  └── overrides/                    [creata automaticamente se necessario]
      ├── agents/
      │   └── code-Agent-Code.md    [override utente]
      ├── prompts/
      │   └── git-commit.md         [override utente]
      ├── skills/
      └── instructions/

## 13.4 Comportamento al Bootstrap e Install/Update

- Bootstrap workspace vergine: .github/overrides/ non viene creata.
  Viene creata solo al primo scf_override_resource.
- Bootstrap workspace esistente con overrides: SPARK scansiona
  .github/overrides/ e registra tutti i file trovati in McpResourceRegistry.
- Install/update pacchetto: NON tocca mai .github/overrides/.
  Gli override utente sono sempre preservati.
- Remove pacchetto: logga warning se esistono override per quel pacchetto,
  ma NON li cancella. L'utente decide esplicitamente.

## 13.5 Aggiornamento Pacchetto con Override Attivi

Quando scf_update_package aggiorna un pacchetto che ha override attivi:
  1. Confronta SHA-256 della versione engine aggiornata con l'override
  2. Se diversi: notifica l'utente con diff summary e chiede conferma
     su cosa fare: (a) mantieni override, (b) aggiorna override alla
     nuova versione, (c) drop override e usa nuova versione engine
  3. Senza conferma esplicita: mantieni l'override esistente (safe default)

## 13.6 Copilot e gli Override

Gli override in .github/overrides/ NON vengono letti automaticamente
da Copilot (non è nella lista dei path che Copilot scansiona).
Copilot accede agli override SOLO tramite MCP Resources — il che è
corretto: la versione personalizzata è disponibile nella sessione
Copilot solo quando l'agente o l'utente richiede esplicitamente la
risorsa via "Add Context > MCP Resources" o tool invocation.
Questo è il comportamento desiderato: l'override è opt-in per sessione,
non iniettato automaticamente.


# 14. Migrazione Workspace Esistente v2.x → v3.0
#     [SEZIONE NUOVA v1.1]

## 14.1 Scenari di Migrazione

Un utente che aggiorna l'engine da v2.x a v3.0 può trovarsi in
quattro scenari distinti per ogni tipo di file nel workspace.

SCENARIO A — File che nel v3.0 devono RESTARE nel workspace
  (copilot-instructions.md, instructions/*.md, project-profile.md,
  .scf-manifest.json, runtime/orchestrator-state.json)
  Azione: NESSUNA. Rimangono dove sono, continuano a funzionare.
  Nota per copilot-instructions.md: il formato SCF:BEGIN/END è
  compatibile v2/v3 — nessuna modifica strutturale necessaria.

SCENARIO B — File che nel v3.0 diventano RISORSE MCP
  (agents/*.agent.md, prompts/*.prompt.md, skills/*.skill.md,
  skills/*/SKILL.md, changelogs/)
  Azione: il tool scf_migrate_workspace li SPOSTA in
  .github/overrides/{type}/ invece di eliminarli.
  Motivazione: l'utente potrebbe aver modificato questi file.
  Trattarli come override preserva le personalizzazioni.
  AGENTS*.md: eliminati (saranno rigenerati dinamicamente).

SCENARIO C — File che nel v3.0 vengono ELIMINATI dal workspace
  (AGENTS*.md generati automaticamente, .scf-registry-cache.json)
  Azione: eliminati durante la migrazione.
  AGENTS*.md: verranno rigenerati al primo bootstrap/install.
  .scf-registry-cache.json: spostato in engine_dir/cache/.

SCENARIO D — File utente non riconosciuti (fuori dal manifest)
  Azione: NESSUNA. scf_migrate_workspace non tocca file non noti.
  Logga: [SPARK-ENGINE][INFO] File non gestito preservato: {path}

## 14.2 Tool scf_migrate_workspace — Logica

  INPUT:
    dry_run: bool = True   # default: solo analisi, nessuna scrittura
    force: bool = False    # se True: esegue senza conferma interattiva

  FLUSSO (sempre a due step):
  1. ANALISI (obbligatoria, anche se force=True):
     - Scansiona tutto .github/ nel workspace
     - Classifica ogni file in A/B/C/D
     - Costruisce migration_plan con azioni previste
     - Ritorna migration_plan al client SENZA eseguire nulla

  2. ESECUZIONE (solo se dry_run=False):
     - Richiede conferma esplicita (o force=True)
     - Esegue le azioni del migration_plan in ordine sicuro:
       a) Crea .github/overrides/ se necessario
       b) Sposta file Scenario B in overrides/
       c) Elimina file Scenario C
       d) Lascia invariati A e D
       e) Rigenera AGENTS.md da McpResourceRegistry
       f) Aggiorna .scf-manifest.json con nuovo schema v3.0
     - Ritorna migration_report con azioni eseguite e file toccati

  RISPOSTA (dry_run=True):
    {
      "migration_plan": {
        "keep": ["copilot-instructions.md", "project-profile.md", ...],
        "move_to_override": [
          {"from": ".github/agents/code-Agent-Code.md",
           "to": ".github/overrides/agents/code-Agent-Code.md"}
        ],
        "delete": [".github/AGENTS-master.md", ".scf-registry-cache.json"],
        "untouched": ["README.md", "src/main.py"]
      },
      "requires_confirmation": true
    }

## 14.3 Casistiche Edge della Migrazione

CASO 1 — Workspace vergine su engine v3.0 (utente nuovo)
  Non ha file v2.x. scf_bootstrap_workspace crea direttamente
  il workspace v3.0 minimo. scf_migrate_workspace non necessario.

CASO 2 — Workspace v2.x con file AGENTS*.md non modificati
  AGENTS*.md hanno SHA uguale alla versione del pacchetto.
  scf_migrate_workspace li elimina (non c'è personalizzazione da preservare).
  Vengono rigenerati automaticamente da McpResourceRegistry.

CASO 3 — Workspace v2.x con agents/*.agent.md modificati dall'utente
  SHA diverso dalla versione pacchetto.
  scf_migrate_workspace sposta in .github/overrides/agents/.
  McpResourceRegistry li registra come override al prossimo boot.
  L'utente mantiene le sue personalizzazioni senza perdita.

CASO 4 — Workspace v2.x con .scf-registry-cache.json
  Viene spostato in engine_dir/cache/ (copia + delete originale).
  Se engine_dir/cache/ non esiste, viene creata.

CASO 5 — Workspace v2.x con copilot-instructions.md modificato
  (testo utente fuori dai blocchi SCF:BEGIN/END)
  Il file viene lasciato INVARIATO (Scenario A).
  Il testo utente fuori dai marker è protetto dal sistema di merge
  già esistente — nessun rischio.

CASO 6 — Utente che fa rollback da engine v3.0 a v2.x
  Il workspace v3.0 (minimo) è compatibile con engine v2.x in lettura:
  - copilot-instructions.md: compatibile (stesso formato)
  - .github/overrides/: engine v2.x non la conosce, la ignora
  - AGENTS.md assente: engine v2.x non lo genera, Copilot lo cercherà
  AZIONE CONSIGLIATA: prima del rollback, eseguire scf_bootstrap_workspace
  con engine v2.x per ricreare i file mancanti.

## 14.4 Comunicazione all'Utente durante la Migrazione

La risposta di scf_migrate_workspace (dry_run=True) deve essere
navigabile NVDA — lista puntata gerarchica, no tabelle ASCII:

  PIANO DI MIGRAZIONE v2.x → v3.0
  ================================
  File preservati (nessuna azione):
    - .github/copilot-instructions.md
    - .github/project-profile.md
    - .github/instructions/mcp-context.instructions.md
    - .github/runtime/orchestrator-state.json
    - .scf-manifest.json

  File spostati in overrides (personalizzazioni preservate):
    - .github/agents/code-Agent-Code.md
      → .github/overrides/agents/code-Agent-Code.md
    - .github/prompts/git-commit.md
      → .github/overrides/prompts/git-commit.md

  File eliminati (rigenerati automaticamente):
    - .github/AGENTS-master.md
    - .github/AGENTS.md
    - .scf-registry-cache.json

  File non riconosciuti (ignorati):
    - .github/custom-notes.md

  Per eseguire la migrazione:
    scf_migrate_workspace(dry_run=False)


# 15. Versioning Engine e Pacchetti (aggiornato)

  spark-framework-engine  2.4.0 → 3.0.0
    Nuove classi: PackageResourceStore, McpResourceRegistry
    Nuovi tool (5): scf_list_resources, scf_read_resource,
                    scf_override_resource, scf_drop_override,
                    scf_migrate_workspace
    Tool count: 35 (v2.4.0) + 5 = 40 tool totali post-refactor
    Nuovo file: engine-manifest.json (deliverable Fase 1)
    Nuovo agente engine: spark-welcome (deliverable Fase 1)
    URI deprecati con alias retrocompatibile:
      engine-skills:// → skills:// (rimosso in v4.0)
      engine-instructions:// → instructions:// (rimosso in v4.0)

  spark-base              1.5.0 → 1.6.0
  scf-master-codecrafter  2.3.0 → 2.4.0
  scf-pycode-crafter      2.1.0 → 2.2.0
  scf-registry            schema 2.0 (invariato)

---
Fine documento — SPARK-REFACTORING-DESIGN-v1.2
