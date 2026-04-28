# Fase 2 — Integrazione nel flusso install/update

Stato iniziale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezioni 3, 5, 11)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 2, dettaglio 3.2)

Checklist:
- [x] Estendere `_classify_install_files` con `merge_candidate` e fallback preservativo quando BASE manca
- [x] Aggiungere `conflict_mode` ai tool `scf_install_package` e `scf_update_package`
- [x] Implementare il percorso di merge manuale integrando `MergeEngine` e `SnapshotManager`
- [x] Popolare i nuovi campi additivi nel risultato `_build_install_result`
- [x] Scrivere test di integrazione `tests/test_merge_integration.py`

Criteri di uscita:
- Test non-regressione per `abort` e `replace` passano
- `scf_update_package(conflict_mode="manual")` ritorna `session_id` quando necessario

Note di validazione:
- Verificare fallback quando snapshot assente (`base_unavailable: true`)
- Verificare che file binari finiscano in `snapshot_skipped`
