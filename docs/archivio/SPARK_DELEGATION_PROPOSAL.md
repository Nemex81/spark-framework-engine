# SPARK Engine — Proposta di Modifica: Delegazione Skill e Instructions al Server MCP

> **Documento di validazione per Copilot Agent Mode (claude-opus-4-7)**
> Repo di riferimento: `spark-framework-engine`, `spark-base`, `scf-master-codecrafter`
> Data: 2026-04-22 | Versione proposta: engine → 2.2.0 | spark-base → 1.3.0

---

## Istruzioni Operative per Copilot (LEGGERE PRIMA DI TUTTO)

Questo documento è una **proposta di refactoring architetturale** per l'ecosistema SPARK MCP Server.
Il tuo compito è articolato in **tre fasi sequenziali obbligatorie**:

1. **ANALISI** — Leggi l'intera proposta, poi analizza i file reali nei repository indicati verificando
   che le asserzioni strutturali siano corrette. Se trovi discrepanze, segnalale con precisione prima
   di procedere.
2. **VALIDAZIONE** — Valuta la fattibilità tecnica di ogni punto della proposta. Per ciascun gruppo
   di modifiche, indica esplicitamente: `✅ VALIDATO`, `⚠️ VALIDATO CON CAVEAT` o `❌ NON FATTIBILE`
   con motivazione. Se hai domande aperte che cambiano la strategia, ponile TUTTE prima di
   implementare qualsiasi cosa.
3. **IMPLEMENTAZIONE** — Solo dopo che la validazione è completa e approvata dall'utente, procedi
   con le modifiche nell'ordine indicato. Non implementare più di un gruppo per volta senza conferma.

**REGOLA CRITICA — Integrità stdout/stderr:** Il canale MCP dell'engine usa `stdio` per JSON-RPC.
Non modificare MAI `spark-framework-engine.py` con `print()` su stdout. Ogni logging va su `sys.stderr`
con formato `[SPARK-ENGINE][LIVELLO] messaggio`.

**REGOLA CRITICA — ManifestManager:** Ogni file aggiunto, spostato o rimosso dal `.github/` dell'engine
deve essere tracciato dal `ManifestManager`. Non bypassare questa classe.

---

## 1. Contesto e Obiettivo

### Il Problema

Il pacchetto `spark-base` (v1.2.0) è il prerequisito fondazionale che ogni utente deve installare
nel proprio workspace `.github/`. Attualmente contiene due categorie di asset:

- **Asset contestuali** — skill e instruction che dipendono dal contesto del progetto specifico
  dell'utente (es. `project-profile`, `mcp-context`).
- **Asset universali** — skill e instruction con contenuto normativo invariante (es. `personality`,
  `conventional-commit`, `framework-guard`) che sono identiche in OGNI workspace e in OGNI progetto.

Gli asset universali vivono nel pacchetto utente per ragioni storiche, non architetturali. Questa
scelta causa tre problemi concreti:
1. **Peso del pacchetto**: il bootstrap installa file ridondanti.
2. **Deriva di versione**: se l'engine aggiorna una policy (es. `git-policy`), il workspace utente
   rimane alla versione installata finché non reinstalla manualmente.
3. **Duplicazione**: `spark-base` e `scf-master-codecrafter` contengono copie identiche delle stesse
   skill, il che è una violazione diretta del principio DRY.

### La Soluzione

Replicare il modello già funzionante per i **prompt di inizializzazione** e per gli **agenti
`spark-assistant` e `spark-guide`**: questi risiedono nel `.github/` dell'engine e vengono esposti
via MCP come risorse `prompts://` e `agents://`. Gli agenti nel workspace utente li invocano
tramite MCP senza bisogno di copie locali.

Il medesimo meccanismo si applica agli asset universali tramite gli URI `skills://` e
`instructions://` già definiti nell'architettura SPARK (schema v2.0 del registry).

---

## 2. Inventario degli Asset: Classificazione

### 2.1 Skill attualmente in `spark-base/.github/skills/`

