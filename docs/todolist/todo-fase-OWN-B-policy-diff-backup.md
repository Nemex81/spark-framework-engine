# TODO Fase B — Tool di Policy e Utility Diff/Backup

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-b--tool-di-policy-e-utility-diffbackup)

Stato: Non avviata

---

## Template e schema `spark-user-prefs.json`

- [ ] Definire schema JSON completo con campi: `auto_update`, `default_mode`, `mode_per_package`, `mode_per_file_role`, `last_changed`, `changed_by_user`
- [ ] Definire costante `_USER_PREFS_FILENAME = "runtime/spark-user-prefs.json"`
- [ ] Implementare funzione di lettura con fallback a valori default
- [ ] Implementare validazione `default_mode` (rifiutare `selective` come auto-mode)

## Tool `scf_get_update_policy()`

- [ ] Implementare tool MCP con decorator `@self._mcp.tool()`
- [ ] Docstring chiara in inglese, orientata all'utente
- [ ] Ritorna contenuto `spark-user-prefs.json` o default se assente
- [ ] Nessun effetto collaterale
- [ ] Test unitario: file presente, file assente, file corrotto

## Tool `scf_set_update_policy()`

- [ ] Implementare tool MCP con parametri: `auto_update` (obbligatorio), `default_mode`, `mode_per_package`, `mode_per_file_role` (opzionali)
- [ ] Validazione: `default_mode` non può essere `selective`
- [ ] Merge parziale: aggiorna solo i campi passati, preserva gli altri
- [ ] Aggiorna `last_changed` con timestamp UTC ISO
- [ ] Imposta `changed_by_user: true`
- [ ] Test unitario: creazione da zero, aggiornamento parziale, validazione selective

## Utility `_scf_diff_workspace()`

- [ ] Firma: `_scf_diff_workspace(package_id, version, remote_files, manifest)` → `list[dict]`
- [ ] Classificazione file: `new`, `updated_clean`, `updated_user_modified`, `unchanged`
- [ ] Riuso `ManifestManager._is_user_modified()` per rilevamento SHA-256
- [ ] Supporto `files_metadata` schema 2.1 (fallback a default se assente)
- [ ] Test unitario: file nuovo, file clean, file modificato, file invariato

## Utility `_scf_backup_workspace()`

- [ ] Firma: `_scf_backup_workspace(package_id, files_to_backup)` → `str` (path backup)
- [ ] Directory target: `.github/runtime/backups/YYYYMMDD-HHMMSS/`
- [ ] Copia solo i file effettivamente toccati dall'operazione
- [ ] Riuso infrastruttura `SnapshotManager` dove possibile
- [ ] Test unitario: backup creato, directory corretta, file copiati

## Aggiornamento contatori

- [ ] Aggiornare commento di classe: Tools (35)
- [ ] Aggiornare log: `Tools registered: 35 total`
- [ ] Verificare allineamento contatori

## Gate di uscita

- [ ] `pytest -q` passa per tutti i test nuovi
- [ ] I 2 nuovi tool compaiono nel log di registrazione
- [ ] Nessun tool pubblico esistente modificato
- [ ] `_scf_diff_workspace` e `_scf_backup_workspace` testati in isolamento
