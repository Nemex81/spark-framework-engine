---
description: Dispatcher per aggiornamenti pacchetti SCF — instrada verso single o batch.
scf_protected: false
scf_file_role: "prompt"
name: scf-update
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.1"
type: prompt
spark: true
scf_owner: "spark-base"
---

Dispatcher per aggiornamenti pacchetti SCF.

**Regola:** non applicare aggiornamenti senza conferma esplicita dall'utente.

**Routing:**

Se l'utente ha fornito un `package_id` specifico:
→ Usa `#scf-update-single` — aggiornamento singolo con gestione conflict_mode.

Se non è specificato alcun `package_id` (aggiorna tutto):
→ Usa `#scf-update-batch` — piano batch con conferma tabellare.

Se l'intent non è chiaro, chiedi:
> "Vuoi aggiornare un pacchetto specifico (es: `spark-base`) o tutti i pacchetti installati?"
