# Fase 3 — Sessioni di merge stateful

Stato iniziale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezione 7)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 3, dettaglio 3.3)

Checklist:
- [x] Implementare `MergeSessionManager` con metodi CRUD e `cleanup_expired_sessions`
- [x] Implementare `_atomic_write_json(path)` con file `.tmp` nella stessa directory e `os.replace()`
- [x] Aggiungere tool MCP `scf_finalize_update` e integrarlo nella `register_tools()`
- [x] Aggiungere cleanup automatico all'avvio dei tool citati
- [x] Scrivere test `tests/test_merge_session.py`

Criteri di uscita:
- `scf_finalize_update` finalizza la sessione e aggiorna manifest/snapshot
- La scrittura JSON è atomica (test di crash simulato)

Note di validazione:
- Verificare che `_atomic_write_json` usi `os.replace()` e fsync opzionale
- Controllare comportamento su Windows e presenza di file `.tmp` all'avvio
