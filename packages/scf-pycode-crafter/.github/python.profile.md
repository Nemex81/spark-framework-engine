---
scf_protected: false
scf_owner: "scf-pycode-crafter"
scf_version: "2.0.1"
scf_file_role: "config"
scf_merge_priority: 30
plugin: scf-pycode-crafter
spark: true
scf_merge_strategy: "replace"
---

# Python Plugin Profile

Questo file descrive il profilo tecnico del plugin Python.

- Linguaggio: Python
- Type checking: mypy
- Linting: ruff
- Test runner: pytest
- Convenzioni: type hints obbligatori, docstring, validazione prima del commit