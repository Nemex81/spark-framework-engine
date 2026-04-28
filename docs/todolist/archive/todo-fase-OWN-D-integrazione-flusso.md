# TODO Fase D — Integrazione Flusso nei Tool Pubblici

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-d--integrazione-flusso-nei-tool-pubblici)

Stato: Completata

---

## Parametro `update_mode` per `scf_install_package`

- [x] Aggiungere parametro opzionale `update_mode: str = ""` alla firma
- [x] Valori accettati: `""` (default → consulta policy), `integrative`, `replace`, `conservative`, `selective`
- [x] Preservare parametro `conflict_mode` esistente con semantica invariata
- [x] Se `update_mode` assente: consultare `spark-user-prefs.json` → riportare la scelta nel return value
- [x] Test: install con update_mode esplicito, install senza update_mode

## Parametro `update_mode` per `scf_update_package`

- [x] Aggiungere parametro opzionale `update_mode: str = ""` alla firma
- [x] Stessa logica di risoluzione di `scf_install_package`
- [x] Test: update con/senza update_mode

## Step 1 — Lettura Policy

- [x] Integrare lettura `spark-user-prefs.json` all'inizio del flusso install/update
- [x] Fallback a `{"auto_update": false, "default_mode": "ask"}` se file assente
- [x] Logica di risoluzione override: `mode_per_package` → `mode_per_file_role` → `default_mode`

## Step 2 — Riepilogo Pre-Operazione

- [x] Chiamare `_scf_diff_workspace()` per generare classificazione file
- [x] Includere riepilogo nel return value del tool (campo `diff_summary`)
- [x] Escludere file `unchanged` dal riepilogo

## Step 3 — Avviso Cartella Protetta

- [x] Includere campo `authorization_required: true` nel return value quando `auto_update: false`
- [x] Verificare `github_write_authorized` in `orchestrator-state.json`
- [x] Se non autorizzato: ritornare `{"action_required": "authorize_github_write"}` senza scrivere file
- [x] Autorizzazione vale solo per sessione corrente

## Step 4 — Esecuzione Automatica o Richiesta

- [x] Se `auto_update: true` e `update_mode` risolto: eseguire direttamente
- [x] Se `auto_update: false`: ritornare riepilogo con opzioni scelta nel return value
- [x] Protezioni implicite attive anche in modo automatico (`scf_protected`, file modificati)

## Step 5 — Backup Pre-Sostitutivo

- [x] Se modalità `replace` (sostitutivo): chiamare `_scf_backup_workspace()` automaticamente
- [x] Includere path backup nel return value
- [x] Test: backup creato prima della scrittura file

## Step 6 — Esecuzione e Log

- [x] Applicare operazioni file per file secondo la modalità scelta
- [x] Usare `_scf_section_merge()` per file con `merge_sections`
- [x] Log compatto nel return value: lista file con azione eseguita
- [x] Test integrazione: flusso completo install con tutti gli step

## Gate di uscita

- [x] `pytest -q` passa suite completa (nuovi test + regressione)
- [x] I tool `scf_install_package` e `scf_update_package` mantengono backward compatibility
- [x] Il flusso senza `update_mode` funziona come prima (nessuna regressione)
- [x] Il flusso con `update_mode` esplicito salta la domanda di scelta
- [x] Protezioni implicite verificate con test dedicato

Nota implementativa:

- L'enforcement di autorizzazione/scelta OWN-D si attiva quando esiste una policy workspace esplicita oppure quando il caller passa `update_mode`.
- In assenza di policy file e senza `update_mode`, il flusso legacy resta invariato per preservare la backward compatibility richiesta dal gate.
