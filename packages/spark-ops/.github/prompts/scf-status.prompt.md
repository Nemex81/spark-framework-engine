---
description: Mostra una panoramica completa dello stato SCF del workspace attivo.
scf_protected: false
scf_file_role: "prompt"
name: scf-status
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
type: prompt
spark: true
scf_owner: "spark-base"
---

Obiettivo: mostrare lo stato SCF corrente in una vista unica.

Istruzioni operative:
1. Esegui `scf_get_workspace_info()`.
2. Esegui `scf_list_installed_packages()`.
3. Esegui `scf_update_packages()`.
4. Opzionale: se l'utente richiede verifica coerenza, esegui `scf_verify_system()`
   e riporta `issues` e `warnings`.
5. Non modificare file o stato del workspace.

Formato risposta:
- Sezione `Workspace`: root attiva, initialized, engine_version.
- Sezione `Pacchetti installati`: per ogni pacchetto:
  - `package`, `version`, `file_count`
  - `installation_mode`: `v2_workspace` o `v3_store`
  - per `v2_workspace`: conteggio file per `modified_by`
    (`original`, `user`, `integrative_update`)
  - per `v3_store`: risorse MCP esposte (agenti/skill/prompt/instruction)
- Sezione `Asset SCF`: conteggi agent/skill/instruction/prompt.
- Sezione `Aggiornamenti`: up_to_date, update_available, not_in_registry, blocchi.
- Sezione `Override orfani`: override nel workspace per pacchetti non piu
  installati; segnala path e suggerisci rimozione manuale.
- Se non ci sono pacchetti installati, dillo esplicitamente.
