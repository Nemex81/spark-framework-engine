# TODO Fase E — Estensione `scf_bootstrap_workspace`

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-e--estensione-scf_bootstrap_workspace)

Stato: Non avviata

---

## Estensione flusso bootstrap

- [ ] Aggiungere parametro opzionale `update_mode: str = ""` alla firma esistente
- [ ] Preservare il comportamento attuale (copia asset + install spark-base) come sottoinsieme
- [ ] Inserire Step 1 (lettura policy) prima della copia asset
- [ ] Se `spark-user-prefs.json` assente: restituire `{"action_required": "configure_update_policy", ...}`
- [ ] Dopo configurazione policy: procedere con flusso esteso

## Configurazione policy iniziale

- [ ] Restituire opzioni strutturate nel return value (non prompt interattivo)
- [ ] Opzioni: `ask` (default raccomandato), `integrative`, `conservative`, `ask_later`
- [ ] Se nessuna risposta / annullamento: salvare `auto_update: false`
- [ ] Salvare policy tramite logica interna (stessa di `scf_set_update_policy`)

## Riepilogo diff

- [ ] Chiamare `_scf_diff_workspace()` su tutti i file di `spark-base`
- [ ] Includere diff summary nel return value
- [ ] Workspace già inizializzato: mostrare solo differenze rispetto alla versione installata

## Avviso e autorizzazione cartella protetta

- [ ] Includere `authorization_required: true` nel return value
- [ ] Verificare `github_write_authorized` in `orchestrator-state.json`
- [ ] Bloccare esecuzione se non autorizzato

## Idempotenza

- [ ] Sentinella: `.github/agents/spark-assistant.agent.md`
- [ ] Se presente: status `already_bootstrapped`, proporre solo aggiornamenti
- [ ] Preservare logica `already_bootstrapped_and_installed` esistente
- [ ] Test: bootstrap su workspace nuovo, bootstrap su workspace esistente

## Test end-to-end

- [ ] Test: primo bootstrap completo con configurazione policy
- [ ] Test: bootstrap ripetuto (idempotenza)
- [ ] Test: bootstrap con `install_base=True` + `update_mode=integrative`
- [ ] Test: bootstrap senza `install_base` (solo asset + policy)
- [ ] Test: regressione — comportamento attuale preservato senza `update_mode`

## Gate di uscita

- [ ] `pytest -q` passa suite completa
- [ ] Nessuna regressione sul flusso bootstrap attuale
- [ ] Flusso esteso funzionante con policy e diff
- [ ] Configurazione policy iniziale verificata
