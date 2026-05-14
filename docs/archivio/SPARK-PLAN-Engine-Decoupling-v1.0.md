> **STATO: COMPLETATO** — Archiviato il 2026-05-14 (ENGINE_VERSION 3.6.0).
> Documento di sola lettura. Non modificare.

***

<!-- markdownlint-disable MD022 MD032 MD036 MD060 -->

# Piano Tecnico — Disaccoppiamento spark-base → spark-ops
## Versione: 1.0.0 — 2026-05-09
## Branch: `feature/dual-mode-manifest-v3.1`
## Autore analisi: GitHub Copilot (spark-engine-maintainer)
## Commissionato da: Nemex81 / Perplexity AI
## Prompt sorgente: `packages/spark-base/.github/prompts/spark-engine-decoupling-validation.prompt.md`

---

## 1. Obiettivo

Valutare e pianificare il disaccoppiamento dei componenti di `spark-base`
non strettamente connessi all'interazione utente, spostando il sottoinsieme
system-facing in un nuovo package autonomo.

L'obiettivo principale è ridurre il catalogo di `spark-base` ai soli componenti
genuinamente user-facing, rendendo più chiara la separazione concettuale tra:

- ciò che serve all'utente nel suo workflow quotidiano
- ciò che serve al ciclo interno di mantenimento del framework

---

## 2. Verdetto sulla Strategia Originale

**ESITO: FAIL — Blocco architetturale doppio**

### Blocco 1 — Naming conflict

Il nome `spark-engine` proposto crea ambiguità diretta con il repository
`spark-framework-engine` e con il server Python MCP che è già chiamato
informalmente "engine" in tutta la documentazione. Un package chiamato
`spark-engine` farebbe credere agli utenti di stare installando il motore
stesso, non un layer di estensione framework.

### Blocco 2 — Dipendenze inverse per le skill

Alcune skill in `spark-base` candidate alla migrazione (es. `git-execution`,
`file-deletion-guard`, `changelog-entry`, `conventional-commit`) sono usate
da agenti che DEVONO restare in `spark-base` (es. `Agent-Git`). Se queste
skill migrassero in `spark-engine`, `spark-base` dovrebbe dichiarare
`spark-engine` come dipendenza, invertendo la gerarchia: spark-engine
diventerebbe il layer base, non un'estensione. Questo contraddice l'intenzione
della strategia originale.

### Blocco 3 — spark-welcome come dispatcher

`spark-welcome` non esiste come package autonomo. Esiste `Agent-Welcome` in
`spark-base` (project setup) e `spark-welcome` come agente in the engine workspace.
Il perimetro di un `spark-welcome` dispatcher si sovrapporrebbe con:
- `spark-assistant` (routing verso operazioni operative)
- `spark-guide` (orientamento framework)
Un terzo agente dispatcher creerebbe ridondanza cognitiva senza aggiungere valore.

### Blocco 4 — Nessuna separazione tecnica reale per le skill MCP

Tutte le risorse MCP (agents, skills, instructions, prompts) sono servite dallo
STESSO server `spark-framework-engine`. Dividere il catalogo tra due package
`spark-base` e `spark-engine` non introduce separazione tecnica: la skill è
comunque accessibile via `skills://nome` indipendentemente dal package in cui
risiede. Il costo di gestione (due versioni, due dipendenze, aggiornamenti
sincronizzati) non è giustificato dal beneficio.

---

## 3. Strategia Adottata — Alternativa PASS

**ESITO: PASS CONDIZIONALE**

### 3.1 Cambio di nome

Il package proposto si chiama `spark-ops` (non `spark-engine`) per eliminare
l'ambiguità con il server MCP. Il nome riflette il contenuto: componenti
del ciclo operativo del framework (orchestrazione, release, manutenzione documentazione).

### 3.2 Perimetro di migrazione ristretto

Solo i componenti che soddisfano ENTRAMBE le condizioni seguenti possono migrare:
1. Non sono necessari a nessun componente che rimane in `spark-base`
2. Servono esclusivamente al ciclo interno di framework maintenance / E2E cycle

### 3.3 spark-welcome rimane Agent-Welcome

`Agent-Welcome` rimane in `spark-base` con il suo ruolo attuale (project setup).
Non diventa dispatcher. Il perimetro viene chiarito documentalmente ma non modificato.

