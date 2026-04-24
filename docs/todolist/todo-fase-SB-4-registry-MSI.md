# Fase SB-4 — Aggiornamento registry

Stato attuale: In corso

Riferimenti:
- Piano: [PIANO-IMPLEMENTATIVO-SPARK-BASE.md](../PIANO-IMPLEMENTATIVO-SPARK-BASE.md) (Step 4)
- Registry: [scf-registry/registry.json](../../../../scf-registry/registry.json)

Dipendenze:
- SB-1 completata (repo `Nemex81/spark-base` pubblico)
- SB-2 completata (master v2.0.0 pushato)

Checklist:
- [x] Aprire `scf-registry/registry.json`
- [x] Aggiungere entry `spark-base`:
  ```json
  {
    "id": "spark-base",
    "display_name": "SPARK Base Layer",
    "description": "Layer fondazionale SCF — agenti, skill, instruction e prompt general-purpose per qualsiasi tipo di progetto",
    "repo_url": "https://github.com/Nemex81/spark-base",
    "latest_version": "1.0.0",
    "min_engine_version": "1.9.0",
    "engine_min_version": "1.9.0",
    "status": "stable",
    "tags": ["base", "foundation", "agents", "skills", "prompts", "general-purpose"]
  }
  ```
- [x] Aggiornare entry `scf-master-codecrafter`:
  - [x] `latest_version: "2.0.0"`
  - [x] Aggiornare `description` per riflettere il nuovo perimetro CORE-CRAFT
  - [x] Aggiungere `"spark-base"` nei `tags` o note
- [ ] Committare e pushare `registry.json`
- [ ] Verificare che `scf_list_available_packages` restituisca 3 pacchetti

Criteri di uscita:
- `registry.json` contiene 3 pacchetti: `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`
- `scf_list_available_packages` restituisce tutti e 3
- `scf_get_package_info("spark-base")` restituisce i dati corretti del manifest

Note operative:
- Verificare che il campo `engine_min_version` nel registry corrisponda a `min_engine_version`
  nel `package-manifest.json`: in caso di mismatch, `scf_verify_system` segnalerebbe
  `engine_min_mismatch` come issue.
- Il registry usa `schema_version: "2.0"` — non modificare questo campo.
- Validazione locale completata: `registry.json` e parsabile e ora contiene 3 pacchetti
  (`spark-base@1.0.0`, `scf-master-codecrafter@2.0.0`, `scf-pycode-crafter@2.0.0`).
