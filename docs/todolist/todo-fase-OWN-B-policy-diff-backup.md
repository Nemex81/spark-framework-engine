# TODO Fase B — Tool di Policy e Utility Diff/Backup

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-b--tool-di-policy-e-utility-diffbackup)

Stato: Completata

---

## Template e schema `spark-user-prefs.json`

- [x] Definire schema JSON completo con campi: `auto_update`, `default_mode`, `mode_per_package`, `mode_per_file_role`, `last_changed`, `changed_by_user`
- [x] Definire costante `_USER_PREFS_FILENAME = "runtime/spark-user-prefs.json"`
- [x] Implementare funzione di lettura con fallback a valori default
- [x] Implementare validazione `default_mode` (rifiutare `selective` come auto-mode)

## Tool `scf_get_update_policy()`

- [x] Implementare tool MCP con decorator `@self._mcp.tool()`
- [x] Docstring chiara in inglese, orientata all'utente
- [x] Ritorna contenuto `spark-user-prefs.json` o default se assente
- [x] Nessun effetto collaterale
- [x] Test unitario: file presente, file assente, file corrotto

## Tool `scf_set_update_policy()`

- [x] Implementare tool MCP con parametri: `auto_update` (obbligatorio), `default_mode`, `mode_per_package`, `mode_per_file_role` (opzionali)
- [x] Validazione: `default_mode` non può essere `selective`
- [x] Merge parziale: aggiorna solo i campi passati, preserva gli altri
- [x] Aggiorna `last_changed` con timestamp UTC ISO
- [x] Imposta `changed_by_user: true`
- [x] Test unitario: creazione da zero, aggiornamento parziale, validazione selective

## Utility `_scf_diff_workspace()`

- [x] Firma: `_scf_diff_workspace(package_id, version, remote_files, manifest)` → `list[dict]`
- [x] Classificazione file: `new`, `updated_clean`, `updated_user_modified`, `unchanged`
- [x] Riuso `ManifestManager._is_user_modified()` per rilevamento SHA-256
- [x] Supporto `files_metadata` schema 2.1 (fallback a default se assente)
- [x] Test unitario: file nuovo, file clean, file modificato, file invariato

## Utility `_scf_backup_workspace()`

- [x] Firma: `_scf_backup_workspace(package_id, files_to_backup)` → `str` (path backup)
- [x] Directory target: `.github/runtime/backups/YYYYMMDD-HHMMSS/`
- [x] Copia solo i file effettivamente toccati dall'operazione
- [x] Riuso infrastruttura `SnapshotManager` dove possibile
- [x] Test unitario: backup creato, directory corretta, file copiati

## Aggiornamento contatori

- [x] Aggiornare commento di classe: Tools (35)
- [x] Aggiornare log: `Tools registered: 35 total`
- [x] Verificare allineamento contatori

## Gate di uscita

- [x] `pytest -q` passa per tutti i test nuovi
- [x] I 2 nuovi tool compaiono nel log di registrazione
- [x] Nessun tool pubblico esistente modificato
- [x] `_scf_diff_workspace` e `_scf_backup_workspace` testati in isolamento
