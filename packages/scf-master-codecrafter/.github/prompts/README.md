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

- `help.prompt.md` — spiega come funziona un agente specifico
- `git-commit.prompt.md` — wrapper agent commit (delega ad Agent-Git condiviso)
- `git-merge.prompt.md` — wrapper agent merge (delega ad Agent-Git condiviso)
- `framework-update.prompt.md` — aggiorna AGENTS.md e copilot-instructions.md
- `framework-release.prompt.md` — consolida [Unreleased] in una versione rilasciata
- `framework-unlock.prompt.md` — sblocca temporaneamente i path protetti del framework
- `package-update.prompt.md` — aggiorna i pacchetti SCF installati nel workspace

## Note

- I prompt `git-commit` e `git-merge` sono wrapper agent e delegano ad Agent-Git.
- Il prompt `framework-unlock` abilita una finestra controllata di modifica
  dei componenti protetti del framework.
- I prompt framework e workflow condivisi rimossi da questa cartella sono ora forniti dal layer `spark-base`.
- Documento di riferimento completo: [AGENTS.md](../AGENTS.md) sezione "Prompt Files".
