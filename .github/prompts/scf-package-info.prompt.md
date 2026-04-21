---
type: prompt
name: scf-package-info
description: Mostra dettagli completi di un pacchetto SCF, inclusi contenuti e file installabili.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

Obiettivo: aiutare l'utente a decidere se installare un pacchetto.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_get_package_info(package_id)`.
3. Non modificare file o stato del workspace.

Mostra sempre:
- metadati package: id, description, repo_url, latest_version, status, tags
- metadati manifest: version, file_count, categorie
- elenco file installabili

Se il pacchetto e deprecato, evidenzialo chiaramente.
