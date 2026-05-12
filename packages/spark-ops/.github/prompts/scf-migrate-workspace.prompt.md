---
type: prompt
name: scf-migrate-workspace
description: Guida la migrazione di un workspace SCF legacy con conferma esplicita prima di modificare file protetti.
spark: true
scf_owner: "spark-base"
scf_version: "1.3.0"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 10
scf_protected: false
---

Obiettivo: migrare in sicurezza un workspace SCF pre-ownership verso il flusso con policy update e marker SCF.

Regole obbligatorie:
- Non modificare file finche l'utente non conferma in modo esplicito.
- Se il tool richiede autorizzazione `.github/`, fermati e chiedi il passaggio richiesto senza forzare scritture.

Istruzioni operative:
1. Esegui `scf_get_workspace_info()` per capire se il workspace e gia bootstrap-pato.
2. Esegui `scf_get_update_policy()` per verificare se esiste `spark-user-prefs.json`.
3. Per bootstrap sicuro, usa prima `scf_bootstrap_workspace(dry_run=True)` per
   visualizzare i file che verrebbero copiati senza eseguire scritture.
   Mostra chiaramente che `dry_run=True` non ha modificato nulla.
4. Se il dry-run mostra risultati attesi, esegui il bootstrap reale con
   `scf_bootstrap_workspace(update_mode="ask")`.
   - Se `files_protected` nella risposta non e vuoto, segnala all'utente
     e proponi re-run con `force=True` per sovrascrivere i file protetti.
5. Se l'utente vuole aggiornare un pacchetto legacy, usa `scf_update_package(package_id)`.
6. Mostra un riepilogo con: stato policy, `migration_state`, formato
   `copilot-instructions.md`, azioni richieste.
7. Se serve configurazione policy, chiedi modalita: `ask`, `integrative`, `conservative`.
8. Se `copilot-instructions.md` e in formato plain, spiega che SPARK non migra
   automaticamente e chiedi conferma chiusa.
9. Solo se l'utente conferma, ripeti il tool pertinente con `migrate_copilot_instructions=True`.
10. Mostra esito finale: file preservati/migrati, `diff_summary`, `backup_path`.

Se l'utente non conferma, interrompi senza modificare nulla.