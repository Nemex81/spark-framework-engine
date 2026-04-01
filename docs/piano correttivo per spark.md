# Prompt operativo per Copilot — spark-framework-engine

Questo prompt deve essere eseguito da GitHub Copilot in Agent mode nella sessione VS Code con il workspace `spark-framework-engine.code-workspace` aperto. Esegui ogni modifica in modo atomico, verificando il risultato prima di passare al punto successivo. Non chiedere conferme intermedie: procedi in autonomia su tutti i punti.

---

## Contesto

Repository: `spark-framework-engine`  
File principale: `spark-framework-engine.py`  
Interventi richiesti: F4, F5, F13 + pulizia minore `.gitignore`

---

## Esito validazione sistemica

Esito complessivo: **validazione parziale**.

- **F5 (`.gitignore`)**: valido. L'aggiunta di `scripts/*.out` e la rimozione del commento `#.github/` sono coerenti con il repo e non impattano gli altri due repository dell'ecosistema.
- **F4 (`scripts/run_scf_list.py`)**: valido nel merito. Il problema descritto e' reale: lo script corrente fallisce con `scf_list_available_packages not found` perche' cerca una closure non esposta nei globals del modulo.
- **F13 (`CHANGELOG.md`)**: **non valido nello stato attuale del sistema**. L'introduzione di una sezione iniziale `[Unreleased]` rompe una invariante oggi verificata dal repo:
    - `tests/test_engine_coherence.py` assume che la **prima** voce `## [...]` di `CHANGELOG.md` coincida con `ENGINE_VERSION`.
    - `.github/instructions/spark-engine-maintenance.instructions.md` richiede che `ENGINE_VERSION` e l'ultima voce di `CHANGELOG.md` restino allineate.
    - Il tooling del motore e la documentazione di manutenzione trattano quindi la prima voce versionale come release canonica corrente.

Decisione operativa: questo piano viene corretto per implementare **solo F5 + F4 + pulizia `.gitignore`**. L'adozione di `[Unreleased]` viene rinviata a un change-set separato e coordinato.

---

## Intervento 1 — F5: aggiungere `scripts/*.out` a `.gitignore`

**File da modificare:** `.gitignore`

Apri `.gitignore`. Trova il blocco dei commenti relativi ai log (`# Logs`) o dei file temporanei. Aggiungi la seguente riga nella sezione più appropriata, subito dopo la riga `*.log` oppure nella sezione `# SCF-specific caches` in fondo al file:

```
scripts/*.out
```

Non toccare nessun'altra riga del file. Non rimuovere la riga `#.github/` — quella verrà gestita nel punto 4.

**Verifica:** Dopo la modifica, `.gitignore` deve contenere la riga `scripts/*.out`.

---

## Intervento 2 — F4: riscrivere `scripts/run_scf_list.py`

**File da sostituire interamente:** `scripts/run_scf_list.py`

Il contenuto attuale è non funzionale perché usa `runpy.run_path` per trovare `scf_list_available_packages` nei globals del modulo, ma quella funzione è definita come closure dentro `register_tools()` e non viene mai esposta ai module globals. Il risultato è sempre `f = None`.

Sostituisci l'intero contenuto del file con questo:

```python
"""
scripts/run_scf_list.py — Lista i pacchetti disponibili nel registry SCF.

Uso: python scripts/run_scf_list.py

Istanzia RegistryClient direttamente senza passare per il server MCP.
Richiede connessione internet per contattare il registry pubblico.
"""
import json
import sys
import os

# Aggiungi la root del progetto al path in modo da trovare il modulo engine.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from pathlib import Path
    # Import delle classi pubbliche del motore.
    # Il modulo usa un nome con trattini: lo importiamo con importlib.
    import importlib.util
    engine_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "spark-framework-engine.py"
    )
    spec = importlib.util.spec_from_file_location("spark_engine", engine_path)
    engine_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine_module)

    RegistryClient = engine_module.RegistryClient

    # Usa una directory temporanea come github_root per la cache.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        client = RegistryClient(github_root=Path(tmp_dir))
        packages = client.list_packages()

    if not packages:
        print(json.dumps({"ok": True, "count": 0, "packages": []}, ensure_ascii=False))
        sys.exit(0)

    result = [
        {
            "id": p.get("id"),
            "description": p.get("description", ""),
            "latest_version": p.get("latest_version", ""),
            "status": p.get("status", "unknown"),
        }
        for p in packages
    ]
    print(json.dumps({"ok": True, "count": len(result), "packages": result}, indent=2, ensure_ascii=False))

except Exception as exc:
    import traceback
    tb = traceback.format_exc()
    print(json.dumps({"ok": False, "error": str(exc), "traceback": tb}, ensure_ascii=False))
    sys.exit(1)
```

**Verifica:** Esegui `python scripts/run_scf_list.py` dalla root del progetto. Il risultato atteso è un JSON con `"ok": true` e la lista dei pacchetti (o un array vuoto se il registry non è raggiungibile). Non deve più apparire `scf_list_available_packages not found`.

---

## Intervento 3 — F13: sospeso in questo change-set

**File interessato:** `CHANGELOG.md`

**Non modificare `CHANGELOG.md` in questo piano correttivo.**

La proposta originale di inserire una sezione iniziale `[Unreleased]` non e' coerente con lo stato attuale del motore. Prima di adottarla serve un intervento dedicato che aggiorni in modo coordinato almeno:

1. `tests/test_engine_coherence.py`, in modo che ignori un eventuale header `[Unreleased]` e confronti `ENGINE_VERSION` con la prima voce semver reale.
2. Le regole di manutenzione e release che oggi assumono che la prima voce di `CHANGELOG.md` sia la release corrente.
3. La procedura di bump versione, per chiarire quando `[Unreleased]` va svuotato o materializzato in una release numerata.

**Verifica:** `CHANGELOG.md` resta invariato in questo change-set e i test di coerenza continuano a passare.

---

## Intervento 4 — Pulizia `.gitignore`: rimuovere riga commentata `#.github/`

**File da modificare:** `.gitignore`

Apri `.gitignore`. Trova la riga:

```
#.github/
```

Rimuovila. Non toccare nessun'altra riga del file.

**Contesto:** Questa riga è un commento senza contesto lasciato probabilmente da un test rimosso. Non ha valore documentale e genera confusione nell'analisi del repo.

**Verifica:** Il file non deve più contenere la riga `#.github/`.

---

## Ordine di esecuzione

Esegui gli interventi nell'ordine indicato: 1 → 2 → 3 → 4.

Dopo ogni modifica, prima di procedere al punto successivo, verifica che:
- Il file modificato sia sintatticamente corretto (per `.py`: nessun errore di parse; per `.md` e `.gitignore`: struttura integra).
- Nessun altro file del progetto sia stato toccato.

---

## Cosa NON fare

- Non modificare `spark-framework-engine.py`.
- Non toccare file nella directory `tests/`.
- Non rimuovere né modificare le regole esistenti di `.gitignore` oltre a quanto specificato.
- Non fare commit — lascia le modifiche staged o unstaged, sarà l'utente a decidere.
- Non aggiungere dipendenze esterne al progetto.

---

## Risultato atteso al termine

Due file modificati:
1. `.gitignore` — aggiunta `scripts/*.out`, rimossa `#.github/`
2. `scripts/run_scf_list.py` — riscritto funzionante

Nessun altro file alterato. Nessun test rotto (verifica con `pytest -q` dalla root se l'ambiente lo consente).
