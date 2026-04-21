---
type: prompt
name: scf-update-policy
description: Mostra o aggiorna la policy update del workspace con conferma esplicita prima di scrivere il file di policy.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "prompt"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
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