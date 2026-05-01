# Piani archiviati

Questa cartella raccoglie i piani di implementazione e i piani correttivi completati per l'ecosistema SPARK Framework.

Un file viene spostato qui quando tutte le attività previste sono state implementate, testate e convalidate. I file archiviati **non devono essere modificati**: rappresentano la documentazione storica di come il progetto è evoluto e costituiscono un riferimento utile per capire le decisioni architetturali prese nel tempo.

## Struttura dei nomi

I file seguono due convenzioni di nomenclatura:

- `NOME-PIANO-IMPL-PLAN.md` — piano di implementazione di una funzionalità o componente specifico
- `NOME-PIANO-DESIGN.md` — documento di design architetturale preliminare
- `NOME-CORRETTIVO-DATA.md` — piano correttivo applicato a una specifica data

## Piani presenti

| File | Tipo | Oggetto |
|------|------|---------|
| [PIANO-CORRETTIVO-ECOSISTEMA-2026-04-02.md](./PIANO-CORRETTIVO-ECOSISTEMA-2026-04-02.md) | Correttivo | 6 correzioni cross-repo (2026-04-02) |
| [SCF-AUTOMERGE-IMPL-PLAN.md](./SCF-AUTOMERGE-IMPL-PLAN.md) | Implementazione | Auto-merge PR nel registry sync gateway |
| [SCF-CANONICAL-TRUTH-IMPL-PLAN.md](./SCF-CANONICAL-TRUTH-IMPL-PLAN.md) | Implementazione | Fonte canonica unica per metadati pacchetto |
| [SCF-CORRECTIVE-PLAN.md](./SCF-CORRECTIVE-PLAN.md) | Correttivo | Piano correttivo generico SCF |
| [SCF-PACKAGE-PROMPTS-PLAN.md](./SCF-PACKAGE-PROMPTS-PLAN.md) | Implementazione | Prompt e instruction per pacchetti SCF |
| [SCF-PROJECT-DESIGN.md](./SCF-PROJECT-DESIGN.md) | Design | Architettura generale del sistema SCF |
| [SCF-REGISTRY-SYNC-GATEWAY-IMPL-PLAN.md](./SCF-REGISTRY-SYNC-GATEWAY-IMPL-PLAN.md) | Implementazione | Workflow registry-sync-gateway |
| [SCF-SKILL-DUAL-FORMAT-PLAN.md](./SCF-SKILL-DUAL-FORMAT-PLAN.md) | Implementazione | Formato duale per file skill |
| [SPARK-ENGINE-MAINTAINER-DESIGN-REV1.md](./SPARK-ENGINE-MAINTAINER-DESIGN-REV1.md) | Design | Revisione 1 del maintainer engine |
| [SPARK-ENGINE-MAINTAINER-IMPL-PLAN.md](./SPARK-ENGINE-MAINTAINER-IMPL-PLAN.md) | Implementazione | Implementazione completa maintainer engine |
| [SPARK-ENGINE-TASK-SYNC-REGISTRY-WORKFLOW-IMPL-PLAN.md](./SPARK-ENGINE-TASK-SYNC-REGISTRY-WORKFLOW-IMPL-PLAN.md) | Implementazione | Workflow di sync task/registry |
| [piano correttivo per spark.md](./piano%20correttivo%20per%20spark.md) | Correttivo | Piano correttivo iniziale SPARK |

## Regole di archiviazione

1. Un piano viene spostato qui solo dopo che il relativo CHANGELOG riporta la voce corrispondente come completata.
2. Il nome del file non deve essere modificato dopo l'archiviazione.
3. Non aprire issue o PR che fanno riferimento a questi file come "da fare": sono storia, non backlog.
