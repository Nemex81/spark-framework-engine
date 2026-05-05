---
type: prompt
name: scf-update-batch
description: Controlla e applica aggiornamenti a tutti i pacchetti SCF installati.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.3.0"
agent: agent
spark: true
scf_owner: "spark-base"
---

# scf-update-batch — Aggiornamento batch pacchetti SCF

Opzioni: ${input:Opzioni opzionali (es: --skip)}

## Sequenza

1. Se l'input contiene `--skip`: chiama `scf_update_runtime_state` con
   `update_check_done: true` e `last_update_check: <oggi YYYY-MM-DD>`;
   rispondi `Aggiornamento ignorato per questa sessione.` e termina.
2. Chiama `scf_update_packages()` per ottenere il piano aggiornamenti.
3. Se il piano è vuoto: rispondi `Tutti i pacchetti sono aggiornati.` e termina.
4. Se il manifesto è in formato legacy: interrompi con `ERRORE:` e chiedi all'utente
   di eseguire `scf_verify_workspace()` per diagnosi prima di procedere.
5. Mostra la tabella del piano:
   `| Pacchetto | Versione installata | Versione disponibile | Azione |`
6. Chiedi conferma: `Aggiornare tutti i pacchetti? (sì/no/seleziona)`
7. Se sì: chiama `scf_apply_updates()`.
8. Se selezione: chiama `scf_apply_updates(package_id)` per ogni pacchetto scelto.
9. Delega commit ad Agent-Git: `chore(packages): update <pkg> to vX.Y.Z`.
10. Mostra report finale: pacchetti aggiornati, file toccati, file preservati, SHA commit.