### 3.4 Giustificazione del beneficio reale

- `spark-base` si concentra sull'esperienza utente: installazione, onboarding, workflow progetto
- `spark-ops` diventa il layer per i maintainer del framework: orchestrazione E2E, release management, framework documentation
- I pacchetti plugin (`scf-master-codecrafter`) dichiarano `spark-ops` come dipendenza
  opzionale solo se usano gli agenti del ciclo E2E

---

## 4. Componenti da Migrare a spark-ops

### 4.1 Agenti

| Agente | Motivazione migrazione |
|--------|----------------------|
| `Agent-Orchestrator` | Usato solo nel ciclo E2E interno, non nel workflow utente |
| `Agent-FrameworkDocs` | Esclusivamente per manutenzione documentazione framework |
| `Agent-Release` | Esclusivamente per versioning e release del framework |
| `Agent-Research` | Agente di fallback/meta, non user-facing diretto |

### 4.2 Skill

Solo le skill usate ESCLUSIVAMENTE da agenti che migrano:

| Skill | Motivazione migrazione |
|-------|----------------------|
| `semantic-gate` | Usata da Agent-Orchestrator (che migra) |
| `rollback-procedure` | Usata nel ciclo E2E orchestrato |
| `error-recovery` | Usata da Agent-Orchestrator |
| `framework-scope-guard` | Usata da Agent-Orchestrator e Agent-FrameworkDocs |
| `task-scope-guard` | Usata nel ciclo E2E |
| `semver-bump` | Usata da Agent-Release (che migra) |

### 4.3 Prompt

| Prompt | Motivazione migrazione |
|--------|----------------------|
| `orchestrate` | Trigger per Agent-Orchestrator |
| `release` | Trigger per Agent-Release |
| `framework-changelog` | Framework maintenance |
| `framework-release` | Framework release cycle |
| `framework-unlock` | Framework maintenance |
| `framework-update` | Framework maintenance |

### 4.4 Instructions

**Nessuna instruction migra.**

Tutte le instruction attuali di `spark-base` (framework-guard, git-policy, model-policy,
personality, project-reset, spark-assistant-guide, verbosity, workflow-standard) sono
necessarie agli agenti e ai componenti che rimangono in spark-base oppure si applicano
tramite `applyTo: '**'` a tutto il workspace. Migrarle spezzerebbe il comportamento
di Copilot nel workspace utente.

---

## 5. Componenti da Lasciare in spark-base

### 5.1 Agenti — NON MIGRANO

| Agente | Motivazione |
|--------|-------------|
| `spark-assistant` | Punto di contatto primario utente finale — invariante |
| `spark-guide` | Orientamento utente — invariante |
| `Agent-Welcome` | Project setup utente — invariante |
| `Agent-Analyze` | Usato attivamente nei workflow utente e da plugin |
| `Agent-Plan` | Usato nei workflow utente e da plugin |
| `Agent-Docs` | Sincronizzazione documentazione progetto utente |
| `Agent-Git` | Git operations — usato da tutti i workflow utente |
| `Agent-Helper` | Orientamento framework — user-facing |
| `Agent-Validate` | Validazione progetto utente |

### 5.2 Skill — NON MIGRANO

| Skill | Motivazione |
|-------|-------------|
| `git-execution` | Usata da Agent-Git (rimane in spark-base) |
| `file-deletion-guard` | Usata da Agent-Git |
| `changelog-entry` | Usata da Agent-Git nel workflow utente |
| `conventional-commit` | Usata da Agent-Git |
| `framework-index` | Usata da Agent-Helper (user-facing) |
| `framework-query` | Usata da Agent-Helper |
| `project-profile` | Usata da Agent-Welcome e nel workflow utente |
| `project-doc-bootstrap` | User-facing |
| `project-reset` | User-facing |
| `document-template` | User-facing |
| `style-setup` | User-facing |
| `personality` | UX/presentazione |
| `verbosity` | UX/presentazione |
| `accessibility-output` | User-facing |
| `validate-accessibility` | User-facing |
| `agent-selector` | Meta-skill di routing — necessaria a tutti gli agenti |

### 5.3 Instructions — NON MIGRANO

Tutte le 8 instruction rimangono in `spark-base` (vedi §4.4).

