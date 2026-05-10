# Prompt Operativo — SPARK Init Step 4 + SPARK-START.md v1.0

**Autore:** Perplexity AI (Coordinatore)
**Approvato da:** Nemex81
**Branch:** `feature/dual-mode-manifest-v3.1`
**Data:** 2026-05-08
**Agente designato:** `@spark-engine-maintainer`
**Tipo operazione:** Implementazione codice — modifica file esistenti + creazione funzioni
**Baseline test:** 446 passed, 9 skipped, 0 failed
** mode: agent **
** execute_mode: autonomus **

---

## REGOLA ZERO — Analizza prima, modifica dopo

> **Non scrivere una riga di codice senza aver letto integralmente il file
> che stai per modificare.** Questo vale per ogni file, senza eccezioni.
> Se trovi una divergenza tra questo prompt e il codice reale, la realtà
> prevale sempre. Documenta la divergenza e adatta l'implementazione.

---

## Obiettivo

Implementare due modifiche a `spark-init.py`:

**Modifica A — Step 4:** aggiungere la funzione
`_propagate_spark_base_to_workspace()` che copia i file da
`packages/spark-base/.github/` al `.github/` del workspace utente.
Logica: locale, idempotente, nessuna chiamata di rete, policy default `preserve`.

**Modifica B — SPARK-START.md:** aggiungere la funzione
`_write_spark_start_file()` che crea `SPARK-START.md` nella root
del workspace utente con istruzione operativa minimale.

Entrambe le modifiche vengono chiamate da `main()` come Step 4 e Step 5
dopo i tre step esistenti.

**Vincolo critico:** `_BootstrapInstaller` NON va toccata in questa
iterazione. Rimane nel codice invariata. La sua deprecazione è un task
futuro separato.

---

## Il tuo processo di lavoro

### FASE 1 — Lettura e mappatura (obbligatoria, non saltare)

Leggi integralmente i seguenti file nell'ordine indicato:

**1.1 — `spark-init.py` (file principale da modificare)**

Durante la lettura, mappa e documenta mentalmente:
- La struttura della classe `_BootstrapInstaller` (non la modifichi,
  ma devi capire cosa fa per non interferire).
- Le funzioni esistenti in `main()` e il loro ordine di chiamata
  (Step 1, 2, 3 attuali).
- Come sono gestiti `engine_root` e `workspace_root` come `Path`
  nel codice esistente — usa gli stessi pattern, non inventarne di nuovi.
- Come viene fatto il logging attuale: `print()` su `stderr`? Usa
  `sys.stderr.write()`? Formato dei messaggi `[SPARK-INIT]`?
- Esiste già `_sha256_file()` o una funzione equivalente nel file?
  Se sì, riusala senza duplicarla.
- Come gestisce i percorsi `Path` — usa `.resolve()`, `.absolute()`,
  o percorsi relativi?
- Il file ha un blocco `if __name__ == "__main__":` con gestione
  eccezioni? Come si comporta in caso di errore?

**1.2 — `spark/boot/lifecycle.py`**

Cerca e leggi `_install_workspace_files_v3` (o funzione analoga che
già implementa logica di copia idempotente con SHA256). Documenta:
- Come calcola SHA256 dei file.
- Come gestisce la policy di conflitto (preserve vs overwrite).
- Quali utility `pathlib` usa.
- Questa funzione è importabile/riutilizzabile da `spark-init.py`
  senza dipendenze circolari? Se sì, preferisci importarla a crearla
  da zero. Se no (dipendenze circolari o architettura incompatibile),
  crea una versione locale in `spark-init.py`.

**1.3 — `tests/test_spark_init.py`**

Leggi la struttura del file test per capire:
- Come sono organizzati i test esistenti (fixture, mock, classi).
- Ci sono fixture `engine_root` o `workspace_root` già definite?
- Come viene mockato il filesystem (tmp_path? monkeypatch? mock.patch?).
- Questo ti serve per scrivere i nuovi test alla fine.

**1.4 — `packages/spark-base/.github/`**

Verifica che la struttura esista e sia popolata come da report v1.0.
Confirma la presenza di almeno questi file:
- `copilot-instructions.md`
- `agents/spark-assistant.agent.md`
- `skills/` con almeno 10 file

Se la struttura è diversa da quanto atteso, adatta l'implementazione
e documenta la divergenza nel report di completamento.

