# Todo Coordinator — SCF 3-Way Merge Implementation

Funzione: coordinare lo stato delle fasi implementative e linkare i file todo specifici.

Fasi e stato (coordinatore):

- **Fase 0**: Infrastruttura snapshot BASE — Stato: Completata — [todo-fase-0-snapshot-base.md](todolist/todo-fase-0-snapshot-base.md)
- **Fase 1**: MergeEngine core — Stato: Completata — [todo-fase-1-merge-engine.md](todolist/todo-fase-1-merge-engine.md)
- **Fase 2**: Integrazione install/update — Stato: Completata — [todo-fase-2-integrazione-update.md](todolist/todo-fase-2-integrazione-update.md)
- **Fase 3**: Sessioni di merge stateful — Stato: Completata — [todo-fase-3-sessioni-merge.md](todolist/todo-fase-3-sessioni-merge.md)
- **Fase 4**: Modalità auto (AI) — Stato: Completata — [todo-fase-4-modalita-auto.md](todolist/todo-fase-4-modalita-auto.md)
- **Fase 5**: Modalità assisted — Stato: Completata — [todo-fase-5-modalita-assisted.md](todolist/todo-fase-5-modalita-assisted.md)
- **Fase 6**: Policy multi-owner — Stato: Completata — [todo-fase-6-policy-multi-owner.md](todolist/todo-fase-6-policy-multi-owner.md)
- **Fase 7**: Release e documentazione — Stato: Completata — [todo-fase-7-release-docs.md](todolist/todo-fase-7-release-docs.md)

Regole di avanzamento:

- Ogni fase deve avere tutti i test locali associati passati (`pytest -q <testfile>`).
- Prima di marcare una fase come completata: aggiorna il rispettivo `todo-fase-*.md` con tutti i checkbox spuntati e committa la modifica proposta.
- La revisione finale richiede l'esecuzione della suite completa `pytest -q` e l'audit `scf-coherence-audit` (se disponibile).

Ordine di esecuzione raccomandato (dipendenze):

1. F0 e F1 paralleli
2. F2
3. F3
4. F4
5. F5
6. F6
7. F7 (release)

Nota: le regole e le dipendenze sono descritte in dettaglio in [SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md](SCF-3WAY-MERGE-IMPLEMENTATION-PLAN.md).
