# Fase 7 — Release, versioning e documentazione finale

Stato iniziale: Non iniziata
Stato attuale: **Completata** — 2026-04-14

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezioni 11, 15)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 7, dettaglio 3.7)

Checklist:
- [x] Bump `ENGINE_VERSION` a `2.0.0` in `spark-framework-engine.py`
- [x] Aggiornare `CHANGELOG.md` con `## [2.0.0] - 2026-04-14` come prima voce
- [x] Aggiornare commento classe e log con `# Tools (33)` e `Tools registered: 33 total`
- [x] Aggiornare `README.md` con sezione sul merge e i nuovi `conflict_mode`
- [x] Aggiornare `docs/ROADMAP-FASE2.md` come completata
- [x] Eseguire `pytest -q` per verifica finale

Criteri di uscita:
- `test_engine_coherence.py` passa (prima voce CHANGELOG == ENGINE_VERSION)
- Suite completa `pytest -q` passata senza regressioni

Note di validazione:
- Verificare che non sia esposto alcun tool aggiuntivo (scf_cleanup_sessions resta helper interno)
- Controllare che il numero totale di tool sia coerente con i test e commenti sorgente
