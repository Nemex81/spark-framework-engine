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

---

## Progetto spark-base — Riorganizzazione componenti

Coordinator per la migrazione da `scf-master-codecrafter` a `spark-base + master-codecrafter v2.0.0`.

Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](PIANO-IMPLEMENTATIVO-SPARK-BASE.md)
Analisi: [ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md](ANALISI-RIORGANIZZAZIONE-SPARK-BASE.md)

Fasi e stato (coordinator):

- **SB-0**: Preflight workspace — Stato: Non avviata — [todo-fase-SB-0-preflight.md](todolist/todo-fase-SB-0-preflight.md)
- **SB-1**: Creazione repository spark-base — Stato: In corso (scaffold locale pronto, publish remoto bloccato da auth GitHub) — [todo-fase-SB-1-repo.md](todolist/todo-fase-SB-1-repo.md)
- **SB-2**: Riduzione scf-master-codecrafter → v2.0.0 — Stato: In corso (modifiche locali validate, commit/push non eseguiti) — [todo-fase-SB-2-master-v2.md](todolist/todo-fase-SB-2-master-v2.md)
- **SB-3**: Dry-run manifest spark-base — Stato: Non avviata — [todo-fase-SB-3-dry-run.md](todolist/todo-fase-SB-3-dry-run.md)
- **SB-4**: Aggiornamento registry — Stato: In corso (entry locale aggiornata e validata, commit/push non eseguiti) — [todo-fase-SB-4-registry.md](todolist/todo-fase-SB-4-registry.md)
- **SB-5**: Migrazione workspace utente — Stato: Non avviata — [todo-fase-SB-5-migrazione.md](todolist/todo-fase-SB-5-migrazione.md)
- **SB-6**: Gate di verifica post-migrazione — Stato: Non avviata — [todo-fase-SB-6-gate.md](todolist/todo-fase-SB-6-gate.md)
- **SB-7**: Migrazione `spark-init.py` a bootstrap embedded `spark-base` — Stato: Completata (script, test e README allineati localmente) — [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](PIANO-IMPLEMENTATIVO-SPARK-BASE.md)
- **SB-2b**: Correzione asset split (`Agent-Code` + `spark-guide`) — Stato: In corso (fix coordinato engine/base/master avviato) — [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](PIANO-IMPLEMENTATIVO-SPARK-BASE.md)

Ordine di esecuzione:

1. SB-0 (obbligatorio, gate pre-tutto)
2. SB-1 e SB-2 in parallelo (repo diversi)
3. SB-4 (dipende da SB-1 + SB-2) — registry deve essere aggiornato per primo
4. SB-3 (dipende da SB-4) — dry-run richiede entry registry spark-base presente e repo remoto pubblicato
5. SB-5 (dipende da SB-3 + SB-4)
6. SB-6 (dipende da SB-5)

---

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

---

## Progetto SCF File Ownership & Workspace Merge System

Coordinator per l'implementazione del sistema di ownership file, merge a sezioni e preferenze utente.

Piano: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md)
Validazione: Superata v1.1.0 — 13 correzioni applicate al documento originale

Fasi e stato (coordinator):

- **OWN-A**: Normalizzazione pacchetti (front matter + manifest schema 2.1) — Stato: Completata — [todo-fase-OWN-A-normalizzazione.md](todolist/todo-fase-OWN-A-normalizzazione.md)
- **OWN-B**: Tool policy + utility diff/backup — Stato: Completata — [todo-fase-OWN-B-policy-diff-backup.md](todolist/todo-fase-OWN-B-policy-diff-backup.md)
- **OWN-C**: Utility section merge (SCF markers) — Stato: Completata — [todo-fase-OWN-C-section-merge.md](todolist/todo-fase-OWN-C-section-merge.md)
- **OWN-D**: Integrazione flusso install/update — Stato: Non avviata — [todo-fase-OWN-D-integrazione-flusso.md](todolist/todo-fase-OWN-D-integrazione-flusso.md)
- **OWN-E**: Estensione bootstrap workspace — Stato: Non avviata — [todo-fase-OWN-E-bootstrap-estensione.md](todolist/todo-fase-OWN-E-bootstrap-estensione.md)
- **OWN-F**: Documentazione e release — Stato: Non avviata — [todo-fase-OWN-F-docs-release.md](todolist/todo-fase-OWN-F-docs-release.md)
- **OWN-G**: Migrazione workspace esistenti — Stato: Non avviata — [todo-fase-OWN-G-migrazione-workspace.md](todolist/todo-fase-OWN-G-migrazione-workspace.md)

Ordine di esecuzione (strettamente sequenziale):

1. OWN-A (prerequisito per tutto — nessuna modifica engine)
2. OWN-B (utility interne + 2 nuovi tool)
3. OWN-C (section merge, dipende da OWN-B)
4. OWN-D (integrazione nei tool pubblici, dipende da OWN-B + OWN-C)
5. OWN-E (estensione bootstrap, dipende da OWN-D)
6. OWN-F (docs e release, dipende da OWN-E)
7. OWN-G (migrazione, dipende da OWN-F — può procedere in parallelo parziale)

Regole di avanzamento:

- Ogni fase richiede gate di uscita verificato (test + audit).
- Non avviare la fase N+1 se la fase N non ha il gate superato.
- Prima di marcare completata: aggiornare il rispettivo `todo-fase-OWN-*.md` con tutti i checkbox.
- OWN-A non richiede test engine ma richiede validazione coerenza front matter ↔ manifest.
