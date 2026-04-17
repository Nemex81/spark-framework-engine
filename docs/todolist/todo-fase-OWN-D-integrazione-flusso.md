# TODO Fase D — Integrazione Flusso nei Tool Pubblici

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-d--integrazione-flusso-nei-tool-pubblici)

Stato: Non avviata

---

## Parametro `update_mode` per `scf_install_package`

- [ ] Aggiungere parametro opzionale `update_mode: str = ""` alla firma
- [ ] Valori accettati: `""` (default → consulta policy), `integrative`, `replace`, `conservative`, `selective`
- [ ] Preservare parametro `conflict_mode` esistente con semantica invariata
- [ ] Se `update_mode` assente: consultare `spark-user-prefs.json` → riportare la scelta nel return value
- [ ] Test: install con update_mode esplicito, install senza update_mode

## Parametro `update_mode` per `scf_update_package`

- [ ] Aggiungere parametro opzionale `update_mode: str = ""` alla firma
- [ ] Stessa logica di risoluzione di `scf_install_package`
- [ ] Test: update con/senza update_mode

## Step 1 — Lettura Policy

- [ ] Integrare lettura `spark-user-prefs.json` all'inizio del flusso install/update
- [ ] Fallback a `{"auto_update": false, "default_mode": "ask"}` se file assente
- [ ] Logica di risoluzione override: `mode_per_package` → `mode_per_file_role` → `default_mode`

## Step 2 — Riepilogo Pre-Operazione

- [ ] Chiamare `_scf_diff_workspace()` per generare classificazione file
- [ ] Includere riepilogo nel return value del tool (campo `diff_summary`)
- [ ] Escludere file `unchanged` dal riepilogo

## Step 3 — Avviso Cartella Protetta

- [ ] Includere campo `authorization_required: true` nel return value quando `auto_update: false`
- [ ] Verificare `github_write_authorized` in `orchestrator-state.json`
- [ ] Se non autorizzato: ritornare `{"action_required": "authorize_github_write"}` senza scrivere file
- [ ] Autorizzazione vale solo per sessione corrente

## Step 4 — Esecuzione Automatica o Richiesta

- [ ] Se `auto_update: true` e `update_mode` risolto: eseguire direttamente
- [ ] Se `auto_update: false`: ritornare riepilogo con opzioni scelta nel return value
- [ ] Protezioni implicite attive anche in modo automatico (`scf_protected`, file modificati)

## Step 5 — Backup Pre-Sostitutivo

- [ ] Se modalità `replace` (sostitutivo): chiamare `_scf_backup_workspace()` automaticamente
- [ ] Includere path backup nel return value
- [ ] Test: backup creato prima della scrittura file

## Step 6 — Esecuzione e Log

- [ ] Applicare operazioni file per file secondo la modalità scelta
- [ ] Usare `_scf_section_merge()` per file con `merge_sections`
- [ ] Log compatto nel return value: lista file con azione eseguita
- [ ] Test integrazione: flusso completo install con tutti gli step

## Gate di uscita

- [ ] `pytest -q` passa suite completa (nuovi test + regressione)
- [ ] I tool `scf_install_package` e `scf_update_package` mantengono backward compatibility
- [ ] Il flusso senza `update_mode` funziona come prima (nessuna regressione)
- [ ] Il flusso con `update_mode` esplicito salta la domanda di scelta
- [ ] Protezioni implicite verificate con test dedicato
