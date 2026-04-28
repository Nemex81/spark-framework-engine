# Fase SB-0 — Preflight workspace

Stato attuale: Completata

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 0)
- Analisi: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Step 0)

Checklist:

- [x] Eseguire `git status` — verificare nessun file non committed nei repo di sviluppo coinvolti (`scf-master-codecrafter`, `scf-registry`, `scf-pycode-crafter`)
- [x] Eseguire `scf_verify_workspace` — verificare `is_clean: true`
- [x] Verificare `modified: []` nel risultato
- [x] Verificare `missing: []` nel risultato
- [x] Se `orphan_candidates` non è vuoto: documentare ma non bloccare

Criteri di uscita:

- `scf_verify_workspace` restituisce `is_clean: true`
- `modified: []` — nessun file hash mismatch rispetto al manifest
- Se il workspace non è pulito: **blocco totale**. Nessuna fase successiva può partire.

Note operative:

- Se `modified` contiene file: capire se sono modifiche intenzionali o drift.
  In caso di drift: reinstallare il pacchetto corrispondente con `scf_install_package`.
  In caso di modifiche intenzionali: committare prima di procedere.
- Questa fase è la più importante: un workspace sporco durante la migrazione
  può rendere irreversibile la perdita di modifiche utente.
- Gate eseguito sui workspace reali `tabboz-simulator-202` e `uno-ultra-v68`.
- `uno-ultra-v68` mostra `orphan_candidates` e `untagged_spark_files` nei runtime snapshot, ma il report
  resta `is_clean: true` con `modified: []`, `missing: []`, `duplicate_owners: []`.
