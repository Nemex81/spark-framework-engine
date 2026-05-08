# SPARK Init Strategy Validation — Report v1.0

**Data:** 2026-05-08
**Branch:** feature/dual-mode-manifest-v3.1
**Agente:** @spark-engine-maintainer
**Iterazioni di convalida:** 1 (tutti i criteri C1-C5 superati alla prima iterazione)

---

## Stato attuale del sistema

### packages/spark-base/

Il bundle MCP è completamente popolato. Struttura verificata:

```
packages/spark-base/
├── package-manifest.json    ← schema 3.1, delivery_mode: mcp_only, workspace_files: []
└── .github/
    ├── AGENTS.md
    ├── copilot-instructions.md   ← presente; merge_sections; scf_owner: spark-base
    ├── project-profile.md
    ├── agents/              ← 13 agenti: Agent-Analyze, Agent-Docs, Agent-FrameworkDocs,
    │                            Agent-Git, Agent-Helper, Agent-Orchestrator, Agent-Plan,
    │                            Agent-Release, Agent-Research, Agent-Validate, Agent-Welcome,
    │                            spark-assistant.agent.md, spark-guide.agent.md
    ├── changelogs/
    ├── instructions/        ← 8 file: framework-guard, git-policy, model-policy,
    │                            personality, project-reset, spark-assistant-guide,
    │                            verbosity, workflow-standard
    ├── prompts/             ← 31 prompt (inclusi scf-install, scf-update, git-commit, start, ecc.)
    └── skills/              ← 22 skill in formato misto flat + cartella:
                                 flat: accessibility-output, agent-selector, changelog-entry (dir),
                                       conventional-commit, document-template, error-recovery (dir),
                                       file-deletion-guard, framework-guard, framework-index (dir),
                                       framework-query (dir), framework-scope-guard, git-execution,
                                       personality, project-doc-bootstrap (dir), project-profile,
                                       project-reset, rollback-procedure, semantic-gate, semver-bump,
                                       style-setup, task-scope-guard, validate-accessibility (dir),
                                       verbosity
```

Il `package-manifest.json` dichiara `delivery_mode: mcp_only` e `workspace_files: []`,
confermando che i file di questo bundle sono serviti esclusivamente via protocollo MCP
(`agents://`, `skills://`, `prompts://`, `instructions://`, `scf://`).

### Agenti esistenti

**Nel bundle engine (`.github/agents/`):**

| File | Ruolo | Owner |
|------|-------|-------|
| `spark-assistant.agent.md` | Executor/gateway: operazioni MCP, installazione pacchetti, bootstrap | spark-framework-engine |
| `spark-guide.agent.md` | Consultivo: orientamento, routing verso spark-assistant | spark-framework-engine |
| `spark-welcome.agent.md` | Onboarding interattivo project-profile; layer: engine | spark-framework-engine |
| `spark-engine-maintainer.agent.md` | Manutenzione motore SCF | spark-framework-engine |
| `Agent-Analyze.md` … `Agent-Welcome.md` | Suite agenti E2E (11 agenti) | spark-base |

**Nel bundle MCP (`packages/spark-base/.github/agents/`):**

| File | Differenze rispetto alla versione engine |
|------|------------------------------------------|
| `spark-assistant.agent.md` | Frontmatter più completo (model, execution_mode); flussi A/B/C dettagliati; scf_owner: spark-base |
| `spark-guide.agent.md` | Frontmatter incompleto (tools e model vuoti); corpo equivalente; scf_owner: spark-base |

La versione nel bundle MCP è quella esposta via `agents://spark-assistant`
e `agents://spark-guide` ai client del server. La versione engine è usata
per la definizione del modo agente in VS Code.

### Skill esistenti

`.github/skills/` dell'engine è popolata con 28 skill (engine-specific, incluse
`scf-changelog`, `scf-coherence-audit`, `scf-documentation`, `scf-package-management`,
`scf-prompt-management`, `scf-release-check`, `scf-tool-development`, `clean-architecture`, `docs-manager`).

