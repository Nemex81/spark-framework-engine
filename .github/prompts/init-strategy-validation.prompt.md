# Prompt Strutturato — SPARK Init Strategy Validation v1.0

**Autore:** Perplexity AI (Coordinatore)
**Approvato da:** Nemex81
**Branch target:** `feature/dual-mode-manifest-v3.1`
**Data:** 2026-05-08
**Agente designato:** `@spark-engine-maintainer`
** mode: agent **
** execute_mode: autonomus **

---

## Contesto e obiettivo

Il Consiglio ha elaborato una strategia per risolvere tre problemi
aperti nel sistema SPARK:

1. L'utente finale non ha una mappa mentale chiara di cosa offre SPARK
   prima di dover fare scelte operative.
2. Il processo di inizializzazione (`spark-init.py`) non popola il
   workspace utente — lascia il `.github/` vuoto dopo l'init.
3. La distinzione tra **bundle MCP** (file nell'engine, servizi via
   protocollo MCP) e **pacchetti SCF** (repo indipendenti, artefatti
   per agenti) non è dichiarata da nessuna parte nel sistema.

Il tuo compito è: analizzare la strategia proposta, verificarla
sul codice reale, convalidarla o elaborare una strategia correttiva,
e produrre un report finale dettagliato.

**REGOLA GLOBALE — si applica a tutti i task:**
Prima di qualsiasi analisi, leggi ogni file nella sua interezza.
Non fare assunzioni sul contenuto basandoti su letture parziali.
Se trovi una divergenza tra quanto descritto in questo prompt e il
codice reale, quella divergenza è informazione preziosa — registrala
e usala per affinare l'analisi.

**Questo prompt non richiede modifiche al codice.**
Il tuo output è esclusivamente analitico: lettura, ragionamento,
verifica, report. Nessun file del sistema va toccato eccetto il
report finale in `docs/reports/`.

---

## La strategia proposta dal Consiglio

### Pilastro 1 — Distinzione architetturale dichiarata

Il sistema SPARK opera su due livelli distinti che oggi non sono
esplicitati da nessuna parte:

**Bundle MCP** — i file in `packages/` dentro `spark-framework-engine`.
Sono risorse progettate per essere esposte via protocollo MCP come
endpoint del server. Richiedono il server attivo. Non sono leggibili
direttamente da Copilot come istruzioni operative — sono dati che
il server interpreta e serve tramite le URI scheme `agents://`,
`skills://`, `instructions://`, `prompts://`, `scf://`.

**Pacchetti SCF** — i repo indipendenti (`scf-master-codecrafter`,
`scf-pycode-crafter`, ecc.). Contengono risorse agente: file `.md`
progettati per essere letti e interpretati da Copilot in Agent Mode.
Funzionano senza il server MCP attivo. Il server MCP è solo il canale
di distribuzione, installazione e aggiornamento.

Implicazione: la stessa "skill" nei due contesti ha forma e scopo
opposti. Nei pacchetti SCF una skill è narrativa, destinata a Copilot.
Nel bundle MCP una skill è una struttura dati esposta come risorsa MCP.

### Pilastro 2 — Semplificazione di `spark-init.py`

Il Consiglio ha stabilito che `spark-init.py` non deve più scaricare
nulla dalla rete. I pacchetti base sono già presenti in `packages/`
nel repo dell'engine — committati lì direttamente.

Il nuovo flusso di `spark-init.py` deve essere:

```
Step 1 — Prepara il runtime locale (virtualenv + mcp)       [già presente]
Step 2 — Scrive .vscode/mcp.json                            [già presente]
Step 3 — Crea/aggiorna il .code-workspace                   [già presente]
Step 4 — Propaga i file di packages/spark-base/.github/
         nel .github/ del workspace utente                  [MANCANTE]
Step 5 — Stampa messaggio finale con istruzione per Copilot [da aggiornare]
```

Step 4 è la modifica chiave: lettura da filesystem locale, copia
idempotente, nessuna chiamata di rete. La classe `_BootstrapInstaller`
attuale (che fa fetch dal registry remoto) non dovrebbe più essere
necessaria per l'init.

### Pilastro 3 — Skill a struttura a cartella

Le competenze degli agenti (spark-assistant, spark-guide) devono
essere gestite come skill a cartella, non come file `.md` singoli.
La struttura proposta:

```
.github/skills/
└── spark-orientation/
    ├── spark-orientation.skill.md   ← entry point, mappa mentale
    ├── mcp-bundle.md                ← servizi MCP integrati
    └── scf-packages.md              ← pacchetti SCF e plugin
```

