# Fase 9 — Ciclo install/update/remove v3-aware
# Dipende da: Fasi 0-8
# Effort stimato: M
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - tests/test_package_lifecycle_v3.py (nuovo)
#   - docs/MIGRATION-GUIDE-v3.md (aggiornamento sezione "lifecycle")

## Contesto

Engine v3.0.0 ha PackageResourceStore + McpResourceRegistry +
overrides workspace, ma scf_install_package, scf_update_package e
scf_remove_package operano ancora con copia file in workspace/.github/
(logica v2.x). Questa fase rende il ciclo di vita pacchetti
v3-aware con retrocompat per pacchetti legacy
(min_engine_version < 3.0.0).

## Architettura target

INSTALL (pacchetti v3, min_engine_version >= 3.0.0):
- File pacchetto vanno in engine_dir/packages/{pkg_id}/.github/{type}/
- package-manifest.json salvato in engine_dir/packages/{pkg_id}/
- Nessuna scrittura sotto workspace/.github/agents|prompts|skills|instructions
- Workspace .scf-manifest.json registra entry sentinella unica:
    {file: "__store__/{pkg_id}", package, package_version,
     installation_mode: "v3_store", store_path, files: [...]}
- Override workspace pre-esistenti: PRESERVATI sempre
- McpResourceRegistry aggiornato live con le risorse del pacchetto
- _apply_phase6_assets chiamato per rigenerare AGENTS.md

UPDATE (pacchetti v3):
- Scarica nuova versione e riscrive engine_dir/packages/{pkg_id}/
- Per ogni risorsa con override esistente: notifica utente e NON
  sovrascrive l'override. Suggerisce scf_drop_override.
- Manifest entry aggiornata con nuova version + sha256
- _apply_phase6_assets richiamato

REMOVE (pacchetti v3):
- Cancella engine_dir/packages/{pkg_id}/
- Deregistra URIs dal McpResourceRegistry
- Rimuove entry dal manifest workspace
- NON tocca workspace/.github/overrides/
- Warning se esistono override "orfani" per il pacchetto rimosso
- _apply_phase6_assets richiamato (AGENTS.md senza il pacchetto)

RETROCOMPAT:
- Se pkg_manifest min_engine_version < 3.0.0 -> ramo v2 invariato
  con warning su stderr "[SPARK-ENGINE][WARNING] legacy v2 install"

## Sub-fasi

### Sub-fase 9.1 — Install v3-aware

- [ ] 9.1.1 Aggiungere `_is_v3_package(pkg_manifest)` accanto a
      `_is_engine_version_compatible`.
- [ ] 9.1.2 Aggiungere `McpResourceRegistry.unregister(uri)`.
- [ ] 9.1.3 Aggiungere `_install_package_v3_into_store(...)` che
      scarica file in `engine_dir/packages/{pkg_id}/.github/...` via
      RegistryClient.fetch_raw_file.
- [ ] 9.1.4 Aggiungere `_register_v3_package_in_workspace_manifest(...)`
      con entry sentinella `installation_mode: "v3_store"`.
- [ ] 9.1.5 ManifestManager.verify_integrity: skip entry con
      `installation_mode == "v3_store"`.
- [ ] 9.1.6 ManifestManager.remove_package: gestire correttamente le
      entry `v3_store` senza tentare unlink di path workspace.
- [ ] 9.1.7 Branch v3 in scf_install_package.
- [ ] 9.1.8 Idempotenza: re-install stessa versione = no-op success.

### Sub-fase 9.2 — Remove v3-aware

- [ ] 9.2.1 Aggiungere `_remove_package_v3(...)` orchestratore.
- [ ] 9.2.2 Aggiungere `_warn_orphan_overrides_for_package(...)` che
      lista URI override appartenenti al pacchetto rimosso.
- [ ] 9.2.3 Branch v3 in scf_remove_package.
- [ ] 9.2.4 Re-popolazione `inventory.populate_mcp_registry(...)`
      dopo rimozione store + chiamata `_apply_phase6_assets`.

### Sub-fase 9.3 — Update v3-aware

- [ ] 9.3.1 Aggiungere `_update_package_v3(...)` che riusa
      `_install_package_v3_into_store` con override-aware skip.
- [ ] 9.3.2 Branch v3 in scf_update_package.
- [ ] 9.3.3 Diagnostica: lista risorse dove l'override blocca
      l'aggiornamento (campo `override_blocked: [uri,...]`).

### Sub-fase 9.4 — Test

- [ ] 9.4.1 test_install_v3_package_writes_to_store
- [ ] 9.4.2 test_install_v3_package_does_not_touch_workspace_dirs
- [ ] 9.4.3 test_install_v3_package_idempotent
- [ ] 9.4.4 test_install_v3_package_preserves_existing_override
- [ ] 9.4.5 test_install_v3_updates_registry_and_agents_md
- [ ] 9.4.6 test_remove_v3_package_deletes_store_and_manifest_entry
- [ ] 9.4.7 test_remove_v3_package_does_not_delete_overrides
- [ ] 9.4.8 test_remove_v3_package_warns_about_orphan_overrides
- [ ] 9.4.9 test_update_v3_package_skips_resources_with_override
- [ ] 9.4.10 test_v2_packages_still_use_legacy_flow
- [ ] 9.4.11 test_install_v3_blocks_when_engine_too_old (ridondante con
      check esistente, da verificare)

## Test di accettazione

- [ ] Suite completa pytest verde dopo ogni sub-fase.
- [ ] Tutti i 272 test pre-esistenti continuano a passare.
- [ ] +>=10 nuovi test in test_package_lifecycle_v3.py.
- [ ] Compile check: python -m py_compile spark-framework-engine.py.

## Note tecniche

- Sentinella manifest entry: il path `__store__/{pkg_id}` non
  intersecherà mai il filesystem workspace (prefisso non valido
  per workspace .github/), quindi ManifestManager.get_file_owners
  e _classify_install_files ignorano automaticamente la entry per
  `rel`-based lookup.
- `inventory.populate_mcp_registry` si ricostruisce ogni volta con
  registry fresco (idempotente, sicuro post-install/update/remove).
- Per fetchare i file di pacchetto v3 il flusso è identico a v2:
  `RegistryClient.fetch_raw_file(base_raw_url + file_path)`. La
  differenza è solo dove vengono scritti.
- Nessuna modifica al registry pubblico richiesta.
