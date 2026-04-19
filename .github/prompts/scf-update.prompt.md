---
type: prompt
name: scf-update
description: Applica aggiornamenti pacchetti SCF con conferma esplicita e preservazione file utente.
---

Obiettivo: aggiornare pacchetti installati mantenendo sempre i file user-modified.

Regola obbligatoria:
- Non applicare aggiornamenti finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Esegui `scf_update_packages()` per individuare update disponibili.
2. Se non ci sono update, informa l'utente e termina senza modifiche.
3. Esegui `scf_get_update_policy()` se l'utente vuole conoscere o modificare il comportamento di default del workspace prima di aggiornare.
4. Mostra il piano pre-azione usando `plan.order` restituito dal tool.
5. Per ogni package pianificato mostra:
   - package
   - versione installata
   - versione target
   - dipendenze che verranno aggiornate prima del package, se presenti
   - nota di preservazione file utente modificati
6. Se il piano contiene blocchi, mostrali e non proporre applicazione finche non sono risolti.
7. Prima di applicare, distingui i due livelli decisionali:
   - `conflict_mode` per i conflitti file-level
   - `update_mode` per il comportamento package-level (`integrative`, `replace`, `conservative`, oppure policy workspace)
8. Prima di applicare, chiedi quale strategia di conflitto usare:
   - `abort`: mantiene i file utente e blocca i conflitti non tracciati
   - `replace`: sovrascrive i file ufficiali anche se questo perde modifiche locali
   - `manual` / `auto` / `assisted`: prova una fusione coerente con la nuova versione
9. Se l'utente vuole cambiare il default del workspace prima del batch, usa `scf_set_update_policy(...)`; se vuole una sola eccezione puntuale, proponi `scf_update_package(package_id, conflict_mode="...", update_mode="...")` sul package target.
10. Chiedi conferma esplicita finale includendo il `conflict_mode` scelto e l'eventuale `update_mode`.
11. Solo se l'utente conferma, esegui `scf_apply_updates(package_id | None, conflict_mode=...)` oppure `scf_update_package(package_id, conflict_mode="...", update_mode="...")` se il caso e' singolo e richiede una strategia dedicata.
12. Se il tool restituisce `action_required`, fermati e mostra il passo richiesto prima di proporre altri update.
13. Mostra esito finale con:
   - pacchetti aggiornati
   - pacchetti falliti
   - ordine effettivamente applicato
   - dettagli installati/preservati/errori
   - `resolved_update_mode`, `diff_summary` e `backup_path` se presenti
14. Se `scf_apply_updates()` restituisce `batch_conflicts`, spiega che il preflight del batch ha bloccato l'operazione prima della prima scrittura e riporta i package coinvolti.

Se l'utente non conferma, interrompi senza modificare nulla.

*** Add File: c:\Users\nemex\OneDrive\Documenti\GitHub\spark-framework-engine\.github\prompts\scf-update-policy.prompt.md
---
type: prompt
name: scf-update-policy
description: Mostra o aggiorna la policy update del workspace con conferma esplicita prima di scrivere il file di policy.
---

Obiettivo: gestire in modo rapido e leggibile la policy update del workspace SCF.

Regola obbligatoria:
- Non modificare la policy finche l'utente non conferma in modo esplicito.

Istruzioni operative:
1. Esegui `scf_get_update_policy()` per leggere lo stato corrente.
2. Mostra un riepilogo con:
   - source della policy (`file`, `default_missing`, `default_corrupt`)
   - `auto_update`
   - `default_mode`
   - override `mode_per_package`
   - override `mode_per_file_role`
3. Se l'utente voleva solo consultare la policy, fermati qui.
4. Se l'utente vuole cambiarla, proponi le opzioni rilevanti:
   - `auto_update`: `true` / `false`
   - `default_mode`: `ask`, `integrative`, `replace`, `conservative`
   - override per package o per ruolo file se servono
5. Spiega l'impatto essenziale:
   - `ask`: richiede scelta esplicita nei flussi ownership-aware
   - `integrative`: privilegia integrazione e merge
   - `replace`: abilita il percorso sostitutivo con backup
   - `conservative`: preserva piu facilmente i file locali
6. Chiedi conferma esplicita finale con domanda chiusa.
7. Solo se l'utente conferma, esegui `scf_set_update_policy(...)` con i valori scelti.
8. Mostra esito finale con:
   - policy aggiornata
   - `last_changed`
   - `changed_by_user`

Se l'utente non conferma, interrompi senza modificare nulla.
