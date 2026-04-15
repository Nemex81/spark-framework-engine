# Fase SB-6 — Gate di verifica post-migrazione

Stato attuale: Non avviata

Riferimenti:

- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 6)

Dipendenze:

- SB-5 completata (migrazione workspace eseguita)

Checklist:

- [ ] V1: `scf_list_installed_packages` restituisce 3 pacchetti:
  - [ ] `spark-base@1.0.0`
  - [ ] `scf-master-codecrafter@2.0.0`
  - [ ] `scf-pycode-crafter@2.0.0`
- [ ] V2: `scf_verify_workspace` → `is_clean: true`, `modified: []`
- [ ] V3: Agenti — contare gli agenti con `scf_list_agents`:
  - [ ] 11 agenti BASE da spark-base (Analyze, Plan, Docs, Helper, Research, Welcome, FrameworkDocs, Git, Orchestrator, Release, Validate)
  - [ ] 3 agenti CORE-CRAFT da master (Design, CodeRouter, CodeUI)
  - [ ] 5 agenti python da pycode (py-Agent-Analyze, py-Agent-Code, py-Agent-Design, py-Agent-Plan, py-Agent-Validate)
  - [ ] Totale atteso: 19 agenti
- [ ] V4: Skill — verificare skill chiave:
  - [ ] `semver-bump` presente (da spark-base) ✅
  - [ ] `changelog-entry` presente (da spark-base) ✅
  - [ ] `clean-architecture` presente (da master-codecrafter) ✅
  - [ ] `code-routing` presente (da master-codecrafter) ✅
- [ ] V5: Instruction — `scf_list_instructions`:
  - [ ] `framework-guard`, `model-policy`, `personality`, `verbosity`, `workflow-standard`, `git-policy` da spark-base
  - [ ] `mcp-context` da master-codecrafter
  - [ ] `python`, `tests` da pycode-crafter
- [ ] V6: Prompt presenti: `scf_list_prompts` → 18 prompt da spark-base
- [ ] V7: `scf_get_agent("Agent-Design")` → non restituisce errore (da master-codecrafter)
- [ ] V8: `scf_get_agent("Agent-Git")` → non restituisce errore (da spark-base)
- [ ] V9: `scf_get_skill("clean-architecture")` → non restituisce errore (da master-codecrafter)
- [ ] V10: `scf_get_skill("semver-bump")` → non restituisce errore (da spark-base)
- [ ] V11: `AGENTS-master.md` fisicamente presente in `.github/`
- [ ] V12: `scf_get_runtime_state` → funziona senza errori

Criteri di uscita:

- TUTTI i gate V1–V12 passati

Note operative:

- Se V2 fallisce (modified non vuoto): verificare se è un falso positivo da SHA encoding.
  In caso contrario: capire quale file è stato modificato durante la migrazione.
- Se V3 mostra meno di 19 agenti: verificare se `AGENTS-*.md` è stato aggiunto correttamente.
  Il conteggio dipende da `list_agents()` che scopre i file `.md` in `.github/agents/`.
- Se `scf_verify_system` riporta `engine_min_mismatch`: verificare che
  `engine_min_version` nel registry coincida con `min_engine_version` nel manifest del pacchetto.
- `scf_verify_system` resta un controllo addizionale raccomandato, ma non fa parte dei 12 gate
  V1–V12 del piano esecutivo.