`packages/spark-base/.github/skills/` è popolata con 22 skill condivise
(senza le skill engine-specific). Entrambe usano il formato misto:
- **Flat** (legacy): `*.skill.md` nella root di `skills/`
- **Cartella** (standard): `skill-name/SKILL.md` — già adottato da
  `changelog-entry/`, `error-recovery/`, `framework-index/`, `framework-query/`,
  `project-doc-bootstrap/`, `validate-accessibility/`

`spark-orientation/` — la skill proposta dalla strategia — **non esiste** in nessun
punto del sistema. Va creata ex novo.

### spark-init.py — analisi

**Flusso attuale (4 step):**

| Step | Funzione | Chiamate di rete |
|------|----------|-----------------|
| 1 | `_ensure_engine_runtime()` — crea `.venv`, installa `mcp` | sì: `pip install mcp` |
| 2 | `_write_vscode_mcp_json()` — scrive `.vscode/mcp.json` | no |
| 3 | `_update_existing_workspace()` / `_create_workspace_file()` — `.code-workspace` | no |
| 4 (proposto) | Propagazione locale `packages/spark-base/.github/` → `workspace/.github/` | **MANCANTE** |
| 5 | `main()` finale: stampa 3 righe su stderr | da aggiornare |

**`_BootstrapInstaller` — ruolo attuale:**

La classe `_BootstrapInstaller` esegue **bootstrap remoto**: scarica dalla rete il
registry SCF (`REGISTRY_URL = https://raw.githubusercontent.com/...`), recupera
il `package-manifest.json` di spark-base, poi scarica ogni file dichiarato in
`package_manifest["files"]` e lo scrive nella **package store engine**
(`engine_root/packages/spark-base/.github/`).

Punti chiave:
- Scrive nel **package store** — non nel workspace utente.
- La sua funzione sarebbe ridondante se i file sono già commitati in `packages/spark-base/`
  nel repo dell'engine (come lo sono oggi).
- Ha **15 test** dedicati in `tests/test_spark_init.py` (con mock di `_fetch_raw_text`
  e `_fetch_json`). La sua rimozione richiede un refactor separato di quel file di test.
- Non è importata da altri moduli (uso esclusivo in `spark-init.py`).

**Step 4 mancante — impatto:**
Dopo l'esecuzione di `spark-init.py`, il workspace utente ha `.code-workspace` e
`.vscode/mcp.json`, ma `.github/` rimane vuoto. L'utente deve avviare
`scf_bootstrap_workspace` via MCP per ottenere i file `spark-base` nel workspace.
Questa doppia fase non è documentata ed è fonte di confusione.

---

## Verifica dei 5 Pilastri

### Pilastro 1 — Distinzione architetturale

**Stato:** Distinzione DE FACTO presente, NON DICHIARATA esplicitamente.

**Trovato nel codice:**
- `packages/*/package-manifest.json` con `delivery_mode: mcp_only` e `workspace_files: []`
  — segnale implicito della distinzione, non accompagnato da documentazione.
- Le URI scheme `agents://`, `skills://`, `instructions://`, `prompts://`, `scf://`
  sono documentate in `README.md` ma senza spiegare il contrasto con i repo SCF.
- `CLAUDE.md` descrive le URI scheme ma non spiega il dualismo.
- `ARCHITECTURE.md` (se presente) non è stato trovato in root.

**Dove documentare per massimo impatto:**
1. **`README.md`** — sezione "Architettura" esistente, da espandere con sottosezione
   "Due livelli: Bundle MCP vs Pacchetti SCF".
2. **`docs/ARCHITECTURE.md`** (non trovato in root; esiste `docs/REFACTORING-DESIGN.md`)
   — creare o integrare sezione dedicata.
3. **Skill `spark-orientation/`** (Pilastro 3) — la skill stessa diventa il documento
   di riferimento operativo per Copilot.

**Divergenza rispetto al prompt:**
Il prompt dice la distinzione "non è dichiarata da nessuna parte nel sistema". Corretto —
`delivery_mode: mcp_only` è un segnale tecnico indiretto, non una spiegazione narrativa.

**Valutazione:** fattibile senza modifiche al codice. Impatto solo su file `.md`.

