---
spark: true
scf_file_role: "skill"
scf_version: "2.0.1"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_merge_priority: 30
---
# Errori Python comuni — Reference

## Import

| Errore | Causa probabile | Soluzione |
|--------|----------------|-----------|
| `ModuleNotFoundError: No module named 'X'` | Modulo non installato o venv non attivo | `pip install X` oppure attiva il venv |
| `ImportError: cannot import name 'Y' from 'X'` | Nome errato o versione sbagliata | Verifica API della versione installata |
| `CircularImportError` | Import circolare tra moduli | Ristruttura con dependency injection |

## Mypy

| Errore | Soluzione |
|--------|-----------|
| `Incompatible types in assignment` | Controlla il type hint della variabile |
| `Item "None" of "Optional[X]" has no attribute` | Aggiungi guard `if x is not None:` |
| `Cannot find implementation or library stub` | Installa `types-X` o aggiungi `# type: ignore` |
| `Missing return statement` | Aggiungi `return` o gestisci tutti i branch |

## Pytest

| Errore | Soluzione |
|--------|-----------|
| `FAILED test_X - AssertionError` | Leggi il diff, confronta expected vs actual |
| `fixture 'Y' not found` | Verifica `conftest.py` e scope della fixture |
| `ImportError` nei test | Verifica `__init__.py` e struttura package |
| `RecursionError` | Mock le dipendenze circolari nei test |