| Asset | Tipo | Classificazione | Motivazione |
|---|---|---|---|
| `accessibility-output.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Regola comportamentale universale di output accessibile. Invariante. |
| `agent-selector.skill.md` | flat file | 🟡 CONTESTUALE | Dipende dagli agenti *installati* nel workspace. Non delegabile. |
| `changelog-entry/` | directory | 🔴 DELEGABILE AL SERVER | Procedura standard Git, universale. |
| `conventional-commit.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Standard Conventional Commits, mai cambia per progetto. |
| `document-template.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Template documenti universale. |
| `error-recovery/` | directory | 🔴 DELEGABILE AL SERVER | Policy di error recovery, universale. |
| `file-deletion-guard.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Guard di sicurezza del framework stesso. Paradossale nel pacchetto utente. |
| `framework-guard.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Idem: protegge il framework, deve vivere nel framework. |
| `framework-index/` | directory | 🔴 DELEGABILE AL SERVER | Procedura di indicizzazione engine, universale. |
| `framework-query/` | directory | 🔴 DELEGABILE AL SERVER | Procedura di query engine, universale. |
| `framework-scope-guard.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Guard di scope, universale. |
| `git-execution.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Esecuzione comandi Git standard. |
| `personality.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Comportamento agente, universale per definizione. |
| `project-doc-bootstrap/` | directory | 🟡 CONTESTUALE | Genera doc specifiche del progetto utente. Non delegabile. |
| `project-profile.skill.md` | flat file | 🟡 CONTESTUALE | Legge `project-profile.md` del workspace. Non delegabile. |
| `project-reset.skill.md` | flat file | 🟡 CONTESTUALE | Procedura reset specifica del workspace utente. |
| `rollback-procedure.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Procedura rollback Git standard. |
| `semantic-gate.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Gate semantico universale. |
| `semver-bump.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | SemVer standard, mai specifico per progetto. |
| `style-setup.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Setup stile universale. |
| `task-scope-guard.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Guard universale di scope task. |
| `validate-accessibility/` | directory | 🔴 DELEGABILE AL SERVER | Validazione accessibilità, procedurale e universale. |
| `verbosity.skill.md` | flat file | 🔴 DELEGABILE AL SERVER | Comportamento verbosità agente, universale. |

**Riepilogo**: 18 asset delegabili, 5 contestuali.

### 2.2 Instructions attualmente in `spark-base/.github/instructions/`

| File | Classificazione | Motivazione |
|---|---|---|
| `framework-guard.instructions.md` | 🔴 DELEGABILE | Policy framework invariante. |
| `git-policy.instructions.md` | 🔴 DELEGABILE | Policy Git universale (mai specifica del progetto). |
| `mcp-context.instructions.md` | 🟡 CONTESTUALE | Lista i tool MCP disponibili nell'installazione utente. |
| `model-policy.instructions.md` | 🔴 DELEGABILE | Policy modello AI, universale. |
| `personality.instructions.md` | 🔴 DELEGABILE | Comportamento agente. |
| `verbosity.instructions.md` | 🔴 DELEGABILE | Verbosità agente. |
| `workflow-standard.instructions.md` | 🔴 DELEGABILE | Standard workflow, universale. |

**Riepilogo**: 6 instruction delegabili, 1 contestuale.

---

## 3. Architettura della Soluzione

### 3.1 Cosa Cambia nell'Engine (`spark-framework-engine`)

Gli 18 skill-file e le 6 instruction delegate vengono aggiunti al `.github/` dell'engine nelle
rispettive sottocartelle. Già oggi l'engine espone via MCP le risorse con questi URI:

```
skills://     → .github/skills/<nome>.skill.md (o directory)
instructions:// → .github/instructions/<nome>.instructions.md
```

Quindi l'esposizione MCP è **a costo zero** — le risorse esistenti vengono semplicemente ampliate.

**Modifica al `ManifestManager`**: i nuovi file vanno aggiunti all'inventario con il flag
`"source": "engine"` nel loro record manifest, così il sistema sa che sono asset nativi del server
e non file installati da pacchetti.

### 3.2 Cosa Cambia in `spark-base`

Gli asset delegati vengono rimpiazzati con **stub leggeri** di massimo 5 righe, con frontmatter
YAML esplicito:

```markdown
---
hosted_by: engine
mcp_resource: "skills://conventional-commit"
version: "engine-managed"
---

Questa skill è gestita centralmente dall'engine SPARK.
Richiedila via MCP con: `scf_get_resource("skills://conventional-commit")`
```

Lo stub consente all'agente di trovare il file durante la navigazione del workspace e di sapere
immediatamente dove recuperare il contenuto reale. Non è un file vuoto — è un redirect semantico.

### 3.3 Nuovo Campo nel `package-manifest.json` di spark-base

```json
{
  "package_id": "spark-base",
  "version": "1.3.0",
  "engine_provided_skills": [
    "accessibility-output",
    "changelog-entry",
    "conventional-commit",
    "document-template",
    "error-recovery",
    "file-deletion-guard",
    "framework-guard",
    "framework-index",
    "framework-query",
    "framework-scope-guard",
    "git-execution",
    "personality",
    "rollback-procedure",
    "semantic-gate",
    "semver-bump",
    "style-setup",
    "task-scope-guard",
    "validate-accessibility",
    "verbosity"
  ],
  "engine_provided_instructions": [
    "framework-guard",
    "git-policy",
    "model-policy",
    "personality",
    "verbosity",
    "workflow-standard"
  ]
}
```

Questo campo permette a `scf_bootstrap_workspace` di sapere, durante il bootstrap, quali asset
NON copiare fisicamente e per quali generare invece gli stub di redirect.

### 3.4 Aggiornamento di `scf_bootstrap_workspace` (28° Tool)

La logica di bootstrap diventa:

```python
# Pseudocodice logica idempotente del 28° tool
per ogni asset in package_manifest:
    se asset in engine_provided_skills:
        se stub NON esiste nel workspace:
            crea stub con frontmatter hosted_by=engine
        # Se lo stub esiste già: NO-OP (idempotenza garantita)
    altrimenti:
        se file fisico NON esiste nel workspace:
            copia file fisico dal pacchetto
        elif file è stato modificato dall'utente:
            log WARNING, salta (non sovrascrivere)
