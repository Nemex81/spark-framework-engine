---
scf_protected: false
scf_file_role: "instruction"
name: python
applyTo: "**/*.py"
scf_merge_strategy: "replace"
scf_version: "2.0.1"
package: scf-pycode-crafter
scf_merge_priority: 30
scf_owner: "scf-pycode-crafter"
spark: true
version: 2.0.1
---

# Instruction: Python

Questa instruction si applica a tutti i file `.py` del workspace.

## Standard

- Python 3.10+ con type hints obbligatori per funzioni pubbliche
- Docstring per moduli, classi pubbliche e funzioni pubbliche
- f-string per formattazione stringhe
- `pathlib.Path` per operazioni su file (no `os.path`)
- Dataclass per strutture dati semplici
- Context manager per risorse (file, connessioni, lock)

## Stile

- Nomi variabili e funzioni in `snake_case`
- Nomi classi in `PascalCase`
- Costanti in `UPPER_SNAKE_CASE`
- Lunghezza riga max 100 caratteri
- Import ordinati: stdlib, third-party, locale (isort/ruff)

## Errori

- Gestione esplicita con eccezioni tipizzate
- Non usare `except Exception` senza motivazione
- Non sopprimere eccezioni con `pass`
- Log degli errori prima di ri-sollevare

## Test

- Framework: pytest
- File di test: `tests/test_<nome_modulo>.py`
- Naming: `test_<cosa>_<condizione>_<risultato_atteso>`
- Evita mock eccessivi: testa comportamenti, non implementazioni
