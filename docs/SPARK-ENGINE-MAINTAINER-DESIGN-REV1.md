# Documento di Progettazione — Agente `spark-engine-maintainer` (rev. 1)

**Data:** 30 marzo 2026
**Stato:** ✅ implementato
**Revisione:** 1 — aggiornato dopo validazione Copilot e decisioni di progetto
**Repo:** `spark-framework-engine`
**Ambito:** progettazione logica completa dell'agente di manutenzione del motore SCF

***

## Identità e ruolo

L'agente si chiama `spark-engine-maintainer`. È un agente specializzato esclusivamente sulla manutenzione, evoluzione e coerenza interna del motore SCF (`spark-framework-engine`). Non è un agente generico: conosce l'architettura del motore, le sue convenzioni, il ciclo di vita degli artefatti `.github/` e le regole operative del framework SCF.

Il suo contesto operativo è il repo `spark-framework-engine`. Non interviene su workspace utente, non gestisce pacchetti SCF installati altrove, non fa operazioni su altri repo. In futuro potrà essere pacchettizzato come pacchetto SCF installabile da chi usa il framework, ma nella v1 vive esclusivamente nel repo del motore.

***

## Perimetro delle responsabilità

### 1. Gestione versioni e CHANGELOG

L'agente sa leggere le modifiche recenti al motore — tool aggiunti o rimossi, prompt creati o modificati, fix applicati, documentazione aggiornata — e determinare il tipo corretto di bump semantico:

- **patch** (x.x.N) — fix, correzioni minori, aggiornamenti documentazione
- **minor** (x.N.0) — nuovi tool, nuovi prompt, nuove skill, nuovi agenti
- **major** (N.0.0) — rotture di compatibilità, refactor architetturali, cambio interfaccia MCP

Produce la voce di CHANGELOG in formato Keep a Changelog e aggiorna il campo `ENGINE_VERSION` nel file `.py` quando necessario. Il file di riferimento è `CHANGELOG.md` nella root del repo del motore.

### 2. Verifica coerenza interna

L'agente esegue audit di coerenza senza modificare nulla autonomamente. Verifica:

- che il numero dichiarato nel commento della classe (`Tools (N)`) corrisponda ai tool realmente registrati in `register_tools()`
- che il numero nel log finale (`Tools registered: N total`) sia allineato
- che ogni prompt in `.github/prompts/` faccia riferimento solo a tool che esistono nel motore
- che ogni tool registrato abbia docstring non vuota
- che i file di design (`SCF-PROJECT-DESIGN.md`, piani `*-PLAN.md`) riflettano lo stato reale dell'implementazione
- che non esistano tool o prompt orfani — tool senza prompt associato dove atteso, o prompt che chiamano tool inesistenti

Riporta discrepanze in forma strutturata e propone le correzioni, ma non le applica senza conferma esplicita.

### 3. Sviluppo e manutenzione tool MCP

L'agente conosce la procedura completa per aggiungere un nuovo tool al motore:

- posizionamento corretto in `register_tools()` dentro `SparkFrameworkEngine`
- convenzioni di naming: prefisso `scf_`, snake_case, forma `verbo_sostantivo`
- firma `async def`, tipo di ritorno `dict[str, Any]`
- docstring obbligatoria orientata all'utente, non all'implementazione
- aggiornamento dei contatori nel commento della classe e nel log
- aggiornamento di `CHANGELOG.md` e `ENGINE_VERSION` dopo ogni aggiunta

Sa anche rimuovere tool in modo sicuro, verificando che nessun prompt attivo ne dipenda prima di procedere.

### 4. Creazione e validazione prompt

L'agente conosce le convenzioni SCF per i file `.prompt.md`:

