---
name: scf-tool-development
description: Guida la procedura completa per aggiungere o rimuovere tool MCP dal motore SCF rispettando tutte le convenzioni di naming, struttura e aggiornamento contatori.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.1"
scf_file_role: "skill"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

# Skill: scf-tool-development

Obiettivo: introdurre o rimuovere tool MCP in modo sicuro, coerente e verificabile.

## Procedura aggiunta tool

1. Verifica pre-aggiunta.
- Validare naming con prefisso scf_, snake_case, forma verbo_sostantivo.
- Verificare assenza di omonimi in register_tools().
- Verificare che la funzionalita non sia gia coperta da tool esistenti.

2. Implementazione.
- Aggiungere il tool in coda al blocco register_tools() di SparkFrameworkEngine.
- Firma: async def nome_tool(...) -> dict[str, Any].
- Prima riga docstring orientata all'utente in italiano.
- Gestire errori e restituire sempre dict[str, Any].

3. Aggiornamento contatori obbligatorio.
- Aggiornare N nel commento Tools (N).
- Aggiornare N nel log Tools registered: N total.
- Verificare che i due valori siano identici e corretti.

4. Proposta e conferma.
- Mostrare diff completo proposto.
- Attendere conferma esplicita utente prima di applicare.
- Applicare solo dopo conferma con editFiles.

5. Post-aggiunta.
- Invocare scf-changelog per classificare bump minor e aggiornare documentazione release.
- Se il tool tocca scritture di file condivisi o ownership-aware, documentare esplicitamente quando va usato `_scf_section_merge()` invece di path sostitutivi diretti.

## Procedura rimozione tool

1. Verifica dipendenze.
- Usare scf_list_prompts e scf_get_prompt su tutti i prompt.
- Verificare che nessun prompt referenzi il tool da rimuovere.
- Se ci sono dipendenze, bloccare la rimozione e segnalare remediation.

2. Rimozione e contatori.
- Rimuovere il metodo da register_tools().
- Decrementare i contatori nel commento e nel log.
- Verificare allineamento dei contatori.

3. Proposta e conferma.
- Mostrare diff completo.
- Attendere conferma esplicita prima di applicare.

## Tool da usare

- readFile
- editFiles
- scf_list_prompts
- scf_get_prompt
- scf_get_workspace_info

## Nota su file condivisi

- I file con `scf_merge_strategy: merge_sections` non vanno gestiti come semplici overwrite: il percorso canonico del motore e' `_scf_section_merge()`.
- I file `user_protected` devono restare delegati al workspace senza overwrite impliciti.
