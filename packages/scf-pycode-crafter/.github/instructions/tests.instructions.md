---
scf_protected: false
scf_file_role: "instruction"
name: tests
applyTo: "tests/**/*.py"
scf_merge_strategy: "replace"
scf_version: "2.0.1"
package: scf-pycode-crafter
scf_merge_priority: 30
scf_owner: "scf-pycode-crafter"
spark: true
version: 2.0.1
---

# Instruction: Tests

Questa instruction si applica a tutti i file in `tests/`.

- Framework: pytest
- Un file di test per ogni modulo sorgente
- Naming test: `test_<cosa>_<condizione>_<risultato_atteso>`
- Usa fixture pytest per setup condiviso
- Isola i test: ogni test deve essere indipendente dagli altri
- Non usare `print()` nei test — usa `logging` o assert
- Mock solo le dipendenze esterne (I/O, rete, DB)
- Non testare implementazioni interne — testa comportamenti osservabili
- Coverage minima logica di business: 70%