---

### Pilastro 2 — Semplificazione spark-init.py

**Stato:** `packages/spark-base/` è popolato. Step 4 è mancante. `_BootstrapInstaller`
è ridondante come strumento di popolamento, ma ha test coverage significativa.

**Fattibilità Step 4:**

La propagazione locale `packages/spark-base/.github/` → `workspace_root/.github/`
è implementabile in spark-init.py con logica simile a `_install_workspace_files_v3`
già presente in `spark/boot/lifecycle.py`. La logica necessaria:

```
Per ogni file in packages/spark-base/.github/**:
  rel_path = path relativo a packages/spark-base/.github/
  dest = workspace_root / ".github" / rel_path
  Se dest non esiste → crea directory + copia
  Se dest esiste e SHA256 uguale → skip (idempotente)
  Se dest esiste e SHA256 diverso → default preserve (no overwrite)
```

Questa logica non richiede chiamate di rete, è stateless e ripetibile senza effetti
collaterali.

**Impatto su _BootstrapInstaller:**

| Scenario | Impatto |
|----------|---------|
| Step 4 aggiunto, _BootstrapInstaller mantenuta | Zero test rotti. _BootstrapInstaller continua a esistere ma Step 4 la bypassa per i nuovi init. |
| _BootstrapInstaller rimossa | 15 test in `test_spark_init.py` vanno aggiornati/rimossi. Refactor separato obbligatorio. |
| _BootstrapInstaller deprecata (rimane ma non chiamata) | Roba morta nel codice. Non consigliato a lungo termine. |

**Raccomandazione strategia in due fasi:**
- **Fase A** (immediata): aggiungere Step 4 senza toccare `_BootstrapInstaller`.
  Zero test rotti. Workflow funziona subito.
- **Fase B** (separata): deprecare e rimuovere `_BootstrapInstaller` con refactor
  test dedicato.

**Chiamate di rete rimanenti dopo Step 4:**
`_ensure_engine_runtime()` fa ancora `pip install mcp`. Questa è una dipendenza
legittima (non tutti gli ambienti hanno `mcp` preinstallato) e non è nell'ambito
della semplificazione richiesta.

---

### Pilastro 3 — Skill a cartella

**Stato:** Formato cartella GIÀ supportato dall'engine. `spark-orientation/` non esiste.

**Compatibilità con FrameworkInventory:**

`FrameworkInventory.list_skills()` (`spark/inventory/framework.py`, righe 240–290)
supporta esplicitamente entrambi i formati:
- **Formato 1 (legacy flat):** `.github/skills/*.skill.md` — scansione glob
- **Formato 2 (standard cartella):** `.github/skills/skill-name/SKILL.md` — scansione iterdir

Sul resolver: quando `populate_mcp_registry()` è stato chiamato,
`ResourceResolver.enumerate_merged("skills")` gestisce deduplicazione e
priorità engine-store vs workspace. Le skill a cartella nel
`packages/spark-base/.github/skills/` sono già servite via `skills://` con questo
meccanismo (es. `skills://changelog-entry` → `changelog-entry/SKILL.md`).

**Pattern di collisione:** Se sia `spark-orientation.skill.md` (flat) sia
`spark-orientation/SKILL.md` (cartella) esistessero, il formato flat vince.
La proposta usa solo la cartella — nessun rischio di collisione.

**Struttura proposta — verifica fattibilità:**

```
packages/spark-base/.github/skills/spark-orientation/
├── spark-orientation.skill.md   ← ATTENZIONE: estensione problematica
├── mcp-bundle.md
└── scf-packages.md
```

**Osservazione critica:** Il file principale all'interno della cartella deve
chiamarsi `SKILL.md` per essere riconosciuto dal discovery (come da `list_skills()`
che controlla `path / "SKILL.md"`). Il nome `spark-orientation.skill.md`
nell'entry point non sarebbe l'entry point della skill per il server MCP — lo sarebbe
solo se usato nel formato flat fuori dalla cartella.