### 5.4 Prompt — NON MIGRANO

Tutti i prompt user-facing rimangono in `spark-base`:
`help`, `init`, `start`, `status`, `project-setup`, `project-update`,
`git-commit`, `git-merge`, `sync-docs`, `personality`, `verbosity`,
tutti i `scf-*` (package management).

---

## 6. Nuovo Package — spark-ops

### 6.1 Perimetro

| Campo | Valore |
|-------|--------|
| Package ID | `spark-ops` |
| Path fisico | `packages/spark-ops/` |
| Version iniziale | `1.0.0` |
| delivery_mode | `mcp_only` |
| schema_version | `3.1` |
| Dipendenze | `spark-base >= 1.7.3` |
| min_engine_version | `3.3.0` |

### 6.2 Responsabilità

`spark-ops` fornisce:
- Gli agenti del ciclo E2E (Orchestrator, FrameworkDocs, Release, Research)
- Le skill del ciclo operativo interno (orchestrazione, release, error handling)
- I prompt di framework maintenance (framework-*, orchestrate, release)

`spark-ops` NON fornisce:
- Componenti user-facing
- Agenti di workflow progetto
- Skill usate da agenti user-facing

### 6.3 Dipendenza inversa

`scf-master-codecrafter` e `scf-pycode-crafter` non devono dichiarare `spark-ops`
come dipendenza obbligatoria. I loro agenti dispatcher (code-Agent-Orchestrator, ecc.)
sono definiti autonomamente e non ereditano direttamente da Agent-Orchestrator via MCP.
Se un pacchetto vuole usare Agent-Orchestrator dalla sua versione spark-ops, può
aggiungere `spark-ops` come dipendenza opzionale — ma non è richiesto per funzionare.

---

## 7. Impatti Previsti

### 7.1 Onboarding nuovo utente

**Impatto: BASSO**

`spark-ops` è opzionale per l'utente finale. Il bootstrap automatico installa
solo `spark-base`. `spark-ops` viene installato esplicitamente da chi gestisce
il framework o da plugin che lo dichiarano come dipendenza.

### 7.2 Bootstrap workspace vergine

**Impatto: NULLO**

`spark-base` rimane il package bootstrap. `spark-ops` è un package separato
installato solo se necessario. La sentinella di bootstrap (`spark-assistant.agent.md`)
non è toccata.

### 7.3 Documentazione utente

**Impatto: MEDIO**

`README.md`, `docs/architecture.md` devono essere aggiornati per spiegare
la nuova distinzione `spark-base` / `spark-ops`. La narrativa dual-universe
(Universo A / Universo B) si arricchisce di un terzo livello: pacchetti base
(spark-base) vs pacchetti operativi framework (spark-ops).

### 7.4 Suite di test

**Impatto: MEDIO**

- Nuovi test per il package-manifest di spark-ops
- Aggiornamento test che verificano il catalogo agenti di spark-base
- Nessun test core del motore deve essere modificato (boot, lifecycle, manifest)

### 7.5 Skill informative comuni

**Impatto: NULLO**

Le skill informative (`framework-index`, `framework-query`) rimangono in
`spark-base`. Non vengono duplicate né spostate. Il principio di "unica fonte
di verità" è rispettato.

---

## 8. Fasi Operative

### Fase 1 — Analisi e preparazione

**Obiettivo:** Verificare l'inventario completo e identificare dipendenze nascoste.

**Attività:**
1. Elencare tutti i componenti di `spark-base` con classificazione USER-FACING / SYSTEM-FACING
2. Verificare ogni skill candidate per dipendenze da agenti che rimangono in spark-base
3. Verificare ogni agente candidate per dipendenze da skill che rimangono in spark-base
4. Documentare le dipendenze verificate in un file di analisi

**Criterio di uscita:** Lista definitiva dei componenti da migrare, senza dipendenze incrociate

**Rischi:** Dipendenze nascoste non documentate nelle agent definition

### Fase 2 — Creazione package spark-ops

**Obiettivo:** Creare la struttura del nuovo package in `packages/spark-ops/`

**Attività:**
1. Creare `packages/spark-ops/` con struttura `.github/` parallela a spark-base
2. Creare `packages/spark-ops/package-manifest.json` con:
   - schema_version: "3.1"
   - delivery_mode: "mcp_only"
   - dependencies: ["spark-base"]
   - mcp_resources: solo i componenti selezionati