```

La sentinella di bootstrap rimane `.github/agents/spark-assistant.agent.md` come già pianificato.

---

## 4. Impatto sul Versioning

Questa modifica introduce una breaking change controllata:

- **`spark-framework-engine`**: bump `MINOR` → v2.2.0 (nuove risorse MCP esposte, retrocompatibile
  con workspace che hanno ancora i file fisici — lo stub è opzionale per chi è già installato).
- **`spark-base`**: bump `MINOR` → v1.3.0 (gli stub sono retrocompatibili: un agente che li trova
  può sempre fare fallback al contenuto del pacchetto vecchio se l'engine non è raggiungibile).
- **`scf-master-codecrafter`**: stesso trattamento di `spark-base`, bump `MINOR` → v2.2.0.
- **`scf-registry`**: aggiornamento `registry.json` con le nuove versioni e il flag
  `engine_managed_resources: true` per i pacchetti aggiornati.

---

## 5. Piano di Implementazione (Ordine Obbligatorio)

> ⚠️ Implementare UN gruppo per volta, attendere conferma prima di procedere al successivo.

### Gruppo A — Engine: aggiunta asset delegati

**Repository**: `spark-framework-engine`
**Branch suggerito**: `feat/engine-hosted-skills`

1. Creare `.github/skills/` nell'engine (se non esiste) con le 18 skill delegate.
   Copiare i file da `spark-base` verbatim — nessuna modifica al contenuto.
2. Creare `.github/instructions/` nell'engine con le 6 instruction delegate.
3. Aggiornare il `ManifestManager` per tracciare i nuovi file con `"source": "engine"`.
4. Verificare che le risorse `skills://` e `instructions://` nel server MCP le espongano
   correttamente (test via `scf_get_resource`).

**File da toccare**: `spark-framework-engine.py` (solo la sezione `FrameworkInventory` e
`ManifestManager`), più i nuovi file `.md` nelle cartelle `.github/`.

### Gruppo B — spark-base: sostituzione con stub

**Repository**: `spark-base`
**Branch suggerito**: `refactor/delegate-to-engine`

1. Per ogni asset nella lista `engine_provided_skills`: sostituire il file con lo stub di redirect.
2. Aggiornare `package-manifest.json` con i nuovi campi `engine_provided_skills` e
   `engine_provided_instructions`.
3. Aggiornare `CHANGELOG.md` con entry per v1.3.0.
4. Bump versione in `package-manifest.json` → 1.3.0.

**File da toccare**: tutti i file `.md` delegati (sostituzione con stub), `package-manifest.json`,
`CHANGELOG.md`.

### Gruppo C — scf-master-codecrafter: allineamento

**Repository**: `scf-master-codecrafter`
**Branch suggerito**: `refactor/delegate-to-engine`

Stessa procedura del Gruppo B. Aggiungere stub per tutte le skill che `scf-master-codecrafter`
condivide con `spark-base` e che sono già state delegate nell'engine al Gruppo A.

### Gruppo D — Registry: aggiornamento

**Repository**: `scf-registry`

Aggiornare `registry.json` con le nuove versioni dei tre pacchetti e il flag
`engine_managed_resources: true`.

---

## 6. Criteri di Accettazione

Prima di considerare l'implementazione completa, verificare che:

- [ ] Un agente nel workspace utente può invocare `scf_get_resource("skills://conventional-commit")`
  e ricevere il contenuto corretto dall'engine.
- [ ] Il bootstrap su un workspace vuoto genera gli stub (non i file fisici) per gli asset delegati.
- [ ] Il bootstrap è idempotente: eseguirlo due volte non sovrascrive nulla.
- [ ] Un workspace con i file fisici originali (v1.2.0) continua a funzionare — il motore non rompe
  la retrocompatibilità.
- [ ] Il `.gitignore` dell'engine non esclude i nuovi file `.md` aggiunti al `.github/`.
- [ ] Il `ManifestManager` registra tutti i nuovi file con SHA-256 corretto.
- [ ] Nessun `print()` su stdout è stato aggiunto a `spark-framework-engine.py`.
- [ ] Tutti i file `.md` generati rispettano le regole markdownlint (una riga vuota dopo header,
  no spazi finali, una riga vuota finale).

---

## 7. Note per la Validazione di Copilot

Prima di implementare, Copilot deve rispondere esplicitamente a queste domande:

1. Nel `.github/` dell'engine esiste già una cartella `skills/`? Se sì, quali file contiene?
   Se no, è necessario crearla o il server la scopre dinamicamente?
2. Il tool `scf_get_resource` nell'engine accetta già lo schema `skills://` e `instructions://`
   per file nel `.github/` locale del server? O richiede modifiche?
3. Il `ManifestManager` ha già un campo per distinguere file `"source": "engine"` vs
   `"source": "package"`? Se no, qual è l'estensione minima necessaria?
4. Esiste già un campo `engine_provided_skills` nel formato del `package-manifest.json`?
   Se no, è uno schema v2.1 o andrebbe introdotto come v3.0?
5. Ci sono test automatici nell'engine che si romperebbero aggiungendo nuovi file al `.github/`?

