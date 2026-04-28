# Fase 5 — Modalità assisted (approvazione utente)

Stato iniziale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezioni 6, 7, 11)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 5, dettaglio 3.5)

Checklist:
- [x] Implementare `scf_approve_conflict` e `scf_reject_conflict` tool MCP
- [x] Estendere lo schema sessione con `resolution_status`, `proposed_text`, `validator_results` e stato `approved`
- [x] Gestire approve/reject per singolo conflitto e bloccare `scf_finalize_update` finche' restano marker manuali
- [x] Scrivere coverage assisted in `tests/test_merge_session.py` e `tests/test_merge_integration.py`

Criteri di uscita:
- Flusso assisted end-to-end testato (approve/reject/finalize)
- `remaining_conflicts` aggiornato correttamente

Note di validazione:
- Verificare che approve richieda `proposed_text` non-NULL
- Verificare che rejected produca marcatori nella finalizzazione