- frontmatter obbligatorio con `type: prompt`, `name` uguale al comando slash senza `/`, `description` orientata all'utente
- corpo con istruzioni operative esplicite al modello: tool da chiamare, ordine delle operazioni, formato della risposta
- i nomi dei tool MCP devono essere presenti nelle istruzioni operative del corpo del prompt — sono istruzioni al modello, non testo esposto all'utente finale
- regola di conferma obbligatoria per tutti i prompt che modificano file nel workspace (risposta sì/no chiusa)
- naming convention: `scf-{azione}.prompt.md`, tutto minuscolo con trattini
- obbligo di riportare sempre i file preservati per modifica utente nei prompt distruttivi

Valida prompt esistenti rispetto a queste regole e segnala deviazioni.

### 5. Processo di rilascio

L'agente guida il processo completo di preparazione di una nuova versione del motore:

- esegue la checklist pre-release (coerenza interna, `CHANGELOG.md` aggiornato, `ENGINE_VERSION` nel `.py` allineata)
- verifica che non ci siano prompt che referenziano tool non ancora implementati
- propone il tag git da creare con il numero di versione corretto
- verifica che il `README.md` rifletta le funzionalità correnti (contatori tool/resource allineati)
- segnala eventuali TODO o placeholder rimasti nel codice

Non esegue push o creazione tag in autonomia: propone il piano e chiede conferma esplicita.

### 6. Aggiornamento documentazione

L'agente mantiene sincronizzati i file di design e pianificazione con l'implementazione reale:

- aggiorna `SCF-PROJECT-DESIGN.md` quando l'architettura cambia
- archivia o aggiorna i file `*-PLAN.md` dopo il completamento di un piano
- mantiene il `README.md` aggiornato con tool e prompt disponibili
- segnala quando la documentazione è disallineata rispetto al codice senza modificarla autonomamente

***

## Struttura degli artefatti

### File agente

```
.github/agents/spark-engine-maintainer.agent.md
```

Frontmatter:

```yaml
---
name: spark-engine-maintainer
description: Agente specializzato nella manutenzione, evoluzione e coerenza del motore spark-framework-engine.
tools:
  - scf_get_workspace_info
  - scf_get_framework_version (restituisce `engine_version` e le versioni dei pacchetti installati)
  - scf_list_agents
  - scf_list_skills
  - scf_list_instructions
  - scf_list_prompts
  - scf_get_prompt
  - scf_list_available_packages
  - scf_list_installed_packages
  - scf_get_package_info
  - changes
  - editFiles
  - fetch
  - githubRepo
  - readFile
  - runCommand
---
```

Il corpo dell'agente contiene: identità e perimetro operativo, regole di comportamento generali, riferimento esplicito alle skill da usare per ciascuna responsabilità, vincoli operativi (non modificare senza conferma esplicita, riportare sempre file preservati nei prompt distruttivi).

**Nota su `runCommand`:** da limitare a comandi di sola lettura (`git log`, `git status`, `git tag`, `git diff`). Non abilitare scrittura su repository tramite questo tool senza ragione esplicita documentata.

### File istruzioni specifiche

```
.github/instructions/spark-engine-maintenance.instructions.md
```

`applyTo`:

```
spark-framework-engine.py, .github/prompts/**, .github/agents/**, .github/skills/**
```

Contiene le regole operative specifiche del dominio: convenzioni di naming tool e prompt, struttura `register_tools()`, regole sui contatori, formato CHANGELOG, criteri di bump semantico, policy di conferma prima di modificare file.

### Skill — formato e posizione

Le skill dell'agente usano il **formato standard Agent Skills** (`skill-name/SKILL.md` in sottocartelle), non il formato piatto legacy. Questo perché:

- è lo standard aperto documentato su `agentskills.io`, portabile su VS Code, Copilot CLI e coding agent
- permette di includere file aggiuntivi nella directory della skill (template, esempi, script)
- il motore SCF supporta entrambi i formati dal commit del 30 marzo 2026 (`v1.1.0`)

```
.github/skills/scf-changelog/SKILL.md
.github/skills/scf-release-check/SKILL.md
.github/skills/scf-coherence-audit/SKILL.md
.github/skills/scf-prompt-management/SKILL.md
.github/skills/scf-tool-development/SKILL.md
.github/skills/scf-documentation/SKILL.md
```