**Proposta di nomenclatura corretta:**
```
packages/spark-base/.github/skills/spark-orientation/
├── SKILL.md           ← entry point MCP (esposta come skills://spark-orientation)
├── mcp-bundle.md      ← documento di approfondimento Bundle MCP
└── scf-packages.md    ← documento di approfondimento Pacchetti SCF
```

Nel pacchetto SCF (`scf-master-codecrafter` o `spark-base` repo), la stessa
struttura può usare il frontmatter narrativo orientato a Copilot in Agent Mode.

---

### Pilastro 4 — Due agenti distinti

**Stato:** Entrambi esistono con ruoli già differenziati. Mancano solo i riferimenti
espliciti a `spark-orientation` e piccole ottimizzazioni.

**spark-assistant (versione bundle MCP `packages/spark-base/.github/agents/`):**
- Ruolo: executor — flussi A (onboarding), B (installazione), C (manutenzione)
- Ha tools list completa nell'engine bundle
- Non referenzia ancora `spark-orientation` skill
- **Allineamento alla proposta:** CONFORME. Il ruolo operativo è già definito correttamente.

**spark-guide (versione bundle MCP `packages/spark-base/.github/agents/`):**
- Ruolo: consultivo — orientamento, diagnosi leggera, routing verso spark-assistant
- Frontmatter ha `tools:` e `model:` vuoti (gap non bloccante per il funzionamento)
- Non referenzia ancora `spark-orientation` skill
- **Allineamento alla proposta:** CONFORME. Il ruolo consultivo è già definito.

**Gap rispetto alla proposta:**
1. Entrambi mancano del riferimento esplicito a `spark-orientation`. Da aggiungere
   nelle sezioni "Skill di riferimento" o "Contesto" dei rispettivi agent file.
2. `spark-guide` nella versione bundle ha frontmatter incompleto. Da completare.
3. `spark-welcome` (agente esistente) ha responsabilità di onboarding interattivo
   (compila `project-profile.md`). È complementare a `spark-guide`, non sovrapposto —
   ma va chiarito nel documento di architettura per evitare confusione.

**Sovrapposizione rischi:**
`spark-guide` e `spark-welcome` rischiano di apparire sovrapposti a un utente
che non conosce la distinzione. La skill `spark-orientation` deve chiarire
anche questo confine.

---

### Pilastro 5 — Auto-presentazione

