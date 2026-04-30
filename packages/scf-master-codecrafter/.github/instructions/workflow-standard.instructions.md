---
applyTo: "**"
name: workflow-standard
package: scf-master-codecrafter
version: 1.0.0
spark: true
---

# Workflow Standard

## Sequenza

1. Analyze
2. Design
3. Plan
4. Code
5. Validate
6. Docs
7. Release

## Regole

- Ogni fase deve avere un criterio di uscita verificabile.
- Non passare alla fase successiva se la validazione locale fallisce.
- Aggiorna `docs/TODO.md` dopo ogni fase implementativa.
- Se manca una capability plugin, usa il fallback Agent-Research e segnala il gap.