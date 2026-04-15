# Fase SB-0 — Preflight workspace

Stato attuale: In corso

Riferimenti:
- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 0)
- Analisi: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Step 0)

Checklist:
- [x] Eseguire `git status` — verificare nessun file non committed nei repo di sviluppo coinvolti (`scf-master-codecrafter`, `scf-registry`, `scf-pycode-crafter`)
- [ ] Eseguire `scf_verify_workspace` — verificare `is_clean: true`
- [ ] Verificare `modified: []` nel risultato
- [ ] Verificare `missing: []` nel risultato
- [ ] Se `orphan_candidates` non è vuoto: documentare ma non bloccare

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
- Nel workspace corrente multi-root non è stato ancora eseguito il vero `scf_verify_workspace`
  del target utente da migrare. Questo gate resta obbligatorio prima di SB-5.