---

### FASE 2 — Implementazione Modifica A: Step 4

Dopo la lettura, implementa `_propagate_spark_base_to_workspace()`.

#### Specifica funzionale

```
Input:
  engine_root: Path   — root del repo spark-framework-engine
  workspace_root: Path — root del workspace utente da inizializzare

Behavior:
  src_root = engine_root / "packages" / "spark-base" / ".github"
  dst_root = workspace_root / ".github"

  Se src_root non esiste → logga avviso su stderr, ritorna senza errori

  Per ogni file in src_root (ricorsivo):
    rel_path = percorso relativo a src_root
    dst_file = dst_root / rel_path

    CASO 1: dst_file non esiste
      → crea le directory padre (parents=True, exist_ok=True)
      → copia il file (bytes, non testo per preservare encoding)
      → logga: [SPARK-INIT] .github/<rel_path> → scritto

    CASO 2: dst_file esiste, SHA256 identico a src_file
      → skip silenzioso (idempotente)

    CASO 3: dst_file esiste, SHA256 diverso
      → NON sovrascrivere (policy preserve)
      → logga: [SPARK-INIT] .github/<rel_path> → preservato (modificato dall'utente)

Return: dict con chiavi "written" (list[str]) e "preserved" (list[str])
```

#### Requisiti di implementazione

- **SHA256**: se `_sha256_file()` esiste già in `spark-init.py` o in
  `lifecycle.py` (importabile senza circolarità), riusala.
  Altrimenti implementala localmente:
  ```python
  def _sha256_file(path: Path) -> str:
      import hashlib
      h = hashlib.sha256()
      h.update(path.read_bytes())
      return h.hexdigest()
  ```

- **Logging**: usa esattamente lo stesso formato dei log esistenti
  in `spark-init.py`. Non inventare un nuovo formato.

- **Gestione errori**: se una singola operazione di copia fallisce
  (permessi, disco pieno, ecc.), logga l'errore su stderr e continua
  con i file successivi. Non interrompere l'intero Step 4 per un
  singolo file.

- **Docstring**: Google Style.
  ```python
  def _propagate_spark_base_to_workspace(
      engine_root: Path,
      workspace_root: Path,
  ) -> dict[str, list[str]]:
      """Propaga i file di packages/spark-base/.github/ nel workspace utente.

      Operazione locale, idempotente, senza chiamate di rete.
      Policy default: preserve (file utente modificati non vengono
      sovrascritti; aggiornamenti tramite scf_update_packages via MCP).

      Args:
          engine_root: Path radice del repo spark-framework-engine.
          workspace_root: Path radice del workspace utente.

      Returns:
          Dict con "written" (file copiati) e "preserved" (file
          esistenti con contenuto diverso, non sovrascritti).
      """
  ```

- **Posizione nel file**: aggiungi la funzione nello stesso blocco
  dove si trovano le altre funzioni di Step 1-3. Non in coda al file
  se gli altri step sono in cima.

---

### FASE 3 — Implementazione Modifica B: SPARK-START.md

Implementa `_write_spark_start_file(workspace_root: Path) -> None`.

#### Contenuto del file

```markdown
# Avvia SPARK

Il workspace è configurato. Per iniziare:

1. Apri il pannello Copilot in VS Code (`Ctrl+Shift+I`).
2. Seleziona la modalità **Agent**.
3. Scegli l'agente **spark-assistant**.
4. Scrivi: `inizializza il workspace`

SPARK avvierà l'orientamento e proporrà i pacchetti
necessari per il tuo progetto.

---

*Puoi eliminare questo file dopo il primo avvio.*
*Per domande sull'architettura SPARK, usa l'agente `spark-guide`.*
```

#### Requisiti

- **Idempotente**: se `SPARK-START.md` esiste già, non sovrascrivere.
  Logga skip silenzioso.
- **Encoding**: `utf-8` esplicito nel `write_text()`.
- **Posizione nel file**: subito sotto `_propagate_spark_base_to_workspace`.
- **Docstring**: Google Style.

---

### FASE 4 — Integrazione in main()

Leggi di nuovo la funzione `main()` (già letta in FASE 1, ma rileggi
il blocco specifico per non sbagliare il punto di inserimento).

