---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Piano Tecnico Fase 4 — Gateway e workspace minimale
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Piano Tecnico Fase 4 — Gateway e workspace minimale

## 1. Obiettivo

Trasformare `spark/workspace/` in un layer di sola lettura. Introdurre un gateway centralizzato in `spark/manifest/` per tutte le scritture sul filesystem, garantendo che ogni modifica passi per `ManifestManager`.

## 2. Criterio di completamento

- Nessuna chiamata a `Path.write_text`, `Path.write_bytes`, `Path.unlink`, `shutil.copy*`, `shutil.rmtree` esiste in `spark/workspace/**`.
- Tutte le scritture su `<workspace>/.github/**` passano da `WorkspaceWriteGateway` (nuova classe in `spark/manifest/gateway.py`).
- Il gateway registra ogni scrittura nel manifest aggiornando `sha256` e `installed_at` automaticamente.
- I tool MCP `scf_install_package`, `scf_update_package`, `scf_remove_package`, `scf_bootstrap_workspace` usano il gateway, mai scritture dirette.

## 3. File coinvolti

- `spark/manifest/gateway.py` — nuovo. Espone `WorkspaceWriteGateway(workspace_root, manifest_manager)` con metodi `write(rel_path, content, owner, version)`, `delete(rel_path, owner)`, `copy(source, rel_path, owner, version)`.
- `spark/workspace/inventory.py` — rimuove eventuali metodi che oggi modificano filesystem (verifica con `grep -n "write_text\|write_bytes\|unlink" spark/workspace/`).
- `spark/packages/lifecycle.py` — sostituisce ogni scrittura diretta con chiamate al gateway.
- `spark/assets/renderers.py` — `_apply_phase6_assets` usa il gateway per scrivere `AGENTS.md`, `.clinerules`, `project-profile.md`.

## 4. Operazioni specifiche

1. Censire tutte le scritture filesystem sotto `<workspace>/.github/**` con `grep -rn "write_text\|write_bytes\|unlink\|shutil" spark/`.
2. Per ognuna, decidere: passa al gateway o resta scrittura interna a runtime/cache (questi ultimi non passano dal gateway).
3. Implementare `WorkspaceWriteGateway` con interfaccia minimale e idempotente.
4. Aggiornare `register_tools` in `spark/boot/sequence.py` perché istanzi e iniettì il gateway nei tool che ne hanno bisogno.
5. Aggiungere test che verificano: ogni scrittura tracciata nel manifest, nessuna scrittura silente.

## 5. Dipendenze dalla fase precedente

- Fase 3 chiusa: runtime separato dal workspace.
- `ManifestManager` ha API stabile per `upsert_many`, `purge_owner_entry`, `get_file_owners`.

## 6. Rischi specifici

- **Bug di tracciamento.** Se il gateway dimentica di registrare anche solo una scrittura, il manifest diverge dallo stato reale. Mitigazione: test E2E che verificano `scf_verify_workspace.is_clean == True` dopo ogni operazione.
- **Performance.** Il gateway aggiunge un livello indiretto su ogni scrittura. Mitigazione: batch writes in `WorkspaceWriteGateway.transaction()`.
- **Compatibilità tool esterni.** Tool che oggi scrivono direttamente sotto `.github/` (script di terze parti) non passano dal gateway; il gateway non li blocca, ma `scf_verify_workspace` li segnala come `user_modified`.

---

## DRIFT — Note di allineamento post-Fase 0/1 (2026-05-01)

Aggiornamenti alla struttura reale rispetto a quanto scritto sopra:

- **Sezione 3 — `spark/workspace/inventory.py`:** il file non esiste.
  `FrameworkInventory` ed `EngineInventory` vivono in `spark/inventory/framework.py`
  e `spark/inventory/engine.py` (package separato estratto in Fase 0).
  Il grep di Fase 4 deve includere `spark/inventory/`.
- **Sezione 3 — `spark/assets/renderers.py`:** il file non esiste come singolo file.
  Le funzioni di rendering sono distribuite in 4 file: `spark/assets/collectors.py`,
  `spark/assets/phase6.py`, `spark/assets/rendering.py`, `spark/assets/templates.py`.
  `_apply_phase6_assets` è in `spark/assets/phase6.py`.
- **`spark/workspace/migration.py`:** questo file esiste in `workspace/` (non in
  `packages/` come previsto dal piano originale). Contiene `MigrationPlan` e
  `MigrationPlanner` e include operazioni di scrittura filesystem. Va incluso nel
  censimento scritture di Fase 4 Operazione 1.
- **Verificare scritture in `spark/packages/lifecycle.py`:** `_install_package_v3_into_store`
  (funzione standalone, non il metodo istanza residuo) usa `dest.write_text` e
  `dest.parent.mkdir` direttamente. È un candidato naturale per la migrazione al
  gateway in Fase 4.