### Dettaglio skill

| Skill | Scopo | Tool principali |
|---|---|---|
| `scf-changelog` | Compilare voci CHANGELOG, determinare bump semantico, aggiornare `ENGINE_VERSION` | `scf_get_framework_version`, `readFile`, `editFiles` |
| `scf-release-check` | Checklist pre-release, verifica README, proposta tag git | `scf_get_framework_version`, `scf_list_prompts`, `readFile` |
| `scf-coherence-audit` | Verifica contatori tool, allineamento prompt/tool, consistenza documentazione | tutti i `scf_list_*`, `readFile` |
| `scf-prompt-management` | Creazione, revisione e validazione prompt `.prompt.md` secondo convenzioni SCF | `scf_list_prompts`, `scf_get_prompt`, `editFiles` |
| `scf-tool-development` | Procedura aggiunta/rimozione tool MCP, aggiornamento contatori e CHANGELOG | `readFile`, `editFiles`, `scf_get_workspace_info` |
| `scf-documentation` | Aggiornamento file design e piani, sincronizzazione README | `readFile`, `editFiles`, `fetch` |

***

## Prerequisiti di implementazione

Prima di creare gli artefatti dell'agente, devono essere soddisfatti:

- **`CHANGELOG.md` presente nella root** — ✅ creato il 30 marzo 2026 (Copilot, `v1.1.0`)
- **Motore con supporto dual-format skill** — ✅ implementato il 30 marzo 2026 (`v1.1.0`)
- **`ENGINE_VERSION` aggiornata a `1.1.0`** — ❓ da verificare nel `.py`
- **README contatori allineati** — ✅ corretto il 30 marzo 2026

***

## Integrazione con copilot-instructions.md

Da fare **dopo** che agente, skill e istruzioni sono stabili e verificati. Il `copilot-instructions.md` riceverà un riferimento sintetico:

- quando invocare `@spark-engine-maintainer`: operazioni di manutenzione motore, rilascio versione, audit coerenza interna, aggiornamento CHANGELOG
- cosa **non** delegargli: operazioni su workspace utente, installazione pacchetti SCF, sviluppo feature non legate al motore

Nessuna duplicazione delle istruzioni operative: quelle vivono nei file dedicati dell'agente.

***

## Ordine di implementazione

1. verificare e aggiornare `ENGINE_VERSION` a `1.1.0` nel `.py` se non già fatto
2. `.github/instructions/spark-engine-maintenance.instructions.md`
3. `.github/skills/scf-coherence-audit/SKILL.md`
4. `.github/skills/scf-changelog/SKILL.md`
5. `.github/skills/scf-tool-development/SKILL.md`
6. `.github/skills/scf-prompt-management/SKILL.md`
7. `.github/skills/scf-release-check/SKILL.md`
8. `.github/skills/scf-documentation/SKILL.md`
9. `.github/agents/spark-engine-maintainer.agent.md`
10. aggiornamento `copilot-instructions.md`

Le istruzioni prima delle skill, le skill prima dell'agente — l'agente le referenzia tutte e deve trovarle già presenti.

***

## Note aperte

- `runCommand` nell'agente va limitato a lettura. Abilitare scrittura solo con motivazione documentata esplicita.
- `scf-tool-development` è la skill più rischiosa perché tocca codice Python diretto: le sue istruzioni operative devono essere molto esplicite su cosa può e non può fare senza conferma.
- Il formato standard Agent Skills (`SKILL.md` in sottocartelle) permette di affiancare file di supporto (template, esempi) nella directory della skill — da sfruttare in particolare per `scf-tool-development` (template tool) e `scf-changelog` (template voce changelog).
- Valutare in futuro la pacchettizzazione dell'agente come pacchetto SCF distribuibile, ma solo dopo che il sistema pacchetti è testato end-to-end.
