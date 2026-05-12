---
description: Mostra dettagli completi di un pacchetto SCF, inclusi contenuti e file installabili.
scf_protected: false
scf_file_role: "prompt"
name: scf-package-info
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.1"
type: prompt
spark: true
scf_owner: "spark-base"
---

Obiettivo: aiutare l'utente a decidere se installare un pacchetto.

Istruzioni operative:
1. Se manca il nome pacchetto, chiedi `package_id`.
2. Esegui `scf_get_package_info(package_id)`.
3. Non modificare file o stato del workspace.

Mostra sempre:
- metadati package: id, description, repo_url, latest_version, status, tags
- metadati manifest: version, file_count, categorie
- `installation_mode`: indica se il pacchetto sara installato come `v2_workspace`
  (file copiati in `.github/`) o `v3_store` (risorse via MCP, nessun file locale)
- elenco file installabili

Se il pacchetto e deprecato, evidenzialo chiaramente.
