# SPARK Framework — Proposta Strategica Implementativa

## SCF File Ownership & Workspace Merge System

**Versione:** 1.1.0-draft
**Data:** 17 Aprile 2026
**Autore:** Nemex81 / SPARK Architecture Team
**Stato:** Proposta corretta — Validazione superata con correzioni
**Repository di riferimento:** `spark-framework-engine`, `spark-base`, `scf-master-codecrafter`, `scf-pycode-crafter`, `scf-registry`

---

## Indice

- Premessa e Obiettivo
- Parte 1 — Convenzione Universale di Ownership dei File
- Parte 2 — Schema a Marcatori per `copilot-instructions.md`
- Parte 3 — Preferenze Persistenti di AggiornAMENTO
- Parte 4 — Flusso Operativo Completo con Autorizzazione
- Parte 5 — Modalità di AggiornAMENTO
- Parte 6 — Architettura dei Tool nell'Engine
- Parte 7 — Fasi di Implementazione
- Appendice A — Note di Compatibilità con Engine Esistente
- Appendice B — Log di Validazione

---

## Premessa e Obiettivo

Il sistema SPARK distribuisce file nel workspace dell'utente attraverso pacchetti SCF (`.github/agents/`, `.github/instructions/`, `.github/skills/`, ecc.). Attualmente manca un meccanismo formale che regoli cosa accade a quei file quando un pacchetto viene installato, aggiornato o rimosso: non esiste tracciabilità di ownership, non esiste logica di merge, non esiste protezione delle personalizzazioni dell'utente.

Questa proposta definisce il sistema completo per risolvere il problema su tre livelli:

- **Ownership**: ogni file conosce il pacchetto di provenienza.
- **Merge**: i file aggregati (come `copilot-instructions.md`) si aggiornano per sezioni senza distruggere il contenuto utente.
- **Controllo**: l'utente sceglie come gestire gli aggiornamenti, con preferenze persistenti e autorizzazione esplicita alle operazioni sulla cartella protetta `.github/`.

---

<!-- Contenuto completo archiviato; per la versione originale vedere la cronologia del repository -->

---

**Archivio:** Stato: Completata — Spostato in `docs/piani archiviati` il 19 Aprile 2026 (OWN-G)
