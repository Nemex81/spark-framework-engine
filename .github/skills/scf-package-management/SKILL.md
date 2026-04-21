---
name: scf-package-management
description: Flusso operativo riutilizzabile per installare, aggiornare, rimuovere e verificare pacchetti SCF nel workspace utente.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "skill"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

# Skill: scf-package-management

Obiettivo: gestire il ciclo di vita dei pacchetti SCF nel workspace in modo prevedibile e leggibile.

## Installazione

- Usare `scf_list_available_packages` per il catalogo.
- Usare `scf_get_package_info(package_id)` per confermare dipendenze, conflitti e compatibilita.
- Usare `scf_get_update_policy()` quando serve chiarire come il workspace risolvera `update_mode`, autorizzazione e backup.
- Usare `scf_install_package(package_id, conflict_mode="...", update_mode="...")` solo dopo aver spiegato l'impatto essenziale.
- Se il tool restituisce `action_required`, non forzare workaround: completa prima il passo richiesto nel payload, ad esempio `action_required: "configure_update_policy"`, `action_required: "authorize_github_write"` o una scelta esplicita del mode.

## Aggiornamento

- Usare `scf_check_updates` per il delta rapido.
- Usare `scf_update_packages` per il piano ordinato e dependency-aware.
- Usare `scf_get_update_policy()` o `scf_set_update_policy(...)` quando il workspace deve cambiare comportamento di default prima dell'update.
- Usare `scf_update_package(package_id, conflict_mode="...", update_mode="...")` o `scf_apply_updates(package_id | None, conflict_mode)` solo quando l'utente vuole applicare davvero gli update e ha scelto la strategia appropriata.
- Distinguere sempre `conflict_mode` (file-level) da `update_mode` (package-level).

## Bootstrap

- Usare `scf_bootstrap_workspace(install_base=True, conflict_mode="...", update_mode="...")` per l'onboarding orchestrato dal motore MCP.
- Se il bootstrap restituisce `policy_configuration_required` o `authorization_required`, completa prima quel passaggio invece di ripetere il bootstrap in loop.

## Rimozione

- Verificare prima i pacchetti installati con `scf_list_installed_packages`.
- Usare `scf_remove_package(package_id)` spiegando eventuali file preservati per modifiche utente.

## Verifica

- Usare `scf_verify_workspace` per integrita manifest e file SCF.
- Usare `scf_verify_system` per controlli di coerenza piu ampi sul framework.

## Regola pratica

- Preferire sempre il tool piu specifico disponibile invece di combinare manualmente piu operazioni se il motore ha gia un flusso dedicato.
- Quando il workspace e' ownership-aware, riportare sempre `diff_summary`, file preservati, file sostituiti e backup creati se presenti.