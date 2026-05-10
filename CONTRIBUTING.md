# Contributing — spark-framework-engine

Questa guida raccoglie le procedure operative ricorrenti che richiedono
attenzione cross-file. Per le convenzioni generali (Python style, test,
commit) fare riferimento a `.github/instructions/` e ai report di branch
in `docs/reports/`.

---

## Rinomina agenti SCF

Quando si rinomina un agente in `packages/<pkg>/.github/agents/<name>.agent.md`
(es. `Agent-Code.md` → `code-Agent-Code.md`), aggiornare in modo coordinato
i seguenti riferimenti per evitare che resti un nome stale (cfr. Bug D del
report `SPARK-REPORT-LiveFixture-v1.0.md`):

1. **Manifest pacchetto** — `packages/<pkg>/package-manifest.json`
   - Aggiornare le voci in `files`, `workspace_files` e `plugin_files`
     che puntano al vecchio path agente.

2. **File fisico** — `git mv` del file agente al nuovo nome.
   Mantenere il frontmatter intatto (in particolare `name`, `scf_owner`).

3. **Test** — eseguire ricerca su `tests/` per occorrenze del nome vecchio:

   ```powershell
   Select-String -Path "tests\**\*.py" -Pattern "<old-name>" -SimpleMatch
   ```

   Aggiornare in particolare `tests/test_integration_live.py` e
   qualsiasi fixture che usi `conflict_rel`, `expected_files` o path
   hard-coded sotto `.github/agents/`.

4. **CHANGELOG** — aggiungere voce in `[Unreleased]` sezione `Changed`
   con il diff `vecchio_nome → nuovo_nome` e la motivazione (es.
   "razionalizzazione prefisso `code-` per agenti del layer master").

5. **Cross-reference doc** — controllare `README.md` di pacchetto e
   ogni `docs/reports/SPARK-REPORT-*.md` recente per riferimenti al
   nome agente.

6. **Validazione** — eseguire la suite completa:

   ```
   C:/Users/nemex/Envs/audiomaker311/Scripts/python.exe -m pytest tests/ -q --tb=short
   ```

   Risultato atteso: ≥ baseline corrente (oggi 476 passed, 9 skipped, 0
   failed). Una variazione del numero di passati segnala riferimenti
   stale non aggiornati.

---

## Aggiunta o rimozione tool MCP

Vedere `.github/skills/scf-tool-development/SKILL.md` per la procedura
completa. In sintesi:

- decorator `@_register_tool("scf_*")` + docstring inglese
- aggiornare il contatore `Tools registered: N total` nel log di boot
- aggiungere test in `tests/test_register_tools.py`
- aggiornare CHANGELOG

---

## Fixture pytest condivise

Se la stessa logica di setup compare in due o piu fixture distinte (es.
inizializzazione di `runtime/orchestrator-state.json`), estrarla come
helper in `tests/conftest.py`. La soglia operativa e **due o piu usi**:
sotto questa soglia preferire l'inline per leggibilita locale.
