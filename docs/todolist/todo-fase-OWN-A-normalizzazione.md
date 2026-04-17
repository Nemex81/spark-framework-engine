# TODO Fase A — Normalizzazione dei Pacchetti

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-a--normalizzazione-dei-pacchetti)

Stato: Completata

---

## spark-base (79 file `.md` attuali in `.github/`)

- [x] Inventario completo file `.md` in `.github/` con front matter attuale
- [x] Aggiungere campi `scf_owner`, `scf_version`, `scf_file_role`, `scf_merge_strategy`, `scf_merge_priority`, `scf_protected` a tutti i file `.md` preservando `spark: true`
- [x] File `copilot-instructions.md`: impostare `scf_merge_strategy: merge_sections`, `scf_merge_priority: 10`
- [x] File agents: impostare `scf_file_role: agent`, `scf_merge_strategy: replace`
- [x] File instructions: impostare `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [x] File skills: impostare `scf_file_role: skill`, `scf_merge_strategy: replace`
- [x] File prompts: impostare `scf_file_role: prompt`, `scf_merge_strategy: replace`
- [x] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [x] Verificare coerenza front matter ↔ `files_metadata`

## scf-master-codecrafter (81 file `.md` attuali in `.github/`)

- [x] Inventario completo file `.md` in `.github/`
- [x] Aggiungere campi `scf_*` a tutti i file preservando `spark: true`
- [x] File `copilot-instructions.md`: convertire a sezione contribuita con `scf_merge_strategy: merge_sections`, `scf_merge_priority: 20`
- [x] File agents: impostare `scf_file_role: agent`, `scf_merge_strategy: replace`
- [x] File instructions: `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [x] File skills: `scf_file_role: skill`, `scf_merge_strategy: replace`
- [x] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [x] Verificare coerenza front matter ↔ `files_metadata`

## scf-pycode-crafter (11 file `.md` attuali in `.github/` + `copilot-instructions.md` da creare)

- [x] Inventario completo file `.md` in `.github/`
- [x] Aggiungere campi `scf_*` a tutti i file preservando `spark: true`
- [x] Creare `copilot-instructions.md` con sezione contribuita, `scf_merge_strategy: merge_sections`, `scf_merge_priority: 30`
- [x] File agents: `scf_file_role: agent`, `scf_merge_strategy: replace`
- [x] File instructions: `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [x] File skills: `scf_file_role: skill`, `scf_merge_strategy: replace`
- [x] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [x] Verificare coerenza front matter ↔ `files_metadata`

## Gate di uscita

- [x] Tutti i front matter validati con check automatico (grep `scf_owner` su tutti i `.md`)
- [x] Tutti i `package-manifest.json` a schema `2.1`
- [x] Nessun file `.md` senza `spark: true` tra quelli gestiti
- [x] Nessuna modifica all'engine in questa fase
- [x] `scf-registry` escluso esplicitamente dalla fase in coerenza con il piano strategico aggiornato
