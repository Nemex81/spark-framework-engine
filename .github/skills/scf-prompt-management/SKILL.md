---
name: scf-prompt-management
description: Crea, valida e corregge prompt SCF verificando frontmatter, naming convention, istruzioni operative e regole di conferma.
spark: true
scf_owner: "spark-framework-engine"
scf_version: "2.3.2"
scf_file_role: "skill"
scf_merge_strategy: "replace"
scf_merge_priority: 0
scf_protected: false
---

# Skill: scf-prompt-management

Obiettivo: garantire che i prompt SCF rispettino convenzioni formali e comportamento operativo atteso.

## Convenzioni obbligatorie

Frontmatter richiesto:

---
type: prompt
name: scf-nome-azione
description: Descrizione orientata all'utente finale, senza riferimenti tecnici interni.
---

Regole corpo:
- Le istruzioni operative devono nominare esplicitamente i tool MCP da chiamare.
- L'output utente non deve esporre i nomi tecnici dei tool MCP.
- I prompt che modificano file devono richiedere conferma si/no prima di procedere.
- I prompt distruttivi devono elencare i file preservati per modifiche manuali.

## Procedura creazione nuovo prompt

1. Verificare unicita del name con scf_list_prompts.
2. Determinare i tool necessari e verificare che esistano nel motore.
3. Costruire frontmatter con type, name, description.
4. Scrivere corpo con passi operativi espliciti al modello.
5. Proporre file completo e attendere conferma prima della creazione.

## Procedura validazione prompt esistente

1. Leggere prompt con scf_get_prompt.
2. Verificare frontmatter: type, name, description.
3. Verificare naming file: scf-{azione}.prompt.md, minuscolo, trattini.
4. Verificare esistenza tool citati nel motore.
5. Verificare richiesta conferma per prompt modificativi.
6. Produrre report PASS, WARNING, CRITICAL con azioni suggerite.

## Tool da usare

- scf_list_prompts
- scf_get_prompt
- editFiles
- readFile
