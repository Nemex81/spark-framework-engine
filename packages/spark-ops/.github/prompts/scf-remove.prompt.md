---
description: Rimuove un pacchetto SCF con conferma esplicita prima di modificare file.
scf_protected: false
scf_file_role: "prompt"
name: scf-remove
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
type: prompt
spark: true
scf_owner: "spark-base"
---

Obiettivo: rimuovere un pacchetto installato senza toccare file user-modified.

Regola obbligatoria:
- Non eseguire rimozione finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_list_installed_packages()` per verificare presenza del pacchetto.
3. Mostra riepilogo pre-azione:
   - pacchetto da rimuovere e modalita installazione (`v2_workspace` o `v3_store`)
   - per `v2_workspace`: i file in `.github/` saranno rimossi;
     i file con `modified_by: "user"` saranno preservati per default.
   - per `v3_store`: lo store centralizzato sara rimosso e le MCP resources
     (agents/skills/prompts/instructions) saranno deregistrate;
     eventuali override locali nel workspace restano e vengono segnalati.
4. Chiedi conferma esplicita (es: "Confermi rimozione? [si/no]").
5. Solo se l'utente conferma, esegui `scf_remove_package(package_id)`.
6. Mostra esito con:
   - file rimossi
   - `workspace_files_preserved` (file user-modified preservati)
   - override residui segnalati, se presenti

Se l'utente non conferma, interrompi senza modificare nulla.
