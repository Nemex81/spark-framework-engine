# Piano Tecnico Implementativo — Agente `spark-engine-maintainer`

**Data:** 30 marzo 2026
**Repo:** `spark-framework-engine`
**Riferimento progettazione logica:** `SPARK-ENGINE-MAINTAINER-DESIGN-REV1.md`
**Ambito:** creazione completa di tutti gli artefatti `.github/` dell'agente di manutenzione SCF

---

## Stato prerequisiti (verificati al 30 marzo 2026)

- `ENGINE_VERSION = "1.1.0"` in `spark-framework-engine.py` ✅
- `CHANGELOG.md` presente nella root ✅
- Motore con supporto dual-format skill (`list_skills()`) ✅
- `README.md` con contatori tool/resource allineati ✅
- Documento progettazione logica `SPARK-ENGINE-MAINTAINER-DESIGN-REV1.md` ✅

---

## Struttura directory da creare

```
.github/
├── prompts/                         # già esistente, non toccare
│   ├── scf-check-updates.prompt.md
│   ├── scf-install.prompt.md
│   ├── scf-list-available.prompt.md
│   ├── scf-list-installed.prompt.md
│   ├── scf-package-info.prompt.md
│   ├── scf-remove.prompt.md
│   ├── scf-status.prompt.md
│   └── scf-update.prompt.md
├── instructions/                    # da creare
│   └── spark-engine-maintenance.instructions.md
├── skills/                          # da creare
│   ├── scf-coherence-audit/
│   │   └── SKILL.md
│   ├── scf-changelog/
│   │   └── SKILL.md
│   ├── scf-tool-development/
│   │   └── SKILL.md
│   ├── scf-prompt-management/
│   │   └── SKILL.md
│   ├── scf-release-check/
│   │   └── SKILL.md
│   └── scf-documentation/
│       └── SKILL.md
├── agents/                          # da creare
│   └── spark-engine-maintainer.agent.md
└── copilot-instructions.md          # da creare
```

---

## Ordine di implementazione obbligatorio

Le istruzioni prima delle skill. Le skill prima dell'agente. L'agente prima di `copilot-instructions.md`. L'agente referenzia tutti gli altri artefatti — devono esistere prima.

1. `.github/instructions/spark-engine-maintenance.instructions.md`
2. `.github/skills/scf-coherence-audit/SKILL.md`
3. `.github/skills/scf-changelog/SKILL.md`
4. `.github/skills/scf-tool-development/SKILL.md`
5. `.github/skills/scf-prompt-management/SKILL.md`
6. `.github/skills/scf-release-check/SKILL.md`
7. `.github/skills/scf-documentation/SKILL.md`
8. `.github/agents/spark-engine-maintainer.agent.md`
9. `.github/copilot-instructions.md`

---

## Artefatto 1 — File istruzioni

**Percorso:** `.github/instructions/spark-engine-maintenance.instructions.md`

**Scopo:** fornire al modello le regole operative specifiche del dominio SCF ogni volta che lavora su file del motore. VS Code applica questo file automaticamente quando il contesto corrisponde al pattern `applyTo`.

**Frontmatter obbligatorio:**
```yaml
---
applyTo: "spark-framework-engine.py, .github/prompts/**, .github/agents/**, .github/skills/**"
---
```

**Contenuto del corpo — sezioni obbligatorie:**

Sezione A — Convenzioni naming tool MCP:
- prefisso obbligatorio `scf_`
- snake_case, forma `verbo_sostantivo` (es. `scf_list_skills`, `scf_get_prompt`)
- firma sempre `async def nome(self, ...) -> dict[str, Any]`
- docstring obbligatoria: prima riga orientata all'utente, non all'implementazione
- nessun tool senza docstring

Sezione B — Struttura `register_tools()`:
- ogni nuovo tool va aggiunto in coda al blocco `register_tools()` di `SparkFrameworkEngine`
- dopo ogni aggiunta aggiornare il contatore nel commento della classe: `# Tools (N)`
- dopo ogni aggiunta aggiornare il log finale: `logger.info("Tools registered: N total")`
- i due contatori devono essere sempre allineati tra loro e al numero reale di tool

