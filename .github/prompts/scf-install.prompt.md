---
type: prompt
name: scf-install
description: Installa un pacchetto SCF con conferma esplicita prima di modificare file.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

Obiettivo: installare un pacchetto SCF in modo sicuro e trasparente.

Regola obbligatoria:
- Non eseguire installazione finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_get_package_info(package_id)` per costruire il riepilogo.
3. Esegui `scf_plan_install(package_id)`.
4. Esegui `scf_get_update_policy()` se l'utente vuole capire come il workspace gestira `update_mode` o se sospetti che serva una policy esplicita.
5. Mostra anteprima con:
   - package id e versione
   - numero file da installare
   - categorie coinvolte
   - file in `write_plan`
   - file in `preserve_plan`
   - eventuali conflitti in `conflict_plan`
   - policy update attiva, se rilevante
   - eventuale `update_mode` che intendi usare
6. Se `conflict_plan` contiene file `conflict_untracked_existing`, chiedi se l'utente vuole procedere con overwrite esplicito `replace` oppure interrompere.
7. Se `conflict_plan` contiene ownership cross-package, interrompi e spiega che il tool blocca l'operazione.
8. Se il workspace richiede una policy esplicita o l'utente vuole cambiare comportamento di default, proponi `scf_set_update_policy(...)` oppure un `update_mode` esplicito per questa singola installazione.
9. Chiedi conferma esplicita finale con domanda chiusa (es: "Confermi installazione? [si/no]").
10. Solo se l'utente conferma:
   - senza mode esplicito: esegui `scf_install_package(package_id)`
   - con overwrite esplicito approvato: esegui `scf_install_package(package_id, conflict_mode="replace")`
   - con strategia package-level scelta: esegui `scf_install_package(package_id, conflict_mode="...", update_mode="...")`
11. Se il tool restituisce `action_required`, fermati e mostra il passo richiesto (`configure_update_policy`, `authorize_github_write`, `choose_update_mode`) senza forzare scritture.
12. Mostra esito con:
   - file installati
   - file preservati per modifica utente
   - file sostituiti esplicitamente, se presenti
   - `diff_summary`, `backup_path` e `resolved_update_mode` se presenti
   - eventuali errori

Se l'utente non conferma, interrompi senza modificare nulla.
