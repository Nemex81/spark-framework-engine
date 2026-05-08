# Prompt Strutturato — SPARK Dual-Mode Post-Fix v1.0

**Autore:** Perplexity AI (Coordinatore)
**Approvato da:** Nemex81
**Branch target:** `feature/dual-mode-manifest-v3.1`
**Data:** 2026-05-08
**Agente designato:** `@spark-engine-maintainer`

---

## Contesto

Il commit `0d52e644` ha implementato la Dual-Mode Architecture v1.0 (TASK-1..TASK-5).
La suite non-live ha retto: 446 passed, 9 skipped, 0 failed.
Il Coordinatore ha rilevato 3 punti aperti da risolvere prima del merge su `main`.
Questo prompt li gestisce come 3 task sequenziali e indipendenti.

**REGOLA GLOBALE — si applica a tutti i task:**
Prima di modificare qualsiasi file, leggi il file nella sua interezza.
Non fare assunzioni sul contenuto basandoti su letture parziali o precedenti.
Se il file contiene una difformità rispetto a quanto descritto in questo prompt,
registra la divergenza nel report di fine task e adatta l'azione di conseguenza.

---

## TASK-1 — Revisione e audit di `spark/plugins/manager.py`

### Obiettivo

Verificare che il file `spark/plugins/manager.py` (aggiunto nel commit `0d52e644`,
323 righe) sia corretto, coerente con l'architettura SPARK e privo di
problemi critici prima del merge.

### Procedura

**Step 1 — Lettura integrale**
Leggi `spark/plugins/manager.py` nella sua interezza.

**Step 2 — Analisi su 5 assi**

Asse 1 — Controllo stdout/stderr:
Verifica che nessuna funzione usi `print()` su stdout.
Tutti i log devono passare per `logging` (pattern `_log = logging.getLogger(__name__)`).
Se trovi `print()` su stdout, sostituiscilo con `_log.info()` o `_log.error()`.

Asse 2 — Gestione errori e connessione assente:
Verifica che `download_plugin()` e `list_available_plugins()` gestiscano
esplicitamente `requests.exceptions.ConnectionError`, `requests.exceptions.Timeout`
e `requests.exceptions.HTTPError`.
Se l'eccezione non è catturata, il tool MCP che la chiama esplode su stdout —
violazione critica del canale JSON-RPC.
Se mancano i try/except, aggiungili. Ogni eccezione non gestita deve essere
loggata su `_log.error()` e restituire un risultato di errore strutturato
(dict con chiave `"error"` e messaggio stringa), non re-raise nudo.

Asse 3 — Path resolution e workspace:
Verifica che i path di destinazione nel workspace utente siano calcolati
tramite `pathlib.Path` e non tramite concatenazione di stringhe.
Verifica che nessun path sia hardcodato.
Se trovi stringhe di path hardcodate, convertile a `pathlib.Path`.

Asse 4 — Coerenza con `PluginManagerFacade`:
Verifica che `PluginManager` non replichi logica già presente in `PluginManagerFacade`
(in `spark/plugins/facade.py`).
Se c'è duplicazione significativa, segnalala nel report senza rifattorizzare —
la de-duplicazione è fuori scope di questo task.

Asse 5 — Export in `__init__.py`:
Verifica che `spark/plugins/__init__.py` esporti correttamente
`PluginManager`, `download_plugin`, `list_available_plugins`.
Se un export manca, aggiungilo.

**Step 3 — Applica le correzioni**
Applica solo le correzioni degli Assi 1, 2, 3, 5 se necessarie.
Non refactoring, non aggiunte di feature.

**Step 4 — Validazione**
Esegui:

```
python -m py_compile spark/plugins/manager.py
python -m pytest -q --ignore=tests/test_integration_live.py
```

La suite deve restare a 446 passed, 9 skipped, 0 failed (o più passed se
si aggiungono test — vedi sotto).
Se trovi problemi non risolvibili senza modificare l'architettura,
documentali nel report e prosegui con TASK-2.

