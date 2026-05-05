---
spark: true
scf_file_role: "prompt"
scf_version: "2.1.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "scf-master-codecrafter"
scf_merge_priority: 20
---
# Prompt Files — Framework Copilot

Indice dei prompt files nella cartella `.github/prompts/`.
I prompt si attivano dal file picker di VS Code (scrivi `#` in chat)
o digitando il nome del file con `#`.
Usano variabili di input con sintassi `${input:label}`.

## Prompt presenti

Nessun prompt esclusivo in questo pacchetto.
I prompt framework e workflow condivisi sono forniti dal layer `spark-base`.

## Note

- I prompt framework e workflow condivisi rimossi da questa cartella sono ora forniti dal layer `spark-base`.
- Documento di riferimento completo: [AGENTS.md](../AGENTS.md) sezione "Prompt Files".
