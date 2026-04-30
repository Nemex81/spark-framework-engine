# TODO — Gateway Bootstrap
Riferimento piano: docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md — Sezione 3
Priorità: P0
Dipende da: nessuno

## Task specifici
1. Refactor funzione scf_bootstrap_workspace in spark-framework-engine.py (riga ~7379):
	- Aggiorna la logica per copiare solo i file gateway definiti (2 agent, 1 instructions se presente, scf-*.prompt.md)
	- Criterio: Solo questi file sono copiati, nessun altro
	- Pass/Fail: Verifica file in .github/ dopo bootstrap
2. Implementa controllo sha256 tra file sorgente e destinazione:
	- Se il file esiste ed è modificato, non sovrascrivere
	- Criterio: File modificati dall’utente non vengono toccati
	- Pass/Fail: Modifica manuale file, esegui bootstrap, verifica che non sia sovrascritto
3. Logging warning su sys.stderr se file gateway modificato:
	- Criterio: Warning presente in log
	- Pass/Fail: Forza caso, verifica log
4. Aggiorna docstring e commenti funzione:
	- Criterio: Docstring Google-style aggiornata
	- Pass/Fail: Review manuale
5. Verifica idempotenza tramite sentinella agents/spark-assistant.agent.md:
	- Criterio: Bootstrap ripetuto non ricopia file già presenti e non modificati
	- Pass/Fail: Esegui due volte, verifica nessun cambiamento
