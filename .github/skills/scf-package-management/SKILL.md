---
name: scf-package-management
description: Flusso operativo riutilizzabile per installare, aggiornare, rimuovere e verificare pacchetti SCF nel workspace utente.
---

# Skill: scf-package-management

Obiettivo: gestire il ciclo di vita dei pacchetti SCF nel workspace in modo prevedibile e leggibile.

## Installazione

- Usare `scf_list_available_packages` per il catalogo.
- Usare `scf_get_package_info(package_id)` per confermare dipendenze, conflitti e compatibilita.
- Usare `scf_install_package(package_id)` solo dopo aver spiegato l'impatto essenziale.

## Aggiornamento

- Usare `scf_check_updates` per il delta rapido.
- Usare `scf_update_packages` per il piano ordinato e dependency-aware.
- Usare `scf_apply_updates(package_id | None, conflict_mode)` solo quando l'utente vuole applicare davvero gli update e ha scelto la strategia di conflitto appropriata.

## Rimozione

- Verificare prima i pacchetti installati con `scf_list_installed_packages`.
- Usare `scf_remove_package(package_id)` spiegando eventuali file preservati per modifiche utente.

## Verifica

- Usare `scf_verify_workspace` per integrita manifest e file SCF.
- Usare `scf_verify_system` per controlli di coerenza piu ampi sul framework.

## Regola pratica

- Preferire sempre il tool piu specifico disponibile invece di combinare manualmente piu operazioni se il motore ha gia un flusso dedicato.