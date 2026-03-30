---
name: scf-changelog
description: Determina il bump semantico corretto in base alle modifiche recenti, compila la voce CHANGELOG nel formato Keep a Changelog e aggiorna ENGINE_VERSION in spark-framework-engine.py.
---

# Skill: scf-changelog

Obiettivo: classificare correttamente il rilascio e mantenere allineati CHANGELOG.md e ENGINE_VERSION.

## Procedura operativa

1. Raccolta modifiche recenti.
- Usare `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati) per la versione corrente.
- Leggere `CHANGELOG.md` per identificare l'ultima voce rilasciata.
- Leggere modifiche recenti in `spark-framework-engine.py` e `.github/` tramite `readFile` o `changes`.

2. Determinazione bump semantico.
- Major se ci sono breaking change MCP o refactor architetturali incompatibili.
- Minor se ci sono nuovi tool, nuovi prompt, nuove skill o nuovi agenti.
- Patch se ci sono fix, correzioni o aggiornamenti documentazione.
- In caso di dubbio, proporre il bump all'utente con motivazione prima di procedere.

3. Compilazione voce CHANGELOG.
- Usare formato Keep a Changelog.
- Sezioni ammesse: Added, Changed, Fixed, Notes.
- Inserire solo sezioni con almeno una voce.
- Inserire la nuova voce in cima, dopo intestazione e prima delle versioni precedenti.

Template:

## [X.Y.Z] - GG mese AAAA

### Added
- voce

### Changed
- voce

### Fixed
- voce

### Notes
- voce

4. Aggiornamento ENGINE_VERSION.
- Localizzare `ENGINE_VERSION: str = "X.Y.Z"` in `spark-framework-engine.py`.
- Proporre diff e attendere conferma esplicita prima di applicare.

## Tool da usare

- `scf_get_framework_version` (restituisce `engine_version` e le versioni dei pacchetti installati)
- `readFile`
- `editFiles`
- `changes`