Sezione C — Convenzioni naming prompt:
- nome file: `scf-{azione}.prompt.md`, tutto minuscolo, trattini
- frontmatter obbligatorio: `type: prompt`, `name` (comando slash senza `/`), `description` (orientata all'utente)
- corpo: istruzioni operative al modello con tool da chiamare esplicitamente per nome
- i nomi dei tool MCP vanno nelle istruzioni operative del corpo — sono istruzioni al modello, non testo esposto all'utente finale
- tutti i prompt che modificano file nel workspace devono includere una richiesta di conferma esplicita (risposta sì/no) prima di procedere
- i prompt distruttivi devono elencare esplicitamente i file che verranno preservati per modifica manuale dell'utente

Sezione D — Formato CHANGELOG e versioning:
- file di riferimento: `CHANGELOG.md` nella root del repo
- formato: Keep a Changelog (https://keepachangelog.com)
- versioning: Semantic Versioning (https://semver.org)
- bump patch (x.x.N): fix, correzioni minori, aggiornamenti documentazione
- bump minor (x.N.0): nuovi tool, nuovi prompt, nuove skill, nuovi agenti
- bump major (N.0.0): breaking change, refactor architetturali, cambio interfaccia MCP
- dopo ogni bump aggiornare `ENGINE_VERSION` in `spark-framework-engine.py`
- `ENGINE_VERSION` e ultima voce di `CHANGELOG.md` devono sempre essere allineate

Sezione E — Regola di conferma prima di modificare:
- l'agente non modifica mai file senza conferma esplicita dell'utente
- proporre sempre la modifica con anteprima prima di applicarla
- in caso di modifica a `spark-framework-engine.py`: mostrare il diff atteso e attendere approvazione

---

## Artefatto 2 — Skill `scf-coherence-audit`

**Percorso:** `.github/skills/scf-coherence-audit/SKILL.md`

**Scopo:** istruire il modello su come eseguire un audit di coerenza completo del motore SCF senza modificare nulla.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-coherence-audit
description: Esegue un audit di coerenza completo del motore SCF verificando contatori tool, allineamento prompt/tool e consistenza documentazione. Non modifica nulla — riporta solo discrepanze.
---
```

**Contenuto del corpo — procedura operativa:**

Passo 1 — Verifica contatori tool:
- leggere `spark-framework-engine.py`
- contare i tool registrati con `@mcp.tool` in `register_tools()`
- confrontare con il valore dichiarato nel commento della classe `# Tools (N)`
- confrontare con il valore nel log `logger.info("Tools registered: N total")`
- segnalare se i tre valori non coincidono

Passo 2 — Verifica docstring tool:
- per ogni tool registrato verificare che la docstring sia presente e non vuota
- segnalare ogni tool privo di docstring

Passo 3 — Verifica allineamento prompt/tool:
- usare `scf_list_prompts` per ottenere la lista dei prompt disponibili
- per ciascun prompt usare `scf_get_prompt` per leggere il corpo
- estrarre i nomi di tool MCP referenziati nel corpo del prompt
- verificare che ogni tool referenziato esista in `register_tools()`
- segnalare prompt che chiamano tool inesistenti (prompt orfani)

Passo 4 — Verifica coerenza documentazione:
- leggere `README.md` e verificare che il contatore tool dichiarato corrisponda al reale
- leggere `CHANGELOG.md` e verificare che `ENGINE_VERSION` in `spark-framework-engine.py` corrisponda all'ultima voce
- segnalare ogni disallineamento

Passo 5 — Report finale:
- produrre un report strutturato con sezioni: PASS / WARNING / CRITICAL
- per ogni voce CRITICAL o WARNING indicare: file, riga se applicabile, discrepanza trovata, correzione suggerita
- non applicare nessuna correzione autonomamente

**Tool da usare:** `scf_list_prompts`, `scf_get_prompt`, `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati), `readFile`

---

## Artefatto 3 — Skill `scf-changelog`

**Percorso:** `.github/skills/scf-changelog/SKILL.md`

**Scopo:** istruire il modello su come determinare il tipo corretto di bump semantico, compilare una voce CHANGELOG e aggiornare `ENGINE_VERSION`.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-changelog
description: Determina il bump semantico corretto in base alle modifiche recenti, compila la voce CHANGELOG nel formato Keep a Changelog e aggiorna ENGINE_VERSION in spark-framework-engine.py.
---
```

**Contenuto del corpo — procedura operativa:**

Passo 1 — Raccolta modifiche recenti:
- usare `scf_get_framework_version` per leggere la versione corrente
- leggere `CHANGELOG.md` per identificare l'ultima voce rilasciata
- leggere le modifiche recenti a `spark-framework-engine.py` e `.github/` tramite `readFile` o `changes`

Passo 2 — Determinazione bump semantico:
- se ci sono breaking change all'interfaccia MCP o refactor architetturali: bump major
- se ci sono nuovi tool, nuovi prompt, nuove skill o nuovi agenti: bump minor
- se ci sono solo fix, correzioni, aggiornamenti documentazione: bump patch
- in caso di dubbio proporre il bump all'utente con motivazione prima di procedere

Passo 3 — Compilazione voce CHANGELOG:
- formato voce:
  ```
  ## [X.Y.Z] — GG mese AAAA

  ### Added
  - descrizione aggiunta

  ### Changed
  - descrizione modifica

  ### Fixed
  - descrizione fix

  ### Notes
  - note opzionali
  ```
- includere solo le sezioni con almeno una voce
- inserire la nuova voce in cima al file, dopo l'intestazione e prima dell'ultima voce

Passo 4 — Aggiornamento ENGINE_VERSION:
- localizzare la riga `ENGINE_VERSION: str = "X.Y.Z"` in `spark-framework-engine.py`
- proporre la modifica con anteprima del diff e attendere conferma esplicita prima di applicare

**Tool da usare:** `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati), `readFile`, `editFiles`, `changes`

---

## Artefatto 4 — Skill `scf-tool-development`

**Percorso:** `.github/skills/scf-tool-development/SKILL.md`

**Scopo:** istruire il modello sulla procedura completa e sicura per aggiungere o rimuovere tool MCP dal motore.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-tool-development
description: Guida la procedura completa per aggiungere o rimuovere tool MCP dal motore SCF rispettando tutte le convenzioni di naming, struttura e aggiornamento contatori.
---
```

**Contenuto del corpo — procedura aggiunta tool:**

Passo 1 — Verifica pre-aggiunta:
- verificare che il nome proposto rispetti la convenzione: prefisso `scf_`, snake_case, forma `verbo_sostantivo`
- verificare che non esista già un tool con lo stesso nome in `register_tools()`
- verificare che la funzionalità non sia già coperta da un tool esistente

Passo 2 — Implementazione:
- aggiungere il metodo in coda al blocco `register_tools()` di `SparkFrameworkEngine`
- firma: `async def nome_tool(self, parametro: tipo, ...) -> dict[str, Any]:`
- prima riga della docstring: descrizione orientata all'utente in italiano
- corpo: implementazione con gestione errori, ritorno sempre `dict[str, Any]`

Passo 3 — Aggiornamento contatori (obbligatorio, non saltare):
- incrementare N nel commento della classe: `# Tools (N)`
- incrementare N nel log finale: `logger.info("Tools registered: N total")`
- verificare che entrambi i valori siano identici dopo la modifica

Passo 4 — Proposta e conferma:
- mostrare il diff completo della modifica proposta
- attendere conferma esplicita dell'utente prima di applicare
- dopo conferma, applicare con `editFiles`

Passo 5 — Post-aggiunta:
- invocare la skill `scf-changelog` per registrare l'aggiunta come bump minor

**Contenuto del corpo — procedura rimozione tool:**

Passo 1 — Verifica dipendenze:
- usare `scf_list_prompts` e `scf_get_prompt` per ogni prompt disponibile
- verificare che nessun prompt attivo chiami il tool da rimuovere
- se esistono dipendenze: segnalare e bloccare la rimozione finché non vengono risolte

Passo 2 — Rimozione e aggiornamento contatori:
- rimuovere il metodo da `register_tools()`
- decrementare N nel commento della classe e nel log
- verificare allineamento contatori

Passo 3 — Proposta e conferma:
- stessa procedura dell'aggiunta: diff + conferma esplicita prima di applicare

**Tool da usare:** `readFile`, `editFiles`, `scf_list_prompts`, `scf_get_prompt`, `scf_get_workspace_info`

---

## Artefatto 5 — Skill `scf-prompt-management`

**Percorso:** `.github/skills/scf-prompt-management/SKILL.md`

**Scopo:** istruire il modello su come creare, validare e correggere prompt SCF rispettando tutte le convenzioni.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-prompt-management
description: Crea, valida e corregge prompt SCF verificando frontmatter, naming convention, istruzioni operative e regole di conferma.
---
```

**Contenuto del corpo — convenzioni obbligatorie prompt SCF:**

Struttura frontmatter:
```yaml
---
type: prompt
name: scf-nome-azione
description: Descrizione orientata all'utente finale, senza riferimenti tecnici interni.
---
```

Regole corpo:
- le istruzioni operative devono nominare esplicitamente i tool MCP da chiamare — sono istruzioni al modello
- il testo visibile all'utente finale (output del prompt) non deve contenere nomi di tool MCP
- tutti i prompt che modificano file nel workspace devono includere una richiesta di conferma (sì/no) prima di procedere
- i prompt distruttivi devono elencare i file che verranno preservati per modifica manuale

**Procedura creazione nuovo prompt:**

Passo 1: verificare che non esista già un prompt con lo stesso `name` tramite `scf_list_prompts`
Passo 2: determinare i tool necessari verificando che esistano tutti in `register_tools()`
Passo 3: costruire il frontmatter con `type`, `name`, `description`
Passo 4: costruire il corpo con istruzioni operative esplicite al modello
Passo 5: proporre il file completo all'utente e attendere conferma prima di creare

**Procedura validazione prompt esistente:**

Passo 1: usare `scf_get_prompt` per leggere il prompt
Passo 2: verificare frontmatter — presenza e correttezza di `type`, `name`, `description`
Passo 3: verificare naming del file — `scf-{azione}.prompt.md`, tutto minuscolo, trattini
Passo 4: verificare che ogni tool nominato nelle istruzioni esista nel motore
Passo 5: verificare presenza richiesta di conferma se il prompt modifica file
Passo 6: produrre report con PASS / WARNING / CRITICAL per ogni voce verificata

**Tool da usare:** `scf_list_prompts`, `scf_get_prompt`, `editFiles`, `readFile`

---

## Artefatto 6 — Skill `scf-release-check`

**Percorso:** `.github/skills/scf-release-check/SKILL.md`

**Scopo:** istruire il modello su come eseguire la checklist pre-release completa e proporre il tag git corretto.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-release-check
description: Esegue la checklist pre-release del motore SCF verificando coerenza interna, CHANGELOG, versione e README. Propone il tag git da creare senza applicarlo autonomamente.
---
```

**Contenuto del corpo — checklist pre-release:**

Passo 1 — Coerenza interna (delegare a skill `scf-coherence-audit`):
- invocare la procedura di audit completo
- bloccare il rilascio se esistono voci CRITICAL nel report

Passo 2 — Verifica CHANGELOG:
- leggere `CHANGELOG.md`
- verificare che esista una voce `[Unreleased]` oppure una voce con la versione corrente
- verificare che la voce documenti le modifiche effettivamente presenti nel codice
- segnalare se il CHANGELOG è vuoto o non aggiornato

Passo 3 — Allineamento ENGINE_VERSION:
- usare `scf_get_framework_version` per leggere la versione corrente
- confrontare con l'ultima voce di `CHANGELOG.md`
- segnalare se non sono allineate

Passo 4 — Verifica README:
- leggere `README.md`
- verificare che il contatore tool dichiarato corrisponda al numero reale in `register_tools()`
- verificare che il contatore resource dichiarato corrisponda al numero reale in `register_resources()`
- segnalare ogni disallineamento

Passo 5 — Verifica TODO/placeholder:
- cercare in `spark-framework-engine.py` occorrenze di `TODO`, `FIXME`, `HACK`, `XXX`, `pass` in posizioni non attese
- segnalare ogni occorrenza trovata con file e riga

Passo 6 — Proposta tag git:
- se tutti i controlli passano: proporre il comando `git tag vX.Y.Z` con il numero di versione corretto
- non eseguire il tag autonomamente — proporre e attendere conferma esplicita dell'utente
- ricordare che dopo il tag va fatto `git push --tags`

**Tool da usare:** `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati), `scf_list_prompts`, `readFile`, `runCommand` (solo lettura: `git log --oneline -10`, `git status`, `git tag`)

---

## Artefatto 7 — Skill `scf-documentation`

**Percorso:** `.github/skills/scf-documentation/SKILL.md`

**Scopo:** istruire il modello su come mantenere sincronizzati i file di design e pianificazione con l'implementazione reale.

**Frontmatter obbligatorio:**
```yaml
---
name: scf-documentation
description: Mantiene sincronizzati README, file di design e piani di progetto con lo stato reale dell'implementazione del motore SCF.
---
```

**Contenuto del corpo — procedure operative:**

Procedura aggiornamento README:
- leggere `README.md` e `spark-framework-engine.py`
- aggiornare il contatore tool con il valore reale da `register_tools()`
- aggiornare il contatore resource con il valore reale da `register_resources()`
- aggiornare la lista dei tool disponibili se sono stati aggiunti o rimossi tool
- proporre il diff e attendere conferma prima di applicare

Procedura aggiornamento SCF-PROJECT-DESIGN.md:
- invocare solo quando l'architettura del motore cambia in modo sostanziale
- leggere il file corrente e identificare le sezioni da aggiornare
- non riscrivere sezioni ancora accurate
- proporre solo le modifiche necessarie con diff e attendere conferma

Procedura gestione piani `*-PLAN.md`:
- dopo il completamento di un piano: aggiungere una sezione "Stato finale" con data e esito
- non eliminare i piani completati — archiviarli aggiungendo il prefisso `DONE-` al nome file
- se un piano è parzialmente completato: aggiornare lo stato dei singoli item con `[x]` / `[ ]`

Regola generale:
- non modificare mai documentazione autonomamente
- segnalare sempre i disallineamenti trovati prima di proporre correzioni
- proporre sempre diff + conferma esplicita prima di applicare qualsiasi modifica

**Tool da usare:** `readFile`, `editFiles`, `fetch`, `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati)

---

## Artefatto 8 — File agente

**Percorso:** `.github/agents/spark-engine-maintainer.agent.md`

**Frontmatter obbligatorio:**
```yaml
---
name: spark-engine-maintainer
description: Agente specializzato nella manutenzione, evoluzione e coerenza del motore spark-framework-engine. Gestisce versioni, CHANGELOG, audit di coerenza, sviluppo tool MCP, gestione prompt e documentazione.
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

**Contenuto del corpo — sezioni obbligatorie:**

Sezione 1 — Identità e perimetro:
- nome: spark-engine-maintainer
- repo operativo: spark-framework-engine
- non interviene su workspace utente, non gestisce pacchetti SCF installati altrove
- non esegue operazioni su altri repository

Sezione 2 — Responsabilità e skill associate:
- gestione versioni e CHANGELOG → skill `scf-changelog`
- audit di coerenza interna → skill `scf-coherence-audit`
- sviluppo e manutenzione tool MCP → skill `scf-tool-development`
- creazione e validazione prompt → skill `scf-prompt-management`
- processo di rilascio → skill `scf-release-check`
- aggiornamento documentazione → skill `scf-documentation`

Sezione 3 — Regole operative generali:
- non modificare mai file senza conferma esplicita dell'utente
- proporre sempre il diff atteso prima di applicare modifiche a `spark-framework-engine.py`
- in operazioni distruttive: elencare sempre i file che verranno preservati
- usare `runCommand` solo per comandi di sola lettura: `git log`, `git status`, `git tag`, `git diff`
- non eseguire `git push`, `git commit` o creazione tag in autonomia

Sezione 4 — Comportamento su richieste ambigue:
- se la richiesta riguarda sia il motore che un workspace utente: chiedere chiarimento prima di procedere
- se la richiesta potrebbe causare breaking change: segnalarlo esplicitamente e attendere conferma

---

## Artefatto 9 — copilot-instructions.md

**Percorso:** `.github/copilot-instructions.md`

**Scopo:** punto di ingresso globale per Copilot in questo repo. Deve essere sintetico — le istruzioni operative vivono nei file dedicati, qui ci sono solo i riferimenti e le regole di ingaggio.

**Contenuto obbligatorio:**

Sezione 1 — Contesto repo:
- questo repo è il motore MCP universale del SPARK Code Framework
- linguaggio: Python 3.11+
- framework MCP: FastMCP
- file principale: `spark-framework-engine.py`

Sezione 2 — Quando usare `@spark-engine-maintainer`:
- per eseguire audit di coerenza interna del motore
- per aggiungere o rimuovere tool MCP
- per creare o modificare prompt in `.github/prompts/`
- per aggiornare CHANGELOG e versione dopo modifiche
- per eseguire la checklist pre-release e preparare un tag
- per aggiornare README e documentazione di design

Sezione 3 — Cosa NON delegare a `@spark-engine-maintainer`:
- operazioni su workspace utente (installazione pacchetti SCF, configurazione progetti)
- sviluppo di feature non legate al motore SCF stesso
- operazioni su altri repository

Sezione 4 — Riferimento istruzioni operative:
- convenzioni codice motore: `.github/instructions/spark-engine-maintenance.instructions.md`
- skill disponibili: `.github/skills/scf-*/SKILL.md`

---

## Istruzioni operative per Copilot

Implementa tutti e 9 gli artefatti descritti in questo piano nell'ordine indicato nella sezione "Ordine di implementazione obbligatorio".

Per ciascun artefatto:
- crea il file nel percorso esatto indicato
- usa il frontmatter esatto indicato nella sezione dell'artefatto
- il corpo del file deve contenere tutte le sezioni e procedure descritte, scritte in modo operativo e direttamente utilizzabile dal modello — non sintesi, non riferimenti vaghi
- non creare directory vuote: crea direttamente i file con il loro contenuto

Vincoli:
- non toccare nulla in `.github/prompts/` — quei file esistono già e sono corretti
- non modificare `spark-framework-engine.py`
- non modificare `CHANGELOG.md`, `README.md` o altri file esistenti nella root
- creare solo i file elencati in questo piano, nient'altro

Dopo aver creato tutti i file, esegui la suite di test completa con `pytest -q` e riporta l'esito. Se i test passano, il lavoro è completo.

---

## Criteri di accettazione (Definition of Done)

- [ ] `.github/instructions/spark-engine-maintenance.instructions.md` creato con tutte le sezioni A-E
- [ ] `.github/skills/scf-coherence-audit/SKILL.md` creato con procedura in 5 passi
- [ ] `.github/skills/scf-changelog/SKILL.md` creato con procedura in 4 passi
- [ ] `.github/skills/scf-tool-development/SKILL.md` creato con procedure aggiunta e rimozione
- [ ] `.github/skills/scf-prompt-management/SKILL.md` creato con procedure creazione e validazione
- [ ] `.github/skills/scf-release-check/SKILL.md` creato con checklist in 6 passi
- [ ] `.github/skills/scf-documentation/SKILL.md` creato con 3 procedure operative
- [ ] `.github/agents/spark-engine-maintainer.agent.md` creato con frontmatter e 4 sezioni corpo
- [ ] `.github/copilot-instructions.md` creato con 4 sezioni
- [ ] suite test verde dopo la creazione (nessuna regressione attesa — i nuovi file sono `.md`, non Python)
