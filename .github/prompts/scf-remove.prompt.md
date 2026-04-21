---
type: prompt
name: scf-remove
description: Rimuove un pacchetto SCF con conferma esplicita prima di modificare file.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

Obiettivo: rimuovere un pacchetto installato senza toccare file user-modified.

Regola obbligatoria:
- Non eseguire rimozione finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_list_installed_packages()` per verificare presenza del pacchetto.
3. Mostra riepilogo pre-azione:
   - pacchetto da rimuovere
   - nota che i file modificati dall'utente saranno preservati
4. Chiedi conferma esplicita (es: "Confermi rimozione? [si/no]").
5. Solo se l'utente conferma, esegui `scf_remove_package(package_id)`.
6. Mostra esito con elenco `preserved_user_modified`.

Se l'utente non conferma, interrompi senza modificare nulla.
