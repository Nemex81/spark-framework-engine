---
spark: true
scf_file_role: "prompt"
scf_version: "1.2.0"
scf_merge_strategy: "replace"
scf_protected: false
scf_owner: "spark-base"
scf_merge_priority: 10
---
# Prompt Files — Framework Copilot

Indice dei prompt files nella cartella `.github/prompts/`.
I prompt si attivano dal file picker di VS Code (scrivi `#` in chat)
o digitando il nome del file con `#`.
Usano variabili di input con sintassi `${input:label}`.

## Prompt presenti

- `project-setup.prompt.md` — setup iniziale framework
  (nessun input — flusso guidato Agent-Welcome OP-1)
- `project-update.prompt.md` — aggiornamento profilo progetto
  (input opzionale — help automatico se vuoto)
- `init.prompt.md` — avvia nuovo task, suggerisce agente appropriato
- `start.prompt.md` — riprendi codifica dal primo task non completato in TODO.md
- `status.prompt.md` — mostra stato attuale del workflow in corso
- `sync-docs.prompt.md` — avvia Agent-Docs per sync documentazione
- `release.prompt.md` — avvia Agent-Release per versioning e build
- `help.prompt.md` — spiega come funziona un agente specifico
- `git-commit.prompt.md` — wrapper agent commit (input opzionale PUSH per commit + push immediato)
- `git-merge.prompt.md` — wrapper agent merge (delega ad Agent-Git)
- `orchestrate.prompt.md` — ciclo E2E completo tramite Agent-Orchestrator
- `framework-update.prompt.md` — aggiorna AGENTS.md e copilot-instructions.md
- `framework-changelog.prompt.md` — aggiunge voce a FRAMEWORK_CHANGELOG.md
- `framework-release.prompt.md` — consolida [Unreleased] in una versione rilasciata
- `framework-unlock.prompt.md` — sblocca temporaneamente i path protetti del framework
- `scf-check-updates.prompt.md` — verifica aggiornamenti disponibili per i pacchetti SCF installati
- `scf-install.prompt.md` — installa un pacchetto SCF con anteprima e conferma esplicita
- `scf-list-available.prompt.md` — elenca i pacchetti SCF disponibili nel registry
- `scf-list-installed.prompt.md` — mostra i pacchetti SCF installati nel workspace
- `scf-migrate-workspace.prompt.md` — guida la migrazione di workspace legacy verso policy update e marker SCF
- `scf-package-info.prompt.md` — mostra il dettaglio di un pacchetto SCF specifico
- `scf-pre-implementation-audit.prompt.md` — esegue un audit read-only prima di modifiche ecosistema
- `scf-remove.prompt.md` — rimuove un pacchetto SCF installato con conferma esplicita
- `scf-status.prompt.md` — riepiloga stato workspace e pacchetti SCF installati
- `scf-update-policy.prompt.md` — mostra o aggiorna la policy update del workspace SCF
- `scf-update.prompt.md` — pianifica e applica aggiornamenti dei pacchetti SCF

## Note

- I prompt `project-setup` e `project-update` delegano ad Agent-Welcome.
- I prompt `git-commit` e `git-merge` sono wrapper agent e delegano ad Agent-Git.
- Il prompt `framework-unlock` abilita una finestra controllata di modifica
  dei componenti protetti del framework.
- Documento di riferimento: questo file per l'indice prompt e [AGENTS.md](../AGENTS.md) per l'indice agenti.
