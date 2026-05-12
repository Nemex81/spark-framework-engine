---
description: Installa un pacchetto SCF con conferma esplicita prima di modificare file.
scf_protected: false
scf_file_role: "prompt"
name: scf-install
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
type: prompt
spark: true
scf_owner: "spark-base"
---

Obiettivo: installare un pacchetto SCF in modo sicuro e trasparente.

Regola obbligatoria:
- Non eseguire installazione finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_get_package_info(package_id)` per costruire il riepilogo.
3. Esegui `scf_plan_install(package_id)`.
4. Controlla `installation_mode` nella risposta:
   - `v2_workspace`: i file saranno copiati in `.github/` del workspace.
   - `v3_store`: nessun file sara copiato; le risorse sono disponibili via MCP
     (`agents://`, `skills://`, `prompts://`, `instructions://`). Per
     materializzare un componente come override locale usa `scf_override_resource`.
5. Mostra anteprima con: package id e versione, numero file, categorie,
   file in `write_plan`, `preserve_plan`, eventuali conflitti in `conflict_plan`.
6. Se `conflict_plan` contiene `conflict_untracked_existing`, chiedi il
   `conflict_mode` desiderato:
   - `abort` (default): interrompe se c'e conflitto.
   - `replace`: sovrascrive il file esistente.
   - `manual`: risoluzione manuale file per file.
   - `auto`: il motore sceglie la strategia migliore.
   - `assisted`: il motore propone e chiede conferma.
7. Se `conflict_plan` contiene ownership cross-package, interrompi e spiega
   che il tool blocca l'operazione.
8. Chiedi conferma esplicita finale (es: "Confermi installazione? [si/no]").
9. Solo se l'utente conferma, esegui `scf_install_package(package_id)` con
   il `conflict_mode` concordato.
10. Mostra esito con: file installati, file preservati, file sostituiti,
    eventuali errori.

Se l'utente non conferma, interrompi senza modificare nulla.
