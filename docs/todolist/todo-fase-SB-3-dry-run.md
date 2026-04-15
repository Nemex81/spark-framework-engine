# Fase SB-3 — Dry-run manifest spark-base

Stato attuale: Non avviata

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 3)
- Tool engine: `scf_plan_install` (presente da v1.9.0, NON `scf_preview_install` che non esiste)

Dipendenze:

- SB-1 deve essere completata (repo spark-base pubblico e accessibile)
- SB-4 deve essere completata

Checklist:

- [ ] Eseguire `scf_plan_install("spark-base")`
- [ ] Verificare `can_install: true` nel risultato
- [ ] Verificare `dependency_issues: []`
- [ ] Analizzare `conflict_plan`:
  - [ ] Se `conflict_plan: []`: step 5 può usare `conflict_mode` default (`"abort"`)
  - [ ] Se `conflict_plan` contiene `conflict_untracked_existing`: documentare i file
        e pianificare `conflict_mode="replace"` nel step 5 per quei path
- [ ] Verificare che `write_plan` contenga il numero atteso di file (~69)
- [ ] Annotare eventuali file in `preserve_plan` (già tracciati con hash diverso)

Criteri di uscita:

- `scf_plan_install("spark-base")` restituisce `success: true`
- `can_install: true` (o `can_install_with_replace: true` se ci sono file untracked)
- Nessun `dependency_issues` bloccante
- Conflict mode documentato per lo step 5

Note operative:

- Questo step è RACCOMANDATO, NON bloccante: se il dry-run conferma il write plan atteso,
  lo step 5 può procedere con sicurezza.
- I file in `.github/prompts/*.prompt.md` potrebbero comparire come `conflict_untracked_existing`
  se erano già presenti nel workspace ma non tracciati nel manifest.
  In questo caso usare `conflict_mode="replace"` nello step 5.3.
- `scf_plan_install` non scrive NULLA nel workspace — operazione completamente safe.
- `scf_plan_install` risolve il manifest del pacchetto via registry + `repo_url` GitHub pubblico.
  Un registry locale aggiornato senza repository remoto pubblicato NON basta per eseguire lo step.
