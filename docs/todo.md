# SPARK Framework Engine — TODO Coordinatore

- **Sessione attiva:** Refactoring Modulare — Fase 0 (Modularizzazione)
- **Ultimo aggiornamento:** 2026-05-01
- **Stato piano:** VALIDATO — Confidence 0.9
- **Verdetto Copilot:** PIANO PRONTO PER REVISIONE UMANA

## Documenti di riferimento

- Design: `docs/REFACTORING-DESIGN.md`
- Prospetto tecnico: `docs/REFACTORING-TECHNICAL-BRIEF.md`
- Piano operativo Fase 0: `docs/coding plans/FASE0-PIANO-TECNICO.md`
- Rapporto di validazione: `docs/reports/FASE0-VALIDATION-REPORT.md`

---

## ⚠ PREREQUISITO ZERO — Baseline diagnostica

Prima di iniziare qualsiasi step, genera la baseline del tool diagnostico fisso.
Senza questo file l'invariante 3 di ogni step non è verificabile.

**Tool scelto:** `scf_verify_workspace`

**Procedura:**

1. Avvia il motore in locale:
   ```
   cd <cartella-repo>
   python spark-framework-engine.py
   ```
2. Da un client MCP (o `mcp dev`), chiama `scf_verify_workspace` senza argomenti.
3. Salva l'output JSON completo in:
   ```
   docs/reports/baseline-verify-workspace.json
   ```
4. Committa il file:
   ```
   git add docs/reports/baseline-verify-workspace.json
   git commit -m "docs(baseline): cattura output scf_verify_workspace pre-Fase0"
   ```

Da quel momento ogni step confronta il proprio output di verifica con questa baseline.
Se l'output cambia, lo step ha introdotto una modifica logica involontaria — rollback.

---

## Fase 0 — Modularizzazione (9 step)

Regola assoluta: nessuna modifica logica. Solo spostamento di codice.
Re-export hub: prima si aggiunge il re-export, poi si rimuove il codice originale.
Commit per ogni step completato: `refactor(modulo): estrai NomeClasse — nessuna modifica logica`

| Step | Modulo | Rischio | File TODO | Stato |
|------|--------|---------|-----------|-------|
| 01 | `core` | BASSO | [fase0-step-01-core.md](todolist/fase0-step-01-core.md) | [ ] |
| 02 | `merge` | MEDIO | [fase0-step-02-merge.md](todolist/fase0-step-02-merge.md) | [ ] |
| 03 | `manifest` | MEDIO | [fase0-step-03-manifest.md](todolist/fase0-step-03-manifest.md) | [ ] |
| 04 | `registry` | MEDIO | [fase0-step-04-registry.md](todolist/fase0-step-04-registry.md) | [ ] |
| 05 | `workspace` | ALTO | [fase0-step-05-workspace.md](todolist/fase0-step-05-workspace.md) | [ ] |
| 06 | `packages` | MEDIO | [fase0-step-06-packages.md](todolist/fase0-step-06-packages.md) | [ ] |
| 07 | `assets` | BASSO | [fase0-step-07-assets.md](todolist/fase0-step-07-assets.md) | [ ] |
| 08 | `boot` | ALTO | [fase0-step-08-boot.md](todolist/fase0-step-08-boot.md) | [ ] |
| 09 | `cleanup` | BASSO | [fase0-step-09-cleanup.md](todolist/fase0-step-09-cleanup.md) | [ ] |

**Invarianti di verifica dopo ogni step:**
1. Il motore si avvia senza eccezioni non gestite su stderr.
2. Il server MCP risponde — wiring FastMCP intatto, tool raggiungibili.
3. Output di `scf_verify_workspace` identico alla baseline in `docs/reports/baseline-verify-workspace.json`.

**Procedura di rollback se un invariante fallisce:**
```
git stash
# verifica che i tre invarianti tornino verdi
# analizza la dipendenza nascosta
# aggiorna il grafo in REFACTORING-DESIGN.md Sezione 6 se necessario
# ripeti lo step con la dipendenza inclusa
```
Schema commit aggiornamento grafo: `docs(design): aggiorna grafo — dipendenza [A→B] rilevata step N`

---

## Fasi successive (in attesa di Fase 0 completata)

| Fase | Obiettivo | Piano | Stato |
|------|-----------|-------|-------|
| Fase 1 | Stabilizzazione e correzione bug | [FASE1-PIANO-TECNICO.md](coding%20plans/FASE1-PIANO-TECNICO.md) | in attesa |
| Fase 2 | Boot deterministico | [FASE2-PIANO-TECNICO.md](coding%20plans/FASE2-PIANO-TECNICO.md) | in attesa |
| Fase 3 | Separazione runtime | [FASE3-PIANO-TECNICO.md](coding%20plans/FASE3-PIANO-TECNICO.md) | in attesa |
| Fase 4 | Gateway e workspace minimale | [FASE4-PIANO-TECNICO.md](coding%20plans/FASE4-PIANO-TECNICO.md) | in attesa |

---

## Anomalie note (non bloccanti, da trattare in Fase 1)

- **Log hardcoded:** messaggio `"Tools registered: 40 total"` a riga 8380 del sorgente
  riporta 40 tool ma il reale è 44. Da correggere in Fase 2 durante riscrittura `_build_app`.
- **`packages/diff.py` placeholder:** gli helper di diff sono inner function di `register_tools`
  e non estraibili senza modifica logica. Verranno migrati in Fase 1 con marker `# FASE1-RIASSEGNA`.
- **Costanti private:** le costanti oltre righe 44–55 (es. `_RESOURCE_TYPES`, `_MANIFEST_FILENAME`)
  richiedono rilettura puntuale durante Step 01 per evitare omissioni.

---

## Storico sessioni precedenti

Le sessioni implementative precedenti (v3.0.0 Dual-Client, SCF 3-Way Merge,
spark-base, File Ownership, Gateway Pattern) sono archiviate in `docs/archivio/`.
