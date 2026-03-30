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
3. Mostra piano pre-azione per ogni package aggiornabile:
   - package
   - versione installata
   - versione target
   - nota di preservazione file utente modificati
4. Chiedi conferma esplicita (es: "Confermi applicazione aggiornamenti? [si/no]").
5. Solo se l'utente conferma, esegui `scf_apply_updates()`.
6. Mostra esito finale con:
   - pacchetti aggiornati
   - pacchetti falliti
   - dettagli installati/preservati/errori

Se l'utente non conferma, interrompi senza modificare nulla.