Aggiungi le chiamate come Step 4 e Step 5 **dopo** lo step del
`.code-workspace` e **prima** del messaggio finale su stderr:

```python
# Step 4 — Propagazione locale spark-base nel workspace
result = _propagate_spark_base_to_workspace(engine_root, workspace_root)
if result["preserved"]:
    sys.stderr.write(
        f"[SPARK-INIT] {len(result['preserved'])} file preservati "
        f"(modificati dall'utente).\n"
    )

# Step 5 — File di avvio rapido per l'utente
_write_spark_start_file(workspace_root)
```

Aggiorna il messaggio finale su stderr aggiungendo una riga:
```
[SPARK-INIT] SPARK-START.md → apri Copilot e segui le istruzioni
```

---

### FASE 5 — Test

Aggiungi i test in `tests/test_spark_init.py`.

**Analizza prima la struttura del file test** (già letto in FASE 1)
poi aggiungi i test nello stesso stile e con le stesse fixture esistenti.

#### Test minimi obbligatori per `_propagate_spark_base_to_workspace`:

```
test_propagate_writes_new_files:
  - src_root popolato con 2 file
  - dst_root vuoto
  - Verifica: entrambi i file scritti in dst, "written" ha 2 elementi

test_propagate_skip_identical:
  - src e dst hanno stesso file con stesso contenuto
  - Verifica: file NON riscritto, "written" vuoto, "preserved" vuoto

test_propagate_preserve_modified:
  - src e dst hanno stesso file con contenuto DIVERSO
  - Verifica: dst non modificato, "preserved" ha 1 elemento

test_propagate_missing_src_root:
  - src_root non esiste
  - Verifica: nessun errore sollevato, return dict vuoto

test_propagate_creates_nested_dirs:
  - src ha file in sottocartella (agents/spark-assistant.agent.md)
  - Verifica: la sottocartella viene creata nel dst
```

#### Test minimi obbligatori per `_write_spark_start_file`:

```
test_write_spark_start_creates_file:
  - workspace_root vuoto
  - Verifica: SPARK-START.md esiste in workspace_root

test_write_spark_start_idempotent:
  - SPARK-START.md già esiste con contenuto custom
  - Verifica: file NON sovrascritto, contenuto custom intatto
```

---

### FASE 6 — Verifica finale

Dopo ogni modifica e dopo i test, esegui:

```bash
python -m pytest tests/test_spark_init.py -v 2>&1 | tail -30
```

Il risultato deve essere:
- Tutti i test esistenti: **PASS** (446 baseline + nuovi test aggiunti)
- Zero test rotti rispetto alla baseline
- I nuovi test aggiunti: tutti **PASS**

Se un test fallisce → vai a FASE 7 (gestione anomalia).

Esegui anche una verifica di integrità MCP:
```bash
python -c "import spark_framework_engine; print('import OK')" 2>/dev/null || \
python -c "import ast; ast.parse(open('spark-init.py').read()); print('syntax OK')"
```

---

### FASE 7 — Gestione autonoma delle anomalie

Questa fase si attiva solo se si verifica una delle condizioni seguenti:

- Un test della baseline fallisce dopo le modifiche
- Un errore di importazione o sintassi è rilevato
- Il filesystem durante i test produce comportamenti inattesi
- Una dipendenza da `lifecycle.py` causa una circolarità

#### Protocollo anomalia

**Step A — Classificazione:**
Determina se l'anomalia è:
- **Tipo I — Regressione**: un test esistente che prima passava ora fallisce.
  Causa probabile: modifica accidentale al codice esistente o conflitto
  con `_BootstrapInstaller`.
- **Tipo II — Circolarità**: importare da `lifecycle.py` causa
  `ImportError` circolare. Soluzione: implementa `_sha256_file` localmente
  in `spark-init.py` senza importazioni da `spark/`.
- **Tipo III — Filesystem mock**: i test nuovi falliscono perché il
  framework di mock esistente non supporta la struttura attesa.
  Adatta i test alle fixture già presenti invece di crearne di nuove.
- **Tipo IV — Blocco architetturale**: la struttura di `main()` non
  permette l'inserimento di Step 4 e Step 5 nel modo previsto
  (es. `main()` non riceve `engine_root` come parametro).

**Step B — Risoluzione per tipo:**

