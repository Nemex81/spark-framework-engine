# Fase SB-3 — Dry-run manifest spark-base

Stato attuale: Completata

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 3)
- Tool engine: `scf_plan_install` (presente da v1.9.0, NON `scf_preview_install` che non esiste)

Dipendenze:

- SB-1 deve essere completata (repo spark-base pubblico e accessibile)
- SB-4 deve essere completata

Checklist:

- [x] Eseguire `scf_plan_install("spark-base")`
- [x] Verificare `can_install_with_replace: true` nel risultato
- [x] Verificare `dependency_issues: []`
- [x] Analizzare `conflict_plan`:
  - [x] `conflict_plan` contiene 9 file `conflict_untracked_existing`
  - [x] Documentare i file e pianificare `conflict_mode="replace"` nel step 5
- [x] Verificare che `write_plan` sia coerente con il manifest corrente (`spark-base@1.2.0`, 79 file)
- [x] Annotare eventuali file in `preserve_plan` (risultato: `preserve_plan: []`)

Criteri di uscita:

- `scf_plan_install("spark-base")` restituisce `success: true`
- `can_install: true` (o `can_install_with_replace: true` se ci sono file untracked)
- Nessun `dependency_issues` bloccante
- Conflict mode documentato per lo step 5

Note operative:

- Questo step è RACCOMANDATO, NON bloccante: se il dry-run conferma il write plan atteso,
  lo step 5 può procedere con sicurezza.
- Dry-run eseguito su `uno-ultra-v68`.
- I 9 conflitti untracked rilevati erano i prompt:
  `scf-check-updates`, `scf-install`, `scf-list-available`, `scf-list-installed`,
  `scf-package-info`, `scf-pre-implementation-audit`, `scf-remove`, `scf-status`, `scf-update`.
- Per questo workspace lo step 5.3 deve usare `conflict_mode="replace"`.
- `scf_plan_install` non scrive NULLA nel workspace — operazione completamente safe.
- `scf_plan_install` risolve il manifest del pacchetto via registry + `repo_url` GitHub pubblico.
  Un registry locale aggiornato senza repository remoto pubblicato NON basta per eseguire lo step.
