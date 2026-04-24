---
type: prompt
name: scf-install
description: Installa un pacchetto SCF con conferma esplicita prima di modificare file.
---

Obiettivo: installare un pacchetto SCF in modo sicuro e trasparente.

Regola obbligatoria:
- Non eseguire installazione finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_get_package_info(package_id)` per costruire il riepilogo.
3. Esegui `scf_plan_install(package_id)`.
4. Mostra anteprima con:
   - package id e versione
   - numero file da installare
   - categorie coinvolte
   - file in `write_plan`
   - file in `preserve_plan`
   - eventuali conflitti in `conflict_plan`
5. Se `conflict_plan` contiene file `conflict_untracked_existing`, chiedi se l'utente vuole procedere con overwrite esplicito `replace` oppure interrompere.
6. Se `conflict_plan` contiene ownership cross-package, interrompi e spiega che il tool blocca l'operazione.
7. Chiedi conferma esplicita finale con domanda chiusa (es: "Confermi installazione? [si/no]").
8. Solo se l'utente conferma:
   - senza conflitti risolti: esegui `scf_install_package(package_id)`
   - con overwrite esplicito approvato: esegui `scf_install_package(package_id, conflict_mode="replace")`
9. Mostra esito con:
   - file installati
   - file preservati per modifica utente
   - file sostituiti esplicitamente, se presenti
   - eventuali errori

Se l'utente non conferma, interrompi senza modificare nulla.
