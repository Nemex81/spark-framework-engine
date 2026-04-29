# TODO Fase G — Migrazione Workspace Esistenti

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-g--migrazione-workspace-esistenti)

Stato: Completata

---

## Rilevamento workspace pre-esistente

- [x] Al primo `scf_update_package` o `scf_bootstrap_workspace`: verificare assenza `spark-user-prefs.json`
- [x] Se assente: avviare configurazione policy iniziale (come descritto in Fase E)
- [x] Salvare policy default `{"auto_update": false, "default_mode": "ask"}`
- [x] Se il workspace è già parzialmente migrato: rilevare lo stato corrente e proporre solo il delta mancante
- [x] Non rieseguire bootstrap o migrazione completa quando sono già presenti artefatti validi della migrazione

## File senza front matter SCF

- [x] Riconoscere file installati senza campi `scf_*` nel front matter
- [x] Trattarli come `scf_merge_strategy: replace` (default retrocompatibile)
- [x] Non aggiungere front matter `scf_*` ai file esistenti automaticamente
- [x] Log informativo: "file senza metadata SCF trattato con strategia replace"

## Migrazione `copilot-instructions.md`

- [x] Se `copilot-instructions.md` esiste senza marcatori SCF: NON iniettare marcatori automaticamente
- [x] Proporre migrazione esplicita al formato a marcatori nel return value
- [x] Opzione: `{"action_required": "migrate_copilot_instructions", "current_format": "plain", "proposed_format": "scf_markers"}`
- [x] Se utente accetta: wrappare contenuto esistente come sezione utente + iniettare sezioni pacchetto
- [x] Se utente rifiuta: preservare file corrente, saltare merge sezioni
- [x] Garantire esplicitamente che il testo utente fuori dai marcatori `SCF:BEGIN/END` resti intoccabile dopo la migrazione
- [x] Se il file è già in formato marker ma incompleto: proporre solo il completamento dei blocchi mancanti

## Autorizzazione cartella protetta `.github/`

- [x] Prima di qualsiasi scrittura: presentare l'avviso cartella protetta dello Step 3 del piano
- [x] Supportare entrambe le modalità di autorizzazione: conferma esplicita in chat (`confermo`) oppure prompt `/framework-unlock`
- [x] Se `github_write_authorized` è assente o `false` in `orchestrator-state.json`: bloccare la migrazione senza scrivere nulla
- [x] L'autorizzazione vale solo per la sessione attiva corrente e deve essere verificata prima di ogni blocco di scrittura

## Documentazione migrazione

- [x] Sezione dedicata in README: "Migrazione da workspace pre-ownership"
- [x] Prompt `/scf-migrate-workspace` per guidare la migrazione
- [x] FAQ: "cosa succede ai miei file personalizzati?"

## Test migrazione

- [x] Test: workspace con file senza front matter `scf_*`
- [x] Test: workspace con `copilot-instructions.md` plain (senza marcatori)
- [x] Test: workspace con `spark-user-prefs.json` assente
- [x] Test: workspace parzialmente migrato (delta-only, nessuna ripetizione completa)
- [x] Test: migrazione accettata dall'utente
- [x] Test: migrazione rifiutata (preservazione file)
- [x] Test: migrazione bloccata senza autorizzazione `.github/`
- [x] Test: testo utente fuori dai marcatori preservato dopo migrazione accettata

## Gate di uscita

- [x] `pytest -q` passa suite completa
- [x] Workspace pre-esistente non viene corrotto da operazioni standard
- [x] Migrazione opt-in funzionante
- [x] README e prompt di migrazione completi

## Evidenze finali

- Test delta-only aggiunto in `tests/test_migrate_workspace.py`:
  `test_partial_workspace_migration_applies_delta_only`.
- FAQ migrazione aggiornata in `docs/MIGRATION-GUIDE-v3.md`.
- Gate finale verificato con suite completa engine (escluso live integration).
