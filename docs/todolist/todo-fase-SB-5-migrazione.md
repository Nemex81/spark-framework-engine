# Fase SB-5 — Migrazione workspace utente

Stato attuale: Completata con nota

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 5)
- Analisi rischi: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Rischi Residui)

Dipendenze:

- SB-0 completata (workspace pulito)
- SB-3 completata (conflict mode noto)
- SB-4 completata (registry aggiornato)

⚠ Eseguire l'intera sequenza in una **singola sessione** senza interruzioni.
Non aprire Copilot Agent mode durante la transizione (SB-5.2 → SB-5.4).

Checklist:

- [x] 5.1 Pre-migrazione backup:
  - [ ] `git status` → nessun file uncommitted
  - [x] `scf_verify_workspace` → `is_clean: true` (gate finale pre-remove)
- [x] 5.2 `scf_remove_package("scf-master-codecrafter")`:
  - [x] Verificare output: `success: true`
  - [x] Annotare eventuali `preserved_user_modified` (risultato: `[]`)
  - [x] Annotare `deleted_snapshots` (12 snapshot rimossi)
- [x] 5.3 `scf_install_package("spark-base")` (usare `conflict_mode="replace"` se SB-3 ha rilevato file untracked):
  - [x] Verificare `success: true`
  - [x] Verificare `installed` count = 79
  - [x] Verificare che i conflitti untracked siano stati gestiti con `replace`
  - [x] Verificare `preserved: []` (conferma workspace manifest-clean)
- [x] 5.4 `scf_install_package("scf-master-codecrafter")`:
  - [x] Verificare `success: true`
  - [x] Verificare `installed` count = 14
  - [x] Verificare che la dependency `spark-base` sia già installata (nessun errore `missing_dependencies`)
- [x] 5.5 `scf_verify_workspace` → `is_clean: true`

Criteri di uscita:

- Tutti e 5 i sotto-step completati con `success: true`
- `scf_verify_workspace` restituisce `is_clean: true` dopo 5.5
- 2 pacchetti installati nel manifest al termine della migrazione base/core-craft

Note operative:

- La "broken window" (workspace temporaneamente senza agenti) dura ~10–30 secondi tra 5.2 e 5.4.
- Esecuzione reale completata sul workspace `uno-ultra-v68`.
- Nota operativa: il repo target non era git-clean (`.github/**` e `.code-workspace` non tracciati),
  ma il gate vincolante per la migrazione è rimasto il preflight manifest (`is_clean: true`).
- Se 5.3 fallisce per `conflict_cross_owner`: significa che il remove non ha funzionato correttamente.
  Verificare che `scf_remove_package` abbia restituito `success: true`.
- Se 5.3 fallisce per `conflict_untracked_existing` con le prompt: usare `conflict_mode="replace"`.
- Se 5.4 fallisce per dipendenza mancante: verificare che 5.3 sia completata correttamente
  (`scf_list_installed_packages` deve mostrare `spark-base`).