3. Non copiare ancora i file — solo il manifest

**Criterio di uscita:** package-manifest.json valido e coerente

**Rischi:** Errori nel manifest che impediscono il caricamento del package

### Fase 3 — Spostamento dei componenti selezionati

**Obiettivo:** Copiare i file dai path di spark-base ai path di spark-ops

**Attività:**
1. Creare le cartelle `agents/`, `prompts/`, `skills/` in `packages/spark-ops/.github/`
2. Copiare (non eliminare) i file degli agenti candidate
3. Copiare le skill candidate
4. Copiare i prompt candidate
5. Aggiornare il frontmatter di ogni file copiato:
   - `scf_owner: spark-ops`
   - versione invariata fino alla validazione

**Nota importante:** I file rimangono ANCHE in spark-base durante questa fase.
L'eliminazione da spark-base avviene solo nella Fase 4, dopo validazione.

**Criterio di uscita:** Tutti i file presenti in spark-ops con frontmatter aggiornato

### Fase 4 — Pulizia di spark-base

**Obiettivo:** Rimuovere da spark-base i componenti migrati in spark-ops

**Attività:**
1. Rimuovere i file migrati da `packages/spark-base/.github/`
2. Aggiornare `packages/spark-base/package-manifest.json`:
   - Rimuovere componenti migrati da `mcp_resources`
   - Rimuovere file migrati dalla lista `files`
3. Bumping semantico di spark-base (minor version)

**Criterio di uscita:** spark-base manifest coerente senza componenti migrati

**Rischi:** Rimozione accidentale di componenti NON candidati alla migrazione

### Fase 5 — Aggiornamento dipendenze pacchetti esistenti

**Obiettivo:** Verificare che scf-master-codecrafter e scf-pycode-crafter
funzionino correttamente senza modifiche obbligatorie

**Attività:**
1. Verificare che scf-master-codecrafter non dipenda direttamente da componenti migrati
2. Se dipendenze esistono: valutare se aggiungere spark-ops come dipendenza OPZIONALE
3. Aggiornare i CHANGELOG dei pacchetti toccati

**Criterio di uscita:** Test dei pacchetti dipendenti invariati o corretti

### Fase 6 — Aggiornamento documentazione

**Obiettivo:** Allineare README, architecture.md, api.md al nuovo stato

**Attività:**
1. Aggiornare `docs/architecture.md` sezione "Componenti Principali"
2. Aggiornare `README.md` con la nuova distinzione spark-base / spark-ops
3. Creare `packages/spark-ops/README.md` con descrizione e use case
4. Aggiornare `CHANGELOG.md` con la sezione per questa migrazione

**Criterio di uscita:** Documentazione coerente con il nuovo stato

### Fase 7 — Verifica test e regressioni

**Obiettivo:** Suite di test invariata o migliorata

**Attività:**
1. Eseguire `python -m pytest -q --ignore=tests/test_integration_live.py`
2. Verificare che il contatore agenti/skill/prompt nei test sia aggiornato
3. Aggiungere test per il package-manifest di spark-ops
4. Verificare test di bootstrap (sentinella spark-assistant.agent.md invariata)

**Criterio di uscita:** Suite non-live PASS, nessuna regressione

### Fase 8 — Validazione finale e bump versione engine

**Obiettivo:** Confermare la coerenza del sistema nel suo completo

**Attività:**
1. Eseguire `python scripts/validate_gates.py` se disponibile
2. Verificare che spark-ops sia caricabile come package dall'engine
3. Verificare che i tool MCP di lettura risorse restituiscano i componenti di spark-ops
4. Proporre bump ENGINE_VERSION (minor: es. 3.3.0 → 3.4.0)
5. Proporre tag git via Agent-Git

**Criterio di uscita:** PASS su tutti i check, versione aggiornata, comandi git proposti

---

## 9. Rischi e Mitigazioni

