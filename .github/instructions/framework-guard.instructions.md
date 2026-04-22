---
scf_protected: false
scf_file_role: "instruction"
name: framework-guard
applyTo: "**"
scf_merge_strategy: "replace"
scf_version: "1.2.0"
package: scf-master-codecrafter
scf_merge_priority: 10
scf_owner: "spark-base"
spark: true
version: 1.0.0
---

# Framework Guard

- Proteggi i file framework sotto `.github/**` da modifiche accidentali.
- Se il task richiede scrittura su componenti protetti, verifica prima il perimetro richiesto.
- Le modifiche al framework devono restare separate dal codice applicativo.
- Non autorizzare sblocchi impliciti: i cambi di perimetro vanno dichiarati esplicitamente.