# Prompt per Copilot – Allineamento Prompt SCF all'Architettura v3.x

**Schema applicato:** Agente Autonomo & Cooperativo
**Data emissione:** 2026-05-05
**Emesso da:** Perplexity (Coordinatore SPARK Council)
**Approvato da:** Luca (Nemex81) — Coordinatore Generale
**Priorità:** Alta
**Repo coinvolti:** `spark-framework-engine`, `spark-base`

---

## Ruolo

Agisci come implementatore autonomo del SPARK Framework Engine.
Hai capacità di esecuzione in modalità autonoma: analizza, elabora
la strategia e implementa senza richiedere conferme intermedie, salvo
mancanza di informazioni bloccanti. In quel caso, dichiara
esplicitamente l'assunzione ragionevole adottata e prosegui.

---

## 1. Piano d'azione

Scomponi il task nelle seguenti fasi sequenziali:

**Fase 1 — Ricognizione:**
Leggi tutti i file `.prompt.md` con prefisso `scf-` più
`package-update.prompt.md` in entrambi i percorsi:

- `spark-base/.github/prompts/`
- `spark-framework-engine/.github/prompts/`

Leggi anche `spark-base/package-manifest.json`.
Verifica i nomi esatti dei tool MCP registrati in `spark/boot/engine.py`
tramite grep su `@mcp.tool` o decoratori equivalenti.

**Fase 2 — Analisi gap:**
Per ogni prompt, applica la checklist di allineamento v3.x descritta
nella sezione "Obiettivo del task". Documenta internamente le
discrepanze trovate per ciascun file prima di scrivere qualsiasi
modifica.

**Fase 3 — Implementazione:**
Applica le correzioni file per file. Aggiorna `scf_version` nel
frontmatter di ogni file modificato. Mantieni SHA identici tra
spark-base e spark-framework-engine per i file che coincidono.

**Fase 4 — Versioning e report:**
Bumpa `package-manifest.json` di spark-base. Produci il report
sintetico richiesto.

---

## 2. Esecuzione autonoma

### Contesto architetturale — leggi prima di toccare qualsiasi file

SPARK gestisce pacchetti SCF tramite un server MCP locale (stdio).
Esistono due modalità di installazione coesistenti:

**Modalità A — `v2_workspace` (fisica):**
I file del pacchetto vengono copiati in `<workspace>/.github/`.
Il manifest traccia ogni file con SHA-256, `scf_owner`,
`scf_merge_strategy` e `modified_by` che può valere:

- `"original"` — file intatto rispetto all'installazione
- `"user"` — file modificato dall'utente (SHA diverge)
- `"integrative_update"` — aggiornato da update integrativo,
  non toccato dall'utente da allora

L'utente può copiare nel workspace anche solo singoli componenti
di un pacchetto v3 per personalizzarli: questi diventano entry
`override_type` nel manifest. Massima granularità di controllo.

**Modalità B — `v3_store` (centralizzata):**
I file vivono in `engine_dir/packages/{pkg_id}/.github/` e sono
esposti via MCP resources (`agents://`, `skills://`, `prompts://`,
`instructions://`). Nel workspace utente non arriva nessun file
fisico — il manifest registra solo una entry sentinella con
`installation_mode: "v3_store"`. L'utente può materializzare
componenti selezionati nel workspace come override usando
`scf_install_package` con selezione componenti, o copiando
manualmente e registrando con `scf_verify_workspace`.

**Update integrativo:**
Quando un pacchetto v2_workspace viene aggiornato con
`conflict_mode: "auto"` o `"assisted"`, l'engine esegue un merge
a 3 vie (BASE=versione installata, OURS=versione utente,
THEIRS=nuova versione). Se il merge riesce, il file viene
aggiornato e `modified_by` diventa `"integrative_update"`.
Se ci sono conflitti, degrada a `manual` con marker nel file.

**`scf_bootstrap_workspace` v3.1:**
Nuovi parametri: `force: bool = False`, `dry_run: bool = False`.
Nuovi campi response: `files_copied`, `files_skipped`,
`files_protected`, `sentinel_present`, `message`.

---

## 3. Obiettivo del task

Analizza e aggiorna tutti i prompt SCF nei due repo indicati.
Per ogni prompt, verifica e correggi i seguenti punti:

**P1 — Dualità modale (install, update, remove, status):**
Ogni operazione deve gestire esplicitamente entrambe le modalità
`v2_workspace` e `v3_store`. Quando il piano o la response del
tool indica `installation_mode`, il prompt deve guidare l'utente
in modo corretto per quella modalità.

**P2 — Install v3_store:**
Se `scf_plan_install` restituisce `installation_mode: v3_store`,
spiegare che nessun file viene copiato nel workspace, le risorse
sono disponibili via MCP, e offrire la possibilità di
materializzare componenti selezionati come override (spiegare come).

**P3 — Tutti i `conflict_mode`:**
I valori validi sono: `replace`, `preserve`, `manual`, `auto`,
`assisted`. Il prompt deve presentarli con descrizione minima
di ciascuno, non solo citare `replace`.