Questa struttura va sia nel bundle MCP (in `packages/spark-base/`)
sia nel repo del pacchetto (`scf-master-codecrafter`), ma con
implementazioni diverse:
- Nel bundle MCP: risorse esposte via `skills://`
- Nel pacchetto SCF: file narrativi per Copilot

### Pilastro 4 — Due agenti distinti

**`spark-assistant`** — agente operativo. Guida l'utente nel processo
di inizializzazione step-by-step. Usa la skill di orientamento come
contesto, ma il suo scopo primario è eseguire il processo, non spiegare
l'architettura.

**`spark-guide`** — agente consultivo. Risponde a domande aperte su
come funziona il sistema, spiega la distinzione bundle MCP / pacchetti
SCF, orienta l'utente nella scelta dei pacchetti. Non esegue operazioni.

Entrambi referenziano la stessa skill `spark-orientation` ma con
intenzioni diverse dichiarate nel loro file agente.

### Pilastro 5 — Auto-presentazione di spark-assistant

Dopo l'esecuzione di `spark-init.py`, l'utente deve essere guidato
ad aprire Copilot senza dover sapere cosa digitare.

Soluzione proposta (combinazione di due approcci):

**A — `SPARK-WELCOME.md`**: `spark-init.py` crea questo file in root
del progetto utente con istruzioni minimali e una sola azione richiesta:
aprire Copilot e scrivere "@spark-assistant inizializza il workspace".

**B — Direttiva in `copilot-instructions.md`**: il file
`.github/copilot-instructions.md` propagato nel workspace utente
contiene una direttiva a Copilot: se rileva che il workspace è appena
inizializzato (spark-base presente, nessun pacchetto utente aggiuntivo),
deve presentarsi proattivamente come spark-assistant e avviare
l'orientamento.

Limite noto e accettato: VS Code non consente di aprire
automaticamente il pannello chat da script esterni. L'unica azione
manuale richiesta all'utente è aprire il pannello Copilot.

---

## Il tuo processo di lavoro

### FASE 1 — Lettura e mappatura dello stato attuale

Leggi integralmente i seguenti file:

- `spark-init.py` (root engine)
- `spark-framework-engine.py` (root engine)
- `spark/boot/engine.py`
- `packages/spark-base/.github/` — leggi l'intera struttura
- `.github/agents/` — tutti i file agente presenti
- `.github/skills/` — struttura attuale (se esiste)
- `README.md`

Per ogni file, documenta:
- Cosa fa attualmente
- Quali parti sono rilevanti per la strategia proposta
- Eventuali divergenze rispetto a quanto descritto nel prompt

### FASE 2 — Verifica dei 5 Pilastri

Per ciascun pilastro, verifica sul codice reale:

**Pilastro 1 — Distinzione architetturale:**
- La distinzione bundle MCP / pacchetti SCF è già documentata
  da qualche parte nel codice o nei file esistenti?
- I file in `packages/spark-base/` sono implementati in modo
  diverso dai file nei repo SCF? In cosa differiscono concretamente?
- Dove andrebbe inserita questa distinzione nella documentazione
  esistente per massimo impatto?

**Pilastro 2 — Semplificazione `spark-init.py`:**
- `packages/spark-base/` esiste nell'engine repo? È popolato?
  Quanti file contiene e di che tipo?
- La classe `_BootstrapInstaller` in `spark-init.py` è ancora
  necessaria dopo l'adozione del modello locale?
- Ci sono altri punti in `spark-init.py` che fanno chiamate di rete
  che andrebbero rimosse o ridotte?
- La logica di propagazione locale (Step 4) è già presente in
  qualche forma, o va scritta da zero?
- Quale impatto avrebbe la rimozione di `_BootstrapInstaller`
  sugli altri moduli che la importano o la referenziano?

**Pilastro 3 — Skill a cartella:**
- Esiste già una struttura `.github/skills/` nel bundle o negli agenti?
- I file agente esistenti referenziano già skill in qualche forma?
- La struttura a cartella è compatibile con come il server MCP
  espone le risorse via `skills://`? Come funziona attualmente
  il discovery delle skill nel `FrameworkInventory`?

**Pilastro 4 — Due agenti distinti:**
- `spark-assistant.agent.md` esiste? Qual è il suo contenuto attuale?
- `spark-guide.agent.md` esiste? Se no, va creato.
- I ruoli attuali degli agenti rispecchiano la distinzione
  operativo / consultivo proposta, o c'è sovrapposizione?

**Pilastro 5 — Auto-presentazione:**
- `copilot-instructions.md` esiste già nel bundle? Qual è il
  suo contenuto attuale?
- La logica di propagazione (Step 4 di `spark-init.py`) creerebbe
  o aggiornerebbe `copilot-instructions.md` nel workspace utente?
- `SPARK-WELCOME.md` è già previsto da qualche parte, o è nuovo?

