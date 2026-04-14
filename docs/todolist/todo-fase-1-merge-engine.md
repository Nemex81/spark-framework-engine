# Fase 1 — MergeEngine core

Stato iniziale: Completata

Riferimenti:
- Design: [SCF-3WAY-MERGE-DESIGN.md](../SCF-3WAY-MERGE-DESIGN.md) (sezione 4)
- Piano: [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](../SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md) (Fase 1, dettaglio 3.1)

Checklist:
- [x] Implementare `MergeConflict`, `MergeResult` dataclass
- [x] Implementare `MergeEngine.diff3_merge`, `render_with_markers`, `has_conflict_markers`
- [x] Gestire esplicitamente il caso `OURS == THEIRS != BASE` come merge clean (deduplicato)
- [x] Aggiungere test `tests/test_merge_engine.py` coprendo tutti i casi elencati
- [x] Assicurare che `MergeEngine` non importi moduli MCP

Criteri di uscita:
- Copertura di test ≥ 90% per MergeEngine
- Tutti i test `tests/test_merge_engine.py` passano
- Nessuna dipendenza esterna introdotta

Note di validazione:
- Verificare normalizzazione newline `\r\n` → `\n` prima del merge
- Testare frontmatter e casi di deduplicazione esplicita
