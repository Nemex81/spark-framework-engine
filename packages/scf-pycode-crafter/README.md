# scf-pycode-crafter

Plugin SCF per progetti Python.

Questo package non e piu un layer framework completo: fornisce solo i componenti
Python-specifici e richiede `scf-master-codecrafter` come dipendenza diretta.

## Contenuto

Questo pacchetto installa nella cartella `.github/` del tuo workspace:

- **Indice plugin:** `AGENTS-python.md`
- **Profilo plugin:** `python.profile.md`
- **Agenti Python:** Analyze, Code, Design, Plan, Validate
- **Instruction Python-specific:** `python.instructions.md`, `tests.instructions.md`
- **Reference Python:** `error-recovery/reference/errors-python.md`
- **Workflow:** `notify-engine.yml` per notificare aggiornamenti del manifest al motore

Il manifest corrente del pacchetto e `package-manifest.json` schema `3.1`, versione `2.3.0`, con risorse MCP-only gestite.

## Installazione

Tramite il server MCP `spark-framework-engine`:

```python
scf_install_package("scf-pycode-crafter")
```

Prerequisito: installare prima `scf-master-codecrafter`, oppure lasciare che il motore
gestisca la dipendenza dichiarata nel manifest. La catena effettiva diventa:

`spark-base` → `spark-ops` → `scf-master-codecrafter` → `scf-pycode-crafter`

## Compatibilità

- `spark-framework-engine` >= 3.1.0
- `scf-master-codecrafter` >= 2.7.0 installato
- Python >= 3.10
- VS Code con GitHub Copilot

## Manifest Pacchetto

Il pacchetto usa `package-manifest.json` schema `3.1` con metadati espliciti per
compatibilita motore, dipendenze dichiarative e ownership dei file.

## Convenzione Changelog

Il changelog canonico del pacchetto e:

`.github/changelogs/scf-pycode-crafter.md`

Il motore deve leggere il path dichiarato nel campo `changelog_path` del manifest
del pacchetto, senza reintrodurre `FRAMEWORK_CHANGELOG.md` come riferimento canonico.

## Modello architetturale

- Il layer master fornisce agenti trasversali, dispatcher, instruction comuni e skill condivise.
- Questo plugin aggiunge solo competenze Python-specifiche sopra il layer master.
- Gli aggiornamenti devono restare coerenti con le dipendenze dichiarate nel manifest.

## Note

SPARK Code Framework — pacchetto dominio Python.
