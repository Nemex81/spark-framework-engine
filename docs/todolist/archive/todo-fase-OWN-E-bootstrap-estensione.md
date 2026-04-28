# TODO Fase E — Estensione `scf_bootstrap_workspace`

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-e--estensione-scf_bootstrap_workspace)

Stato: Completata

---

## Estensione flusso bootstrap

- [x] Aggiungere parametro opzionale `update_mode: str = ""` alla firma esistente
- [x] Preservare il comportamento attuale (copia asset + install spark-base) come sottoinsieme
- [x] Inserire Step 1 (lettura policy) prima della copia asset
- [x] Se `spark-user-prefs.json` assente: restituire configurazione policy strutturata nel flusso esteso solo quando `update_mode` e esplicito
- [x] Dopo configurazione policy: procedere con flusso esteso

## Configurazione policy iniziale

- [x] Restituire opzioni strutturate nel return value (non prompt interattivo)
- [x] Opzioni: `ask` (default raccomandato), `integrative`, `conservative`, `ask_later`
- [x] Se nessuna risposta / annullamento: preservare il flusso legacy senza policy per backward compatibility
- [x] Salvare policy tramite logica interna (stessa di `scf_set_update_policy`)

## Riepilogo diff

- [x] Chiamare `_scf_diff_workspace()` su tutti i file di `spark-base`
- [x] Includere diff summary nel return value
- [x] Workspace già inizializzato: mostrare solo differenze rispetto alla versione installata

## Avviso e autorizzazione cartella protetta

- [x] Includere `authorization_required: true` nel return value
- [x] Verificare `github_write_authorized` in `orchestrator-state.json`
- [x] Bloccare esecuzione se non autorizzato

## Idempotenza

- [x] Sentinella: `.github/agents/spark-assistant.agent.md`
- [x] Se presente: status `already_bootstrapped`, proporre solo aggiornamenti
- [x] Preservare logica `already_bootstrapped_and_installed` esistente
- [x] Test: bootstrap su workspace nuovo, bootstrap su workspace esistente

## Test end-to-end

- [x] Test: primo bootstrap completo con configurazione policy
- [x] Test: bootstrap ripetuto (idempotenza)
- [x] Test: bootstrap con `install_base=True` + `update_mode=integrative`
- [x] Test: bootstrap senza `install_base` (solo asset + policy)
- [x] Test: regressione — comportamento attuale preservato senza `update_mode`

## Gate di uscita

- [x] `pytest -q` passa suite completa
- [x] Nessuna regressione sul flusso bootstrap attuale
- [x] Flusso esteso funzionante con policy e diff
- [x] Configurazione policy iniziale verificata

Nota implementativa:

- Per preservare la backward compatibility, il bootstrap legacy resta attivo quando `update_mode` non e fornito e il workspace non ha ancora una policy esplicita.
- Il ramo OWN-E con handshake policy/auth si attiva quando `update_mode` e esplicito oppure quando il workspace ha gia `spark-user-prefs.json`.
