---
description: Applica aggiornamenti pacchetti SCF con conferma esplicita e preservazione file utente.
scf_protected: false
scf_file_role: "prompt"
name: scf-update
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
type: prompt
spark: true
scf_owner: "spark-base"
---

Obiettivo: aggiornare pacchetti installati mantenendo sempre i file user-modified.

Regola obbligatoria:
- Non applicare aggiornamenti finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Determina se l'utente ha specificato un `package_id` o vuole aggiornare tutto.

Flusso singolo (package_id specificato):
2a. Esegui `scf_update_package(package_id)`.
2b. Per pacchetti `v3_store`, l'update aggiorna lo store centralizzato senza
    toccare il workspace; eventuali override locali vengono segnalati.
2c. Se la risposta contiene file con `modified_by: "user"`, spiega che quel
    file e stato modificato dall'utente. Proponi il `conflict_mode` appropriato
    (`manual`, `auto`, `assisted`) e chiedi conferma.
2d. Se l'update riesce con merge, mostra file con `modified_by: "integrative_update"`.

Flusso batch (nessun package_id):
3a. Esegui `scf_update_packages()` per il piano update.
3b. Se non ci sono update, informa l'utente e termina.
3c. Mostra piano: pacchetti, versioni, dipendenze, nota preservazione file utente.
3d. Se ci sono blocchi, mostrali e non proporre applicazione.
3e. Chiedi conferma esplicita (es: "Confermi aggiornamenti? [si/no]").
3f. Solo se confermato, esegui `scf_apply_updates()`.

Esito finale (entrambi i flussi):
4. Mostra: pacchetti aggiornati, falliti, ordine applicato, file toccati/preservati.
5. Se `batch_conflicts` e presente, spiega il blocco preflight e i package coinvolti.

Se l'utente non conferma, interrompi senza modificare nulla.
