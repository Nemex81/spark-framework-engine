# SPARK Framework Engine — Roadmap Fase 2

## 1. conflict_mode: "merge"

- Comportamento atteso: merge a 3 vie sui file markdown tra versione installata, versione utente e nuova versione pacchetto.
- Euristica sui blocchi frontmatter: i campi utente hanno precedenza su quelli del pacchetto salvo una lista esplicita di campi protetti.
- Prerequisiti tecnici: parser diff dedicato per markdown strutturato e funzione `_merge_markdown_blocks()` in ManifestManager.
- Stima complessità: alta — richiede versione motore 2.0.0.

## 2. scf_plan_install batch

- Estensione del dry-run a liste di pacchetti in input.
- Dependency graph completo calcolato prima di qualsiasi operazione su disco.
- Conflict report aggregato per tutti i pacchetti in un unico oggetto strutturato.
- Stima complessità: media — richiede versione motore 1.10.0.

## 3. notify-engine.yml — meccanismo push-to-registry

- Il workflow GitHub Actions gia presente in scf-pycode-crafter (.github/workflows/notify-engine.yml) e il prototipo del meccanismo futuro per notificare il registry di nuove versioni.
- Comportamento target: push su main nei repo pacchetto che innesca l'aggiornamento automatico di registry.json.
- Prerequisiti: GitHub Actions con write access su scf-registry, token dedicato e schema webhook in RegistryClient.
- Stima complessità: media — indipendente dalla versione motore.

## 4. Stato attuale

- Engine version: 1.9.0
- Tool registrati: 29
- Test: 83 passed (unit) + 3 passed (integration)
- conflict_mode supportati in produzione: "abort", "replace"
- conflict_mode pianificati: "merge" (Fase 2, motore 2.0.0)
