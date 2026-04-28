# Fase 0 — Infrastruttura snapshot BASE

Stato attuale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezioni 3, 10)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 0, dettaglio 3.0)

Checklist:
- [x] Implementare `SnapshotManager` (CRUD)
- [x] Integrare save snapshot in `scf_install_package`
- [x] Integrare save snapshot in `scf_bootstrap_workspace` con package_id `spark-framework-engine`
- [x] Integrare delete snapshot in `scf_remove_package`
- [x] Aggiungere test unitari `tests/test_snapshot_manager.py`
- [x] Eseguire validazione con `pytest -q tests/test_snapshot_manager.py`

Criteri di uscita:
- Tutti i test `tests/test_snapshot_manager.py` passano
- La scrittura snapshot avviene sotto `.github/runtime/snapshots/`

Note di validazione:
- Verificare che i path relativi siano validati contro path traversal
- Verificare che i file binari siano inseriti in `snapshot_skipped`

Rischi/Note:
- Controllare I/O error handling e non bloccare l'installazione in caso di fallimento snapshot
