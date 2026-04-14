# Fase 4 — Modalità auto (risoluzione AI)

Stato iniziale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezioni 6, 8, 12)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 4, dettaglio 3.4)

Checklist:
- [x] Implementare `scf_resolve_conflict_ai` tool MCP
- [x] Implementare i validator `validate_structural`, `validate_completeness`, `validate_tool_coherence`
- [x] Integrare pipeline auto in `scf_update_package`
- [x] Gestire fallback best-effort non sicuro → degradamento a `manual`
- [x] Scrivere test `tests/test_merge_validators.py`

Criteri di uscita:
- Pipeline auto valida e degrada correttamente in caso di validator falliti
- Conflitti su frontmatter degradano sempre a `manual`

Note di validazione:
- Verificare che la risoluzione best-effort non includa path assoluti o SHA nei payload di sessione
- Controllare i risultati dei validator in `validator_results`
