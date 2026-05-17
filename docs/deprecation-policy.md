# SPARK Deprecation Policy

> ENGINE_VERSION: 3.6.0 — Prima applicazione: `spark/boot/wizard.py`

Questo documento definisce il ciclo di vita formale delle funzionalità deprecate
nel motore SPARK e i criteri per la rimozione.

---

## Livelli di deprecation

| Livello | Stato | Descrizione |
|---------|-------|-------------|
| `soft-deprecated` | In uso, sconsigliato | Il modulo emette `DeprecationWarning` a runtime. La funzionalità è ancora operativa. Il CHANGELOG registra la deprecazione con alternativa raccomandata. |
| `hard-deprecated` | In uso, da rimuovere | Come `soft-deprecated` ma con scadenza dichiarata (versione target di rimozione). I test dedicati restano attivi. |
| `removed` | Non più disponibile | Il modulo o la funzione è eliminata. I test dedicati sono rimossi. Il CHANGELOG registra la rimozione con riferimento al ciclo applicato. |

---

## Criteri per avanzare da un livello all'altro

### Da `soft-deprecated` a `removed`

Tutti i seguenti criteri devono essere soddisfatti:

1. Il modulo emette `DeprecationWarning` da almeno 1 ciclo di sviluppo.
2. Nessun launcher runtime o tool MCP pubblico importa il modulo direttamente.
3. I test dedicati sono stati aggiornati (`filterwarnings` o rimozione).
4. La suite pytest chiude a 0 failed dopo la rimozione.
5. La voce CHANGELOG `### Removed` è scritta prima della rimozione fisica.

### Dall'uso live alla `soft-deprecated`

1. Aggiungere `warnings.warn(..., DeprecationWarning, stacklevel=2)` all'inizio
   della funzione o al livello di modulo.
2. Aggiornare la docstring con la sezione `Deprecated:` (Google Style).
3. Registrare nel CHANGELOG `[Unreleased] ### Deprecated`.

---

## Template voce CHANGELOG per rimozione

```markdown
### Removed

- `<path/module.py>`: rimosso — deprecato dalla versione <X.Y.Z> (CICLO N).
  Alternativa raccomandata: `<path/alternativo.py>`.
  Prima applicazione della Deprecation Policy: `docs/deprecation-policy.md`.
```

---

## Primo caso applicato — `spark/boot/wizard.py`

| Fase | Versione | Descrizione |
|------|----------|-------------|
| `soft-deprecated` | 3.6.0 (CICLO 6) | `run_wizard()` emette `DeprecationWarning`. Boot path unificato verso `spark.cli.startup`. |
| `removed` | 3.7.0 (CICLO 7) | Modulo rimosso. `tests/test_wizard_init.py` eliminato. Docstring stale in `scf_universal.py` corretta. |

Alternativa raccomandata: `spark.cli.startup.run_startup_flow()` e menu `spark.cli.main`.