**P4 — Update flusso duale:**
Distinguere tra update singolo (`scf_update_package(package_id)`)
e batch (`scf_check_updates()` → `scf_apply_updates()`).
Guidare verso il singolo quando l'utente specifica un pacchetto,
verso il batch per aggiornare tutto.

**P5 — Update integrativo:**
Quando la response contiene file con `modified_by: "user"`,
spiegare cosa significa e proporre il `conflict_mode` più adatto
invece di fermarsi sull'errore. Quando il merge a 3 vie riesce,
mostrare i file aggiornati con `modified_by: "integrative_update"`.

**P6 — Update v3_store:**
Per pacchetti v3_store, l'update aggiorna lo store centralizzato
senza toccare il workspace. Gli override presenti nel workspace
vengono segnalati se divergono dalla nuova versione.

**P7 — Remove dualità:**
Per `v3_store`: rimuovere lo store e deregistrare le MCP resources.
Per `v2_workspace`: rimuovere i file rispettando `modified_by: "user"`
(preservati per default salvo conferma esplicita).
In entrambi i casi, segnalare override residui nel workspace.

**P8 — Status/verify:**
Il report deve distinguere chiaramente pacchetti `v2_workspace`
da `v3_store`, mostrare conteggio file per `modified_by`,
e segnalare override orfani (override nel workspace per pacchetti
non più installati).

**P9 — Bootstrap v3.1:**
Aggiornare i prompt che toccano bootstrap per comunicare i nuovi
campi response. Se `files_protected` non è vuoto, segnalare
all'utente e offrire re-run con `force=True`. Se `dry_run=True`
è stato usato, mostrare chiaramente che nessuna modifica è avvenuta.

**P10 — Nomi tool esatti:**
Verifica che ogni tool citato esista in `spark/boot/engine.py`.
Non inventare tool. Se un tool citato nel vecchio prompt non
esiste più, rimuoverlo.

---

## Eventuale delega ad agenti

Prima di delegare, rispondi mentalmente a queste domande:

- Altri agenti sono presenti nello spazio di lavoro? (sì/no)
- Hanno competenze adatte al sotto-task? (sì/no)
- Il contesto è compatibile con le loro capacità? (sì/no)

Se anche una sola risposta è "no", svolgi in autonomia.

---

## Vincoli formali (non negoziabili)

- `scf_version` bumped: patch se solo chiarimenti, minor se il
  flusso visibile all'utente cambia.
- `scf_merge_strategy: replace` — non modificarlo su nessun prompt.
- Stile imperativo: "Esegui X", "Mostra Y", "Se Z interrompi".
- Massimo 35 righe di corpo per prompt (escluso frontmatter).
  Se un prompt supera il limite, segnalalo nel report come
  "OVERFLOW" e proponi come spezzarlo — non implementare senza
  approvazione del coordinatore.
- I file SCF con SHA identico tra i due repo devono restare
  identici dopo le modifiche — aggiornali entrambi con lo stesso
  contenuto.
- I prompt dell'engine non presenti in spark-base (`framework-*`,
  `git-*`, ecc.) non vanno toccati.
- Nessuna modifica a file Python, manifest JSON dei workspace
  utente, o file fuori da `.github/prompts/`.

---

## 4. Deliverable attesi

- File `.prompt.md` aggiornati in entrambi i repo
- `spark-base/package-manifest.json` con bump versione minor
- Report sintetico nel formato seguente (una riga per file):

  `[nome-file] v_old → v_new — motivo sintetico`

- Se durante l'analisi identifichi prompt che andrebbero
  **aggiunti** (es. prompt dedicato alla gestione override,
  oggi assente), segnalalo nel report come:

  `PROPOSTA AGGIUNTA: [nome-file] — motivo`

  Non implementare le proposte di aggiunta — la decisione
  spetta al coordinatore.

---

## Gate di validazione — verifica prima di chiudere il task

- Nessun prompt supera 35 righe di corpo
- Ogni tool citato esiste in `spark/boot/engine.py` (grep)
- `scf_version` bumped su ogni file modificato
- SHA dei file SCF coincide tra spark-base e spark-framework-engine
- `package-manifest.json` di spark-base ha versione incrementata
- Nessuna modifica a file Python, manifest workspace, o file
  fuori da `.github/prompts/`

---

## Tecniche avanzate da applicare

- **Chain of thought:** per ogni prompt, mostra il ragionamento
  gap-analysis → decisione → modifica prima di scrivere.
- **Tree of thought:** per i prompt con logica duale complessa,
  esplora più approcci (ramo singolo vs sezioni condizionali)
  e scegli quello più leggibile e conciso.
- **Concatenamento:** esegui le fasi in sequenza. Non passare
  alla Fase 3 senza aver completato la Fase 2 per tutti i file.

---

## Valutazione post-esecuzione

Al termine, fornisci:

1. Report sintetico delle modifiche (formato indicato sopra)
2. Elenco dei gate di validazione: PASS / FAIL per ciascuno
3. Eventuali proposte di aggiunta prompt
4. Richiesta esplicita di revisione al coordinatore prima del commit