### FASE 3 — Ciclo di convalida

#### Convalida della strategia

Dopo la verifica, applica questi criteri:

**C1 — Coerenza interna:** I 5 pilastri sono coerenti tra loro?
Ci sono dipendenze circolari o contraddizioni?

**C2 — Fattibilità tecnica:** Ogni modifica proposta è implementabile
senza rompere la suite di test esistente (446 passed, 9 skipped)?
Identifica i test che verrebbero impattati da ciascun pilastro.

**C3 — Impatto sul canale MCP:** Nessuna modifica deve introdurre
`print()` su stdout o eccezioni non gestite che raggiungano il canale
JSON-RPC. Verifica che i nuovi file propagati nel workspace utente
non interferiscano con il discovery dell'engine.

**C4 — Idempotenza:** La propagazione locale (Pilastro 2, Step 4)
è idempotente per design? Cosa succede se viene eseguita due volte
sullo stesso workspace?

**C5 — Retro-compatibilità:** Gli utenti che hanno già eseguito
`spark-init.py` con il vecchio sistema (con `_BootstrapInstaller`)
vengono impattati negativamente dalla nuova versione?

#### Esito della convalida

**Se tutti i criteri C1-C5 passano:**
→ La strategia è convalidata. Procedi con FASE 4 (report finale).

**Se uno o più criteri falliscono:**
→ Elabora una strategia correttiva per i pilastri che non passano.
→ Documenta il problema trovato e la correzione proposta.
→ Ri-esegui il ciclo di verifica sui soli pilastri corretti.
→ Ripeti fino a convalida completa o fino a max 3 iterazioni.
→ Se dopo 3 iterazioni la convalida non passa, documenta i blocchi
   aperti con dettaglio sufficiente per una decisione umana.

### FASE 4 — Report finale

Salva il report in `docs/reports/SPARK-REPORT-InitStrategy-v1.0.md`
con il formato seguente:

```markdown
# SPARK Init Strategy Validation — Report v1.0

**Data:** [data]
**Branch:** feature/dual-mode-manifest-v3.1
**Agente:** @spark-engine-maintainer
**Iterazioni di convalida:** [N]

---

## Stato attuale del sistema

### packages/spark-base/
[struttura trovata, file presenti, tipo di contenuto]

### Agenti esistenti
[lista con path e descrizione sintetica di ciascuno]

### Skill esistenti
[struttura .github/skills/ se presente, altrimenti "assente"]

### spark-init.py — analisi
[ruolo attuale di _BootstrapInstaller, chiamate di rete presenti,
step mancanti rispetto alla strategia proposta]

---

## Verifica dei 5 Pilastri

### Pilastro 1 — Distinzione architetturale
[trovato / non trovato / parziale + dettaglio]

### Pilastro 2 — Semplificazione spark-init.py
[fattibilità, impatto, dipendenze, step già presenti vs da aggiungere]

### Pilastro 3 — Skill a cartella
[compatibilità con FrameworkInventory, struttura esistente]

### Pilastro 4 — Due agenti distinti
[stato attuale degli agenti, gap rispetto alla proposta]

### Pilastro 5 — Auto-presentazione
[copilot-instructions.md attuale, SPARK-WELCOME.md, fattibilità]

---

## Risultato ciclo di convalida

### Iterazione 1
[criteri C1-C5: PASS / FAIL + motivazione per ciascuno]

### Iterazione N (se necessaria)
[strategia correttiva applicata + nuovo esito]

---

## Strategia finale convalidata

[descrizione della strategia nella sua forma finale,
con eventuali ottimizzazioni rispetto alla proposta originale]

### Modifiche necessarie — ordine di esecuzione

#### 1. scf-master-codecrafter
[lista file da creare/modificare con descrizione]

#### 2. spark-framework-engine
[lista file da creare/modificare con descrizione]

#### 3. scf-registry
[aggiornamenti necessari se presenti]

### Rischi residui
[eventuali rischi non eliminabili con motivazione]

---

## Stato finale

STRATEGIA CONVALIDATA — PRONTA PER IMPLEMENTAZIONE
oppure
BLOCCHI APERTI: [lista dettagliata con priorità]
```

---

## Checklist pre-report (obbligatoria)

- [ ] Tutti i file listati in FASE 1 sono stati letti integralmente
- [ ] Tutti i 5 pilastri sono stati verificati sul codice reale
- [ ] Il ciclo di convalida è stato eseguito almeno una volta
- [ ] Il report è salvato in `docs/reports/SPARK-REPORT-InitStrategy-v1.0.md`
- [ ] Il report distingue chiaramente "stato attuale" da "strategia proposta"
- [ ] Ogni affermazione nel report è supportata da evidenza nel codice