**Step 5 — Report**
Produce un report sintetico con:

- File letti
- Problemi trovati per asse (o "nessuno")
- Correzioni applicate con numero di riga
- Risultato suite test

### Gestione anomalie TASK-1

Se `manager.py` non esiste sul branch:
→ Segnala nel report, skippa TASK-1, procedi con TASK-2.

Se `py_compile` fallisce dopo le tue modifiche:
→ Annulla le ultime modifiche al file, ripristina il contenuto precedente,
documenta l'errore nel report e procedi con TASK-2.

Se la suite scende sotto 446 passed:
→ Analizza il fallimento. Se è causato dal tuo intervento, annulla la modifica
specifica, ri-esegui la suite e documenta nel report.
Se il fallimento preesisteva (non causato da te), documentalo e procedi.

---

## TASK-2 — Allineamento contatore tool nel README

### Obiettivo

Il `README.md` riporta "46 tool disponibili" dopo il commit di Copilot,
ma il contatore reale nell'engine (`engine.py`, docstring `register_tools()`)
è stato aggiornato a 50. Allineare README al valore effettivo.

### Procedura

**Step 1 — Lettura e verifica**
Leggi `spark/boot/engine.py` nella sua interezza.
Individua la riga contenente il pattern `Tools (N)` nella docstring
di `register_tools()`. Estrai il valore N attuale.

Poi leggi `spark/boot/tools_plugins.py` nella sua interezza e conta
manualmente i decoratori `@_register_tool` presenti nel file.
Poi leggi tutti gli altri file `tools_*.py` in `spark/boot/` e somma
il totale reale dei decoratori `@_register_tool`.

**Step 2 — Verifica coerenza**
Confronta:

- Valore N da `engine.py` docstring
- Conteggio reale da `@_register_tool` su tutti i file `tools_*.py`
- Valore dichiarato nel `README.md`

Se i tre valori coincidono: nessuna azione su codice, vai a Step 4.
Se divergono: applica le correzioni necessarie (Step 3).

**Step 3 — Correzioni**
Aggiorna nel README il numero dichiarato al valore reale.
Se la tabella dei tool nel README non elenca `scf_list_plugins` e
`scf_install_plugin` tra i tool del modulo Plugin, aggiungili.
Aggiorna la docstring di `register_tools()` in `engine.py` se il valore
N non corrisponde al conteggio reale.

**Step 4 — Validazione**
Esegui:

```
python -m pytest tests/test_engine_coherence.py -q
```

Il test `test_tool_counter_consistency` deve passare.
Se fallisce, analizza cosa conta il test e correggi il delta.

**Step 5 — Report**
Produce un report sintetico con:

- Valore trovato in `engine.py`
- Conteggio reale da codice
- Valore trovato in `README.md` prima della modifica
- Valore scritto nel `README.md` dopo la modifica
- Risultato test di coerenza

### Gestione anomalie TASK-2

Se il README non ha una sezione riconoscibile con il contatore tool:
→ Cerca il pattern numerico associato a "tool" o "MCP" nel file.
→ Se non trovi nulla, aggiungi una riga chiara nella sezione appropriata
e documenta nel report.

Se `test_tool_counter_consistency` cerca un pattern diverso da quello che
hai aggiornato:
→ Leggi il test nella sua interezza, identifica esattamente il pattern
atteso, e aggiorna il file corretto.
Non modificare il test.

Se il conteggio reale è diverso da 50 (es. qualche tool è stato rimosso
o aggiunto nel branch senza aggiornare la docstring):
→ Usa il conteggio reale come valore di verità.
→ Aggiorna sia `engine.py` che `README.md` al valore reale.
→ Documenta nel report la divergenza trovata.

---

## TASK-3 — Verifica strutturale dei 2 nuovi tool MCP

### Obiettivo

Verificare che `scf_list_plugins` e `scf_install_plugin` siano
correttamente registrati nell'engine, raggiungibili via import e che
la loro logica non produca errori su import o istanziazione.

