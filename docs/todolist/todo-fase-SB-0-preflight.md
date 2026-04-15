# Fase SB-0 — Preflight workspace

Stato attuale: Non avviata

Riferimenti:
- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 0)
- Analisi: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](../ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md) (Step 0)

Checklist:
- [ ] Eseguire `git status` — verificare nessun file non committed nel workspace
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
