---
type: prompt
name: scf-update-single
description: Aggiorna un singolo pacchetto SCF specificato dall'utente.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
agent: agent
spark: true
scf_owner: "spark-base"
---

# scf-update-single — Aggiornamento pacchetto singolo

Pacchetto da aggiornare: ${input:ID pacchetto SCF (es: spark-base)}

## Sequenza

1. Chiama `scf_get_package_info(package_id)` e mostra versione installata e versione disponibile.
2. Se il pacchetto è già aggiornato: rispondi `Pacchetto già all'ultima versione.` e termina.
3. Se `installation_mode: v2_workspace`: mostra i file con `modified_by: "user"` e chiedi
   il `conflict_mode` da usare: `abort` (interrompi), `replace` (sovrascrivi), `manual`
   (marker nel file), `auto` (merge 3-vie), `assisted` (merge interattivo).
4. Se `installation_mode: v3_store`: l'update aggiorna lo store centralizzato — nessun file
   scritto nel workspace. Gli override presenti vengono segnalati se divergono.
5. Chiama `scf_update_package(package_id)` con il conflict_mode scelto.
6. Se la response contiene file con `modified_by: "integrative_update"`: mostra i file
   aggiornati con merge riuscito.
7. Se ci sono conflitti non risolti: mostra i file bloccati e istruzioni per risolverli.
8. Mostra il riepilogo: pacchetto, versione precedente → nuova, file toccati, file preservati.
