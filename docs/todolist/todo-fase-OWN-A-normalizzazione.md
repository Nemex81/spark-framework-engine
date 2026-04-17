# TODO Fase A — Normalizzazione dei Pacchetti

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-a--normalizzazione-dei-pacchetti)

Stato: Non avviata

---

## spark-base (76 file)

- [ ] Inventario completo file `.md` in `.github/` con front matter attuale
- [ ] Aggiungere campi `scf_owner`, `scf_version`, `scf_file_role`, `scf_merge_strategy`, `scf_merge_priority`, `scf_protected` a tutti i file `.md` preservando `spark: true`
- [ ] File `copilot-instructions.md`: impostare `scf_merge_strategy: merge_sections`, `scf_merge_priority: 10`
- [ ] File agents: impostare `scf_file_role: agent`, `scf_merge_strategy: replace`
- [ ] File instructions: impostare `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [ ] File skills: impostare `scf_file_role: skill`, `scf_merge_strategy: replace`
- [ ] File prompts: impostare `scf_file_role: prompt`, `scf_merge_strategy: replace`
- [ ] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [ ] Verificare coerenza front matter ↔ `files_metadata`

## scf-master-codecrafter (13 file)

- [ ] Inventario completo file `.md` in `.github/`
- [ ] Aggiungere campi `scf_*` a tutti i file preservando `spark: true`
- [ ] File `copilot-instructions.md`: convertire a sezione contribuita con `scf_merge_strategy: merge_sections`, `scf_merge_priority: 20`
- [ ] File agents (4): `scf_file_role: agent`, `scf_merge_strategy: replace`
- [ ] File instructions: `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [ ] File skills: `scf_file_role: skill`, `scf_merge_strategy: replace`
- [ ] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [ ] Verificare coerenza front matter ↔ `files_metadata`

## scf-pycode-crafter (12 file)

- [ ] Inventario completo file `.md` in `.github/`
- [ ] Aggiungere campi `scf_*` a tutti i file preservando `spark: true`
- [ ] Creare `copilot-instructions.md` con sezione contribuita, `scf_merge_strategy: merge_sections`, `scf_merge_priority: 30`
- [ ] File agents (5): `scf_file_role: agent`, `scf_merge_strategy: replace`
- [ ] File instructions (2): `scf_file_role: instruction`, `scf_merge_strategy: replace`
- [ ] File skills: `scf_file_role: skill`, `scf_merge_strategy: replace`
- [ ] Aggiornare `package-manifest.json` a schema `2.1` con `files_metadata`
- [ ] Verificare coerenza front matter ↔ `files_metadata`

## Gate di uscita

- [ ] Tutti i front matter validati con check automatico (grep `scf_owner` su tutti i `.md`)
- [ ] Tutti i `package-manifest.json` a schema `2.1`
- [ ] Nessun file `.md` senza `spark: true` tra quelli gestiti
- [ ] Nessuna modifica all'engine in questa fase
