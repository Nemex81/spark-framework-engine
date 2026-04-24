---
applyTo: "spark-framework-engine.py, .github/prompts/**, .github/agents/**, .github/skills/**"
---

# Spark Engine Maintenance Instructions

Queste istruzioni definiscono le regole operative quando si lavora sul motore SCF in questo repository.

## Sezione A - Convenzioni naming tool MCP

- Tutti i tool devono usare il prefisso obbligatorio scf_.
- Il naming deve essere snake_case con forma verbo_sostantivo, ad esempio scf_list_skills o scf_get_prompt.
- La firma deve essere async con ritorno dict[str, Any].
- Ogni tool deve avere docstring non vuota.
- La prima riga della docstring deve essere orientata all'utente, non all'implementazione interna.

## Sezione B - Struttura register_tools()

- Ogni nuovo tool deve essere aggiunto in coda al blocco register_tools() della classe SparkFrameworkEngine.
- Dopo ogni aggiunta o rimozione, aggiornare il contatore nel commento di classe Tools (N).
- Dopo ogni aggiunta o rimozione, aggiornare anche il log finale Tools registered: N total.
- I due contatori devono restare sempre allineati con il numero reale di tool registrati.

## Sezione C - Convenzioni naming prompt

- Il file prompt deve seguire il pattern scf-{azione}.prompt.md, tutto minuscolo e con trattini.
- Frontmatter obbligatorio: type: prompt, name (slash command senza /), description orientata all'utente.
- Il corpo deve contenere istruzioni operative esplicite al modello, inclusi i tool MCP da chiamare per nome.
- I nomi tool nel corpo sono istruzioni al modello e non devono comparire nell'output utente.
- Ogni prompt che modifica file deve richiedere conferma esplicita si/no prima di procedere.
- Ogni prompt distruttivo deve elencare i file preservati per modifiche manuali utente.

## Sezione D - Formato CHANGELOG e versioning

- File di riferimento: CHANGELOG.md in root.
- Formato obbligatorio: Keep a Changelog.
- Versioning obbligatorio: Semantic Versioning.
- Bump patch x.x.N per fix, correzioni minori, aggiornamenti documentazione.
- Bump minor x.N.0 per nuovi tool, prompt, skill o agenti.
- Bump major N.0.0 per breaking change, refactor architetturali, cambio interfaccia MCP.
- Dopo ogni bump, aggiornare ENGINE_VERSION in spark-framework-engine.py.
- ENGINE_VERSION e ultima voce di CHANGELOG.md devono sempre essere allineati.

## Sezione E - Regola di conferma prima di modificare

- Non modificare mai file senza conferma esplicita dell'utente.
- Proporre sempre anteprima/diff prima di applicare cambiamenti.
- Per modifiche a spark-framework-engine.py mostrare il diff atteso e attendere approvazione.