*Tipo I — Regressione:*
1. Leggi di nuovo `spark-init.py` dal punto della modifica.
2. Identifica la riga esatta che ha introdotto la regressione.
3. Correggi solo quella riga — non refactoring ampi.
4. Ri-esegui i test. Se passa → torna a FASE 6. Se fallisce ancora
   dopo 2 tentativi → documenta nel report e ferma l'implementazione.

*Tipo II — Circolarità:*
1. Non importare da `lifecycle.py`.
2. Implementa `_sha256_file()` localmente in `spark-init.py`.
3. Ri-esegui FASE 2 con la versione locale.

*Tipo III — Filesystem mock:*
1. Leggi le prime 80 righe di `tests/test_spark_init.py` per capire
   il pattern di fixture.
2. Adatta i nuovi test per usare le stesse fixture senza crearne di nuove.
3. Non modificare le fixture esistenti.

*Tipo IV — Blocco architetturale:*
1. Leggi `main()` nella sua interezza.
2. Identifica come vengono passati `engine_root` e `workspace_root`.
3. Se non sono parametri diretti di `main()`, cerca come vengono
   derivati (es. da `sys.argv`, da variabili d'ambiente, da funzioni
   di discovery).
4. Adatta la signature di `_propagate_spark_base_to_workspace` e
   `_write_spark_start_file` per usare lo stesso meccanismo.
5. Documenta l'adattamento nel report di completamento.

**Step C — Limite tentativi:**
Se un'anomalia non è risolta dopo 3 tentativi di correzione:
1. Non proseguire con altri task.
2. Scrivi `docs/reports/SPARK-REPORT-AnomaliaImpl-[timestamp].md`
   con: descrizione anomalia, tentativi effettuati, stato attuale
   del codice, azione raccomandata per revisione umana.
3. Ferma il processo e attendi input dal coordinatore.

---

### FASE 8 — Report di completamento

Salva `docs/reports/SPARK-REPORT-ImplStep4-v1.0.md` con:

```markdown
# SPARK Impl Step4 + SPARK-START.md — Report v1.0

**Data:** [data]
**Branch:** feature/dual-mode-manifest-v3.1
**Agente:** @spark-engine-maintainer
**Stato:** COMPLETATO / PARZIALE / BLOCCATO

---

## File modificati

| File | Tipo modifica | Righe aggiunte | Righe modificate |
|------|---------------|----------------|------------------|
| `spark-init.py` | Aggiunta funzioni + integrazione main() | [N] | [N] |
| `tests/test_spark_init.py` | Aggiunta test | [N] | 0 |

## Funzioni aggiunte

### _propagate_spark_base_to_workspace()
- Riga di definizione: [N]
- SHA256: [locale / importata da lifecycle.py]
- Note di adattamento: [eventuali divergenze rispetto alla spec]

### _write_spark_start_file()
- Riga di definizione: [N]
- Note: []

## Integrazione main()
- Step 4 inserito dopo riga: [N]
- Step 5 inserito dopo riga: [N]

## Risultati test

### Baseline preservata
[PASS/FAIL] — [N] test esistenti: tutti PASS / [N] rotti

### Nuovi test
[lista test aggiunti con esito]

## Anomalie riscontrate

["Nessuna" oppure descrizione con tipo e risoluzione adottata]

## Divergenze rispetto alla spec del prompt

["Nessuna" oppure descrizione con motivazione]

## Stato finale

STEP 4 E SPARK-START.md IMPLEMENTATI — PRONTO PER REVISIONE
```

---

## Checklist pre-commit (obbligatoria)

- [ ] `spark-init.py` letto integralmente prima di modificare
- [ ] `lifecycle.py` analizzato per riuso SHA256
- [ ] `tests/test_spark_init.py` analizzato per pattern fixture
- [ ] `packages/spark-base/.github/` verificato popolato
- [ ] `_BootstrapInstaller` non toccata
- [ ] `_propagate_spark_base_to_workspace()` implementata
- [ ] `_write_spark_start_file()` implementata
- [ ] `main()` aggiornata con Step 4 e Step 5
- [ ] Almeno 7 nuovi test aggiunti
- [ ] `pytest tests/test_spark_init.py` — zero regressioni
- [ ] Sintassi `spark-init.py` verificata (ast.parse o import)
- [ ] Report `SPARK-REPORT-ImplStep4-v1.0.md` salvato in `docs/reports/`
