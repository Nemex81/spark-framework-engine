---
type: prompt
name: scf-migrate-workspace
description: Guida la migrazione di un workspace SCF legacy con conferma esplicita prima di modificare file protetti.
spark: true
scf_owner: "spark-base"
scf_version: "1.2.0"
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
3. Se serve avviare bootstrap o migrazione legacy, usa `scf_bootstrap_workspace(update_mode="ask")` come preflight guidato.
4. Se l'utente vuole aggiornare un pacchetto legacy, usa `scf_update_package(package_id)` per ottenere il prossimo `action_required`.
5. Mostra un riepilogo con:
   - stato policy (`file`, `default_missing`, `default_corrupt`)
   - eventuale `migration_state`
   - formato corrente di `copilot-instructions.md`
   - azioni richieste (`configure_update_policy`, `authorize_github_write`, `migrate_copilot_instructions`)
6. Se il workspace richiede configurazione policy, chiedi quale modalita usare: `ask`, `integrative`, `conservative`.
7. Se `copilot-instructions.md` e in formato plain o marker incompleto, spiega che SPARK non migra automaticamente e chiedi conferma chiusa.
8. Solo se l'utente conferma la migrazione esplicita del file, ripeti il tool pertinente passando `migrate_copilot_instructions=true`.
9. Mostra l'esito finale con:
   - file preservati
   - file migrati o installati
   - `diff_summary`
   - eventuale `backup_path`
   - garanzia che il testo utente fuori dai marker SCF resta intatto

Se l'utente non conferma, interrompi senza modificare nulla.