# TODO Fase C — Utility di Section Merge

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-c--utility-di-merge)

Stato: Completata

---

## Implementazione `_scf_section_merge()`

- [x] Firma: `_scf_section_merge(source_content, target_path, strategy, package_id, version)` → `str`
- [x] Non scrive su disco — restituisce contenuto finale
- [x] Separazione netta da `MergeEngine.diff3_merge()` (file-level vs section-level)

## Strategia `replace`

- [x] Sostituisce integralmente il contenuto del file sorgente nel target
- [x] Preserva front matter del target se presente
- [x] Test: file nuovo, file esistente, file con front matter

## Strategia `merge_sections` (SCF markers)

- [x] Regex apertura: `<!-- SCF:BEGIN:{package_id}@[^\s>]+ -->`
- [x] Regex chiusura: `<!-- SCF:END:{package_id} -->`
- [x] Match tollerante sulla versione (SemVer completo incluso pre-release)
- [x] Se blocco esistente: sostituzione in-place
- [x] Se blocco assente: inserimento rispettando `merge_priority`
- [x] Preservazione assoluta testo utente fuori dai marcatori
- [x] Generazione header SCF se file vuoto o nuovo
- [x] Ordinamento sezioni per `merge_priority` crescente
- [x] Test: blocco esistente aggiornato, blocco nuovo inserito, ordine multi-pacchetto
- [x] Test: versione pre-release nel marker (es. `1.0.0-beta.1`)
- [x] Test: file senza marcatori esistenti (prima sezione)
- [x] Test: blocco corrotto (marker apertura senza chiusura)

## Strategia `user_protected`

- [x] Non sovrascrive mai automaticamente
- [x] Restituisce il contenuto corrente del target invariato
- [x] Log della proposta di aggiornamento (senza applicarla)
- [x] Test: file protetto non viene modificato

## Rimozione sezione pacchetto

- [x] Funzione companion: `_scf_strip_section(content, package_id)` → `str`
- [x] Elimina blocco da `SCF:BEGIN` a `SCF:END` inclusi i marker
- [x] Preserva tutto il resto del file
- [x] Test: rimozione singola sezione, rimozione da file multi-sezione

## Gate di uscita

- [x] `pytest -q` passa per tutti i test nuovi
- [x] Copertura test su tutte e 3 le strategie + rimozione
- [x] Casi limite testati: file vuoto, marker corrotto, versioni pre-release
- [x] Nessun tool pubblico esistente modificato
