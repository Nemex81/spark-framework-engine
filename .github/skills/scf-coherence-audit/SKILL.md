---
name: scf-coherence-audit
description: Esegue un audit di coerenza completo del motore SCF verificando contatori tool, allineamento prompt/tool e consistenza documentazione. Non modifica nulla - riporta solo discrepanze.
---

# Skill: scf-coherence-audit

Obiettivo: verificare coerenza interna del motore SCF senza applicare modifiche.

## Procedura operativa

1. Verifica contatori tool.
- Leggere spark-framework-engine.py.
- Contare i tool registrati con @mcp.tool in register_tools().
- Confrontare con il valore nel commento di classe Tools (N).
- Confrontare con il valore nel log finale Tools registered: N total.
- Segnalare mismatch tra i tre valori.

2. Verifica docstring tool.
- Per ogni tool registrato, verificare che la docstring esista e non sia vuota.
- Segnalare ogni tool privo di docstring.

3. Verifica allineamento prompt/tool.
- Usare scf_list_prompts per elencare i prompt.
- Per ogni prompt, usare scf_get_prompt.
- Estrarre i nomi tool MCP referenziati nel corpo.
- Verificare che ogni tool esista in register_tools().
- Segnalare prompt che referenziano tool inesistenti.

4. Verifica coerenza documentazione.
- Leggere README.md e confrontare il contatore tool con il valore reale.
- Leggere CHANGELOG.md e verificare allineamento tra ultima voce e ENGINE_VERSION in spark-framework-engine.py.
- Segnalare disallineamenti.

5. Report finale.
- Produrre sezioni PASS, WARNING, CRITICAL.
- Per ogni WARNING o CRITICAL includere file, riga se disponibile, discrepanza e correzione suggerita.
- Non applicare correzioni automaticamente.

## Tool da usare

- scf_list_prompts
- scf_get_prompt
- scf_get_framework_version
- readFile
