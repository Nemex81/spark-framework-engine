# Fase 6 — Policy multi-owner

Stato iniziale: Completata

Riferimenti:

- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezione 9)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 6, dettaglio 3.6)

Checklist:

- [x] Estendere `_classify_install_files` per `file_policies` (extend/delegate)
- [x] Implementare parsing `file_policies` e helper `_update_package_section`
- [x] Implementare `_parse_section_markers` e `_create_file_with_section`
- [x] Aggiungere test `tests/test_multi_owner_policy.py`
- [x] Validare con pytest su test nuovi e suite sensibili (manifest/install/update planner)

Criteri di uscita:

- Policy `extend` applica solo la sezione marcata
- Policy `delegate` salta il file senza snapshot

Note di validazione:

- Testare marcatori con whitespace e varianti CRLF
- Verificare che `.agent.md` non sia ammesso per `extend`
- Comando eseguito: `.venv\Scripts\python.exe -m pytest -q tests/test_multi_owner_policy.py tests/test_package_installation_policies.py tests/test_manifest_integrity.py tests/test_merge_integration.py tests/test_update_planner.py`