Il test è strutturale: non richiede un server MCP attivo —
verifica correttezza via `py_compile`, import test e
ispezione del codice.

### Procedura

**Step 1 — Lettura integrale**
Leggi `spark/boot/tools_plugins.py` nella sua interezza.
Individua le definizioni di `scf_list_plugins` e `scf_install_plugin`.

**Step 2 — Verifica import chain**
Verifica che tutti i simboli importati nelle due funzioni esistano
realmente nei moduli dichiarati:

- `PluginManager` da `spark.plugins` (o `spark.plugins.manager`)
- `list_available_plugins` da `spark.plugins`
- `download_plugin` da `spark.plugins`
- `RegistryClient` da `spark.registry.client` (se usato)
- Qualsiasi altro simbolo usato nei due tool

Per ogni simbolo, traccia il percorso: file sorgente → `__init__.py`
del modulo → funzione nel tool. Se un simbolo è mancante o il percorso
è rotto, correggi l'export mancante nel `__init__.py` appropriato.

**Step 3 — Verifica gestione errori nei tool**
Controlla che entrambi i tool restituiscano sempre una risposta
strutturata (stringa o dict) anche in caso di eccezione.
Il pattern corretto è:

```python
try:
    # logica tool
    return risultato_ok
except Exception as exc:
    _log.error("[SPARK-ENGINE][ERROR] scf_xxx: %s", exc)
    return f"ERRORE: {exc}"
```

Se manca il try/except o l'eccezione non è gestita, aggiungilo.

**Step 4 — Test import sintetico**
Esegui:

```
python -c "from spark.plugins import PluginManager, download_plugin, list_available_plugins; print('OK')"
```

Se fallisce con `ImportError` o `ModuleNotFoundError`, analizza
la traccia, correggi il problema nel file corretto e ri-esegui.

**Step 5 — Suite completa finale**
Esegui:

```
python -m pytest -q --ignore=tests/test_integration_live.py
```

La suite deve confermare 446 passed, 9 skipped, 0 failed (o più
se sono stati aggiunti test nei task precedenti).

**Step 6 — Report finale consolidato**
Salva il report in `docs/reports/SPARK-REPORT-DualMode-PostFix-v1.0.md`
con il formato seguente:

```
# SPARK Dual-Mode Post-Fix — Report v1.0

## TASK-1 — manager.py audit
[risultati]

## TASK-2 — README contatore
[risultati]

## TASK-3 — Tool MCP verifica
[risultati]

## File modificati
[lista con path e descrizione modifica]

## Suite test finale
[output pytest]

## Stato finale
PRONTO PER MERGE
oppure
BLOCCHI APERTI: [lista dettagliata]
```

### Gestione anomalie TASK-3

Se il test import al Step 4 fallisce per dipendenza esterna
(es. `requests` non installato nell'env):
→ Non modificare il codice.
→ Documenta nel report il problema di ambiente e marca il punto
come "non verificabile in locale — verificare in env completo".
→ Procedi comunque con Step 5.

Se uno dei due tool non è registrato in `register_plugin_tools()`
in `tools_plugins.py`:
→ Aggiungilo seguendo il pattern degli altri tool nello stesso file.
→ Aggiorna il contatore in `engine.py` e `README.md` di conseguenza.

Se la suite scende sotto 446 passed per un fallimento causato
dai tuoi interventi nei 3 task:
→ Non procedere al merge.
→ Annulla la modifica specifica, ripristina, ri-esegui, documenta.
→ Se non riesci a risolvere, segnala nel report finale con
flag `BLOCCHI APERTI` e descrizione dettagliata del problema.

---

## Checklist pre-commit (obbligatoria dopo tutti i task)

- [ ] `python -m py_compile` su ogni file modificato: nessun errore
- [ ] Suite non-live: >= 446 passed, 0 failed
- [ ] Nessun `print()` su stdout in file toccati
- [ ] Contatore tool in `engine.py` == contatore in `README.md` == contatore reale
- [ ] Report salvato in `docs/reports/SPARK-REPORT-DualMode-PostFix-v1.0.md`
