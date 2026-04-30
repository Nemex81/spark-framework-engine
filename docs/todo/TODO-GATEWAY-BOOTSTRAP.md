# TODO — Gateway Bootstrap
Riferimento piano: docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md — Intervento 1
Priorità: P0
Dipende da: nessuno

## Task specifici
- [ ] Verificare che scf_bootstrap_workspace copi solo i file gateway Layer 0
- [ ] Garantire idempotenza tramite sentinella
- [ ] Aggiornare commenti e docstring per chiarezza

## Criteri di completamento
- Solo i file gateway sono copiati in .github/
- Nessun file utente sovrascritto senza consenso
- Funzione idempotente e documentata
