# TODO Fase C — Utility di Section Merge

Piano di riferimento: [SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md](../SCF-COPILOT-INSTRUCTIONS-MERGE-STRATEGY.md#fase-c--utility-di-merge)

Stato: Non avviata

---

## Implementazione `_scf_section_merge()`

- [ ] Firma: `_scf_section_merge(source_content, target_path, strategy, package_id, version)` → `str`
- [ ] Non scrive su disco — restituisce contenuto finale
- [ ] Separazione netta da `MergeEngine.diff3_merge()` (file-level vs section-level)

## Strategia `replace`

- [ ] Sostituisce integralmente il contenuto del file sorgente nel target
- [ ] Preserva front matter del target se presente
- [ ] Test: file nuovo, file esistente, file con front matter

## Strategia `merge_sections` (SCF markers)

- [ ] Regex apertura: `<!-- SCF:BEGIN:{package_id}@[^\s>]+ -->`
- [ ] Regex chiusura: `<!-- SCF:END:{package_id} -->`
- [ ] Match tollerante sulla versione (SemVer completo incluso pre-release)
- [ ] Se blocco esistente: sostituzione in-place
- [ ] Se blocco assente: inserimento rispettando `merge_priority`
- [ ] Preservazione assoluta testo utente fuori dai marcatori
- [ ] Generazione header SCF se file vuoto o nuovo
- [ ] Ordinamento sezioni per `merge_priority` crescente
- [ ] Test: blocco esistente aggiornato, blocco nuovo inserito, ordine multi-pacchetto
- [ ] Test: versione pre-release nel marker (es. `1.0.0-beta.1`)
- [ ] Test: file senza marcatori esistenti (prima sezione)
- [ ] Test: blocco corrotto (marker apertura senza chiusura)

## Strategia `user_protected`

- [ ] Non sovrascrive mai automaticamente
- [ ] Restituisce il contenuto corrente del target invariato
- [ ] Log della proposta di aggiornamento (senza applicarla)
- [ ] Test: file protetto non viene modificato

## Rimozione sezione pacchetto

- [ ] Funzione companion: `_scf_strip_section(content, package_id)` → `str`
- [ ] Elimina blocco da `SCF:BEGIN` a `SCF:END` inclusi i marker
- [ ] Preserva tutto il resto del file
- [ ] Test: rimozione singola sezione, rimozione da file multi-sezione

## Gate di uscita

- [ ] `pytest -q` passa per tutti i test nuovi
- [ ] Copertura test su tutte e 3 le strategie + rimozione
- [ ] Casi limite testati: file vuoto, marker corrotto, versioni pre-release
- [ ] Nessun tool pubblico esistente modificato