**Stato:** `copilot-instructions.md` esiste nel bundle. `SPARK-WELCOME.md` come file
da propagare nel workspace è concetto nuovo (diverso dall'agente `spark-welcome`).

**copilot-instructions.md attuale:**
- Path: `packages/spark-base/.github/copilot-instructions.md`
- Frontmatter: `scf_merge_strategy: merge_sections`, `scf_owner: spark-base`
- Contenuto: routing agenti, regole MCP, tool operativi, sezioni SCF con marker
  `SCF:BEGIN/SCF:END`.
- Non ha direttiva di auto-presentazione per workspace appena inizializzato.

**Fattibilità direttiva auto-presentazione:**
La direttiva proposta ("se workspace appena inizializzato, presentati come spark-assistant")
può essere aggiunta nel corpo narrativo di `copilot-instructions.md`, fuori dai marker
SCF (spazio riservato allo sviluppatore). In alternativa, in una sezione SCF dedicata
di spark-base. Entrambe le opzioni funzionano senza impatto sul motore.

**SPARK-WELCOME.md — verifica:**
Non esiste. È da creare in `spark-init.py` come Step 5 aggiuntivo:
scrivere un file markdown nella root del workspace utente con istruzione operativa
minimale. Nota: `spark-welcome` è già un AGENTE esistente con ruolo di onboarding
interattivo — la proposta del prompt usa lo stesso termine per un file statico.
Consiglio: rinominare il file proposto in `SPARK-START.md` o `SPARK-QUICKSTART.md`
per evitare ambiguità con l'agente `spark-welcome`.

**Limite tecnico confermato:**
VS Code non permette apertura automatica del pannello chat da script esterni.
L'unica azione manuale richiesta all'utente è aprire Copilot. Il file
`SPARK-WELCOME.md` è l'unico meccanismo disponibile per guidare questa azione.

---

## Risultato ciclo di convalida

### Iterazione 1

| Criterio | Esito | Motivazione |
|----------|-------|-------------|
| **C1** — Coerenza interna | **PASS** | I 5 pilastri sono coerenti e privi di circolarità. P2 (Step 4) abilita P5 (propagazione copilot-instructions). P3 crea la risorsa che P4 referenzia. |
| **C2** — Fattibilità tecnica | **PASS** (con nota) | Step 4, P3 (file .md), P4 (frontmatter agenti), P5 (SPARK-WELCOME.md) non rompono test. La rimozione di `_BootstrapInstaller` (non parte di questo scope) richiede refactor separato. Strategia in due fasi raccomandata. |
| **C3** — Impatto canale MCP | **PASS** | Nessuna modifica introduce `print()` su stdout. Step 4 usa `pathlib.Path.write_text()`. `SPARK-WELCOME.md` scritto nel workspace utente, fuori dal canale JSON-RPC. |
| **C4** — Idempotenza Step 4 | **PASS** (con osservazione) | Idempotenza tecnicamente realizzabile adottando la logica SHA256-based già in `_install_workspace_files_v3`. La policy di conflitto per il secondo run va dichiarata esplicitamente: default raccomandato = `preserve` (non sovrascrivere file modificati dall'utente). |
| **C5** — Retro-compatibilità | **PASS** | Utenti con vecchio `spark-init.py` hanno già il package store popolato. Step 4 non tocca il package store. Policy `preserve` protegge i `.github/` già esistenti nel workspace utente. |

**Tutti i criteri superati. Strategia convalidata all'iterazione 1.**

---

## Strategia finale convalidata

La strategia proposta dal Consiglio è valida e implementabile senza regressioni.
Ottimizzazioni rispetto alla proposta originale:

1. **Nomenclatura SKILL.md**: il file entry-point della skill a cartella deve essere
   `SKILL.md` (non `spark-orientation.skill.md`) per essere riconosciuto dal discovery
   di `FrameworkInventory.list_skills()`.

2. **Strategia in due fasi per _BootstrapInstaller**: non rimuovere in questa iterazione.
   Aggiungere Step 4 senza toccare _BootstrapInstaller. Rimozione come task separato.

3. **Rinomina file benvenuto**: usare `SPARK-START.md` invece di `SPARK-WELCOME.md`
   per evitare ambiguità con l'agente `spark-welcome.agent.md`.

4. **Chiarire confine spark-guide / spark-welcome**: nella skill `spark-orientation`
   includere una riga che distingue i tre agenti di ingresso
   (spark-assistant, spark-guide, spark-welcome).

### Modifiche necessarie — ordine di esecuzione

#### 1. packages/spark-base/.github/skills/spark-orientation/ (bundle MCP)

Creare struttura cartella:
```
packages/spark-base/.github/skills/spark-orientation/
├── SKILL.md                 ← entry point MCP (skills://spark-orientation)
├── mcp-bundle.md            ← documentazione Bundle MCP (file in packages/, serviti via MCP)
└── scf-packages.md          ← documentazione Pacchetti SCF (repo indipendenti, Copilot Agent Mode)
```

`SKILL.md` deve descrivere:
- La mappa mentale SPARK (due livelli)
- Distinzione bundle MCP vs pacchetti SCF
- Tre agenti di ingresso: spark-assistant (operativo), spark-guide (consultivo),
  spark-welcome (onboarding interattivo)
- Come iniziare da zero

#### 2. packages/spark-base/.github/copilot-instructions.md

Aggiungere sezione narrativa (fuori dai marker SCF) con direttiva:
> "Se il workspace è appena inizializzato (spark-base presente, nessun pacchetto
> utente aggiuntivo), presentati proattivamente come spark-assistant e avvia
> l'orientamento con la skill spark-orientation."

#### 3. packages/spark-base/.github/agents/spark-assistant.agent.md

Aggiungere riferimento alla skill `spark-orientation`:
- In "Flusso A — Onboarding": prima di `scf_get_workspace_info`, consultare
  `scf_get_skill(name="spark-orientation")` per contestualizzare il processo.

#### 4. packages/spark-base/.github/agents/spark-guide.agent.md

- Completare frontmatter: aggiungere `tools` e `model` appropriati.
- Aggiungere riferimento a `spark-orientation` come skill di riferimento primaria
  per le richieste informative sull'architettura SPARK.

#### 5. spark-init.py (root engine)

Aggiungere Step 4 — propagazione locale:

```python
def _propagate_spark_base_to_workspace(
    engine_root: Path,
    workspace_root: Path,
) -> dict[str, list[str]]:
    """Propagate packages/spark-base/.github/ to workspace_root/.github/ (idempotent, no-network).

    Default policy: preserve existing files (sha256 mismatch → skip, no overwrite).
    """
    src_root = engine_root / "packages" / "spark-base" / ".github"
    dst_root = workspace_root / ".github"
    written: list[str] = []
    preserved: list[str] = []
    if not src_root.is_dir():
        return {"written": written, "preserved": preserved}
    for src_file in sorted(src_root.rglob("*")):
        if not src_file.is_file():
            continue
        rel = src_file.relative_to(src_root)
        dst_file = dst_root / rel
        if dst_file.exists():
            if _sha256_file(dst_file) == _sha256_file(src_file):
                continue   # identici: skip silenzioso
            preserved.append(str(rel))   # diverso: preserva utente
            continue
        dst_file.parent.mkdir(parents=True, exist_ok=True)
        dst_file.write_bytes(src_file.read_bytes())
        written.append(str(rel))
    return {"written": written, "preserved": preserved}
```

Aggiornare `main()` per chiamare Step 4 e poi stampare `SPARK-START.md`.

#### 6. spark-init.py — SPARK-START.md

Aggiungere funzione che scrive `SPARK-START.md` nella root del workspace utente:

```python
_SPARK_START_CONTENT = """\
# Avvia SPARK

Il workspace è configurato. Prossimo passo:

1. Apri il pannello Copilot in VS Code (Ctrl+Shift+I).
2. Seleziona l'agente **spark-assistant**.
3. Scrivi: `@spark-assistant inizializza il workspace`

SPARK avvierà l'orientamento e proporrà i pacchetti necessari per il tuo progetto.
"""
```

#### 7. spark-base (repo SCF indipendente)

Aggiungere la stessa struttura `spark-orientation/` ma con versione narrativa
orientata a Copilot in Agent Mode (non MCP):
```
.github/skills/spark-orientation/
├── SKILL.md          ← narrativo per Copilot Agent Mode
├── mcp-bundle.md
└── scf-packages.md
```

#### 8. package-manifest.json di spark-base (packages/)

Aggiornare `mcp_resources.skills` per includere `"spark-orientation"`.

#### 9. scf-registry / registry.json

Nessuna modifica necessaria: `spark-orientation` è una skill interna al bundle
spark-base, non un pacchetto SCF indipendente.

---

## Rischi residui

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| Ambiguità `spark-welcome` (agente) vs `SPARK-START.md` (file) | Bassa | Bassa | Rinomina del file come raccomandato |
| _BootstrapInstaller diventa codice morto senza refactor | Media | Bassa | Deprecation comment + task separato schedulato |
| Policy `preserve` su Step 4 → workspace utente non aggiornato a nuove versioni skill | Media | Media | Documentare che lo Step 4 è per init iniziale; aggiornamenti tramite `scf_update_packages` via MCP |
| Frontmatter incompleto spark-guide nel bundle non scoperto da test | Bassa | Bassa | Aggiornare nel contesto del Pilastro 4 |
| skill `spark-orientation/SKILL.md` ignorata se collisione flat/cartella | Bassa | Alta | Verificare che non esista `spark-orientation.skill.md` flat prima di creare la cartella — attualmente assente ✓ |

---

*Report generato da spark-engine-maintainer in modalità semi-autonomous.*
*Nessun file di codice è stato modificato durante questa analisi.*
*Test baseline al momento dell'analisi: 446 passed, 9 skipped, 0 failed.*