| Fase | Rischio | Probabilità | Impatto | Mitigazione |
|------|---------|-------------|---------|-------------|
| 2 | Manifest spark-ops invalido | BASSA | ALTO | Validare con engine prima di procedere |
| 3 | Frontmatter scf_owner errato | MEDIA | MEDIO | Check automatico via grep post-copia |
| 4 | Eliminazione erronea da spark-base | BASSA | ALTO | Lavorare su branch dedicato, non su feature branch attivo |
| 5 | Dipendenza nascosta in scf-master-codecrafter | MEDIA | MEDIO | Leggere ogni agente code-Agent-* prima della Fase 4 |
| 6 | Documentazione incompleta | MEDIA | BASSO | Checklist documentazione da docs-manager skill |
| 7 | Regressione sui test di bootstrap | BASSA | ALTO | Eseguire test bootstrap-focused prima della suite completa |
| 8 | spark-ops non rilevato dall'engine | BASSA | ALTO | Verificare install flow in ambiente locale prima del merge |

---

## 10. Dipendenze e Prerequisiti

### Prerequisiti tecnici

- Il branch `feature/dual-mode-manifest-v3.1` deve essere in stato VERDE (test PASS)
- La suite non-live deve passare prima di iniziare qualsiasi modifica
- L'engine deve essere alla versione >= 3.3.0 (schema 3.1 supportato)

### Prerequisiti organizzativi

- Approvazione esplicita da Nemex81 prima della Fase 4 (eliminazione da spark-base)
- Verifica manuale della lista definitiva componenti candidati (Fase 1)

### Ordine sicuro di esecuzione

Le fasi NON sono parallelizzabili. Devono essere eseguite in sequenza.
Ogni fase richiede il PASS della precedente prima di procedere.

---

## 11. Decisioni Aperte

### DA-1 — Naming spark-ops

Il nome `spark-ops` è una proposta alternativa al `spark-engine` originale.
Nemex81 deve confermare il nome definitivo prima della Fase 2.

**Opzioni:**
- `spark-ops` (raccomandato — chiaro e non ambiguo)
- `spark-cycle` (alternativo — enfatizza il ciclo E2E)
- `spark-framework-ops` (alternativo — disambigua ulteriormente)

### DA-2 — Agent-Research

`Agent-Research` è classificato come SYSTEM-FACING perché è un agente di
fallback meta-layer. Tuttavia potrebbe essere usato da utenti avanzati
direttamente. Se si vuole mantenerlo user-accessible, rimane in spark-base.
**Decisione richiesta a Nemex81.**

### DA-3 — Inclusione in scf-master-codecrafter

`scf-master-codecrafter` dovrà essere aggiornato per dichiarare `spark-ops`
come dipendenza se vuole che i suoi agenti dispatcher facciano riferimento
agli agenti di spark-ops? **Dipende dall'uso effettivo** — verificare in Fase 5.

### DA-4 — Versione iniziale di spark-ops

La versione 1.0.0 implica che spark-ops è un package nuovo. Dovrebbe seguire
la stessa versione di spark-base (1.7.3) per indicare allineamento?
**Preferenza di Nemex81 richiesta.**

---

## 12. Conclusione Tecnica

### Verdetto sulla strategia originale

**FAIL** — La strategia originale presenta due blocchi architetturali non superabili:
naming conflict con `spark-framework-engine` e dipendenze inverse per le skill.
`spark-welcome` come dispatcher è un blocco architetturale aggiuntivo.

### Verdetto sulla strategia alternativa

**PASS CONDIZIONALE** — La strategia alternativa con package `spark-ops` è
tecnicamente fattibile e semanticamente pulita. Il beneficio reale è moderato
(4 agenti, 6 skill, 6 prompt migrano su base più ampia) ma porta un vantaggio
concettuale netto: chi usa SPARK per sviluppo progetti non vede il layer di
framework maintenance; chi mantiene il framework ha un package dedicato.

### Raccomandazione

Si raccomanda di procedere con la strategia alternativa `spark-ops` **dopo**:
1. Conferma del nome da parte di Nemex81 (DA-1)
2. Decisione su Agent-Research (DA-2)
3. Completamento del merge di `feature/dual-mode-manifest-v3.1` su `main`
4. Suite non-live in stato VERDE stabile

**Non procedere** prima del merge del branch corrente — aggiungere modifiche
strutturali al catalogo pacchetti in un branch già complesso aumenterebbe
il rischio di regressione.

---

*Fine Piano Tecnico v1.0.0*
