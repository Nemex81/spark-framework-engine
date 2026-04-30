---
spark: true
name: framework-scope-guard
description: Protegge il layer master da richieste fuori scope o non coperte dai plugin installati.
---

# framework-scope-guard

- Se il task richiede competenze non presenti, non improvvisare: instrada ad Agent-Research.
- Se il task chiede modifiche fuori perimetro framework, esplicitalo prima di procedere.
- Se un dispatcher non trova capability compatibili, ferma l'esecuzione automatica e segnala il fallback.