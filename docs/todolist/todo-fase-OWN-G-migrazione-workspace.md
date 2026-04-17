# TODO Fase G — Migrazione Workspace Esistenti

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-g--migrazione-workspace-esistenti)

Stato: Non avviata

---

## Rilevamento workspace pre-esistente

- [ ] Al primo `scf_update_package` o `scf_bootstrap_workspace`: verificare assenza `spark-user-prefs.json`
- [ ] Se assente: avviare configurazione policy iniziale (come descritto in Fase E)
- [ ] Salvare policy default `{"auto_update": false, "default_mode": "ask"}`
- [ ] Se il workspace è già parzialmente migrato: rilevare lo stato corrente e proporre solo il delta mancante
- [ ] Non rieseguire bootstrap o migrazione completa quando sono già presenti artefatti validi della migrazione

## File senza front matter SCF

- [ ] Riconoscere file installati senza campi `scf_*` nel front matter
- [ ] Trattarli come `scf_merge_strategy: replace` (default retrocompatibile)
- [ ] Non aggiungere front matter `scf_*` ai file esistenti automaticamente
- [ ] Log informativo: "file senza metadata SCF trattato con strategia replace"

## Migrazione `copilot-instructions.md`

- [ ] Se `copilot-instructions.md` esiste senza marcatori SCF: NON iniettare marcatori automaticamente
- [ ] Proporre migrazione esplicita al formato a marcatori nel return value
- [ ] Opzione: `{"action_required": "migrate_copilot_instructions", "current_format": "plain", "proposed_format": "scf_markers"}`
- [ ] Se utente accetta: wrappare contenuto esistente come sezione utente + iniettare sezioni pacchetto
- [ ] Se utente rifiuta: preservare file corrente, saltare merge sezioni
- [ ] Garantire esplicitamente che il testo utente fuori dai marcatori `SCF:BEGIN/END` resti intoccabile dopo la migrazione
- [ ] Se il file è già in formato marker ma incompleto: proporre solo il completamento dei blocchi mancanti

## Autorizzazione cartella protetta `.github/`

- [ ] Prima di qualsiasi scrittura: presentare l'avviso cartella protetta dello Step 3 del piano
- [ ] Supportare entrambe le modalità di autorizzazione: conferma esplicita in chat (`confermo`) oppure prompt `/framework-unlock`
- [ ] Se `github_write_authorized` è assente o `false` in `orchestrator-state.json`: bloccare la migrazione senza scrivere nulla
- [ ] L'autorizzazione vale solo per la sessione attiva corrente e deve essere verificata prima di ogni blocco di scrittura

## Documentazione migrazione

- [ ] Sezione dedicata in README: "Migrazione da workspace pre-ownership"
- [ ] Prompt `/scf-migrate-workspace` per guidare la migrazione
- [ ] FAQ: "cosa succede ai miei file personalizzati?"

## Test migrazione

- [ ] Test: workspace con file senza front matter `scf_*`
- [ ] Test: workspace con `copilot-instructions.md` plain (senza marcatori)
- [ ] Test: workspace con `spark-user-prefs.json` assente
- [ ] Test: workspace parzialmente migrato (delta-only, nessuna ripetizione completa)
- [ ] Test: migrazione accettata dall'utente
- [ ] Test: migrazione rifiutata (preservazione file)
- [ ] Test: migrazione bloccata senza autorizzazione `.github/`
- [ ] Test: testo utente fuori dai marcatori preservato dopo migrazione accettata

## Gate di uscita

- [ ] `pytest -q` passa suite completa
- [ ] Workspace pre-esistente non viene corrotto da operazioni standard
- [ ] Migrazione opt-in funzionante
- [ ] README e prompt di migrazione completi
