---
name: scf-release-check
description: Esegue la checklist pre-release del motore SCF verificando coerenza interna, CHANGELOG, versione e README. Propone il tag git da creare senza applicarlo autonomamente.
---

# Skill: scf-release-check

Obiettivo: validare la release readiness del motore e proporre il tag corretto senza eseguire azioni distruttive.

## Checklist pre-release

1. Coerenza interna.
- Eseguire la procedura scf-coherence-audit.
- Bloccare il rilascio in presenza di CRITICAL.

2. Verifica CHANGELOG.
- Leggere CHANGELOG.md.
- Verificare presenza di voce Unreleased oppure voce con versione corrente.
- Verificare coerenza tra note e modifiche reali nel codice.
- Segnalare changelog vuoto o non aggiornato.

3. Allineamento ENGINE_VERSION.
- Leggere versione corrente con scf_get_framework_version (restituisce `engine_version` e le versioni dei pacchetti installati).
- Confrontare con ultima voce in CHANGELOG.md.
- Segnalare mismatch.

4. Verifica README.
- Verificare contatore tool dichiarato vs numero reale in register_tools().
- Verificare contatore resource dichiarato vs numero reale in register_resources().
- Segnalare disallineamenti.

5. Verifica TODO/placeholder.
- Cercare TODO, FIXME, HACK, XXX, pass non attesi in spark-framework-engine.py.
- Segnalare ogni occorrenza con file e riga.

6. Proposta tag git.
- Se tutti i controlli passano, proporre git tag vX.Y.Z.
- Non eseguire tag automaticamente.
- Ricordare il passaggio git push --tags dopo conferma utente.

## Tool da usare

- scf_get_framework_version (restituisce `engine_version` e le versioni dei pacchetti installati)
- scf_list_prompts
- readFile
- runCommand (sola lettura: git log --oneline -10, git status, git tag)
