# Piano correttivo per l'ecosistema SPARK — 2 aprile 2026
**Stato:** ✅ implementato
> Piano revisionato dall'utente, validato da Copilot e pronto per implementazione.
> Correzioni ordinate per priorità reale. No refactoring non richiesti.
---
## Contesto
Ecosistema SPARK Framework composto da tre repository:
- `spark-framework-engine` — motore MCP Python (`spark-framework-engine.py`)
- `scf-registry` — registro JSON dei pacchetti (`registry.json`)
- `scf-pycode-crafter` — primo pacchetto SCF
Applicare le correzioni nell'ordine indicato.
No refactoring non richiesti.
Mantenere lo stile già presente nel codice.
Ogni modifica deve essere minima, coerente con l'architettura attuale e verificabile subito dopo l'implementazione.
---
## CORREZIONE 0 — Riallineare `scf-registry` alla versione reale del pacchetto
**Repository:** `scf-registry`
**File:** `registry.json`
**Problema:** Il pacchetto `scf-pycode-crafter` dichiara nel suo `package-manifest.json` la versione `1.1.0`, ma `scf-registry/registry.json` pubblica ancora `latest_version: "1.0.1"`.
**Root cause diagnosticata:** Il workflow `notify-engine.yml` è stato aggiunto nel commit `12cbfcc` **dopo** il commit `2e51365` che ha bumped la versione a `1.1.0`. La notifica automatica non è mai partita perché il trigger non esisteva ancora al momento del bump.
**Impatto:** Il registry comunica uno stato falso. Utenti e strumenti leggono una versione superata.
**Checklist implementazione**
- [ ] Aggiornare `scf-registry/registry.json` da `1.0.1` a `1.1.0`
- [ ] Aggiornare `updated_at` con timestamp UTC corrente
- [ ] Validare JSON
- [ ] Commit: `fix: sync registry with scf-pycode-crafter 1.1.0`
---
## CORREZIONE 1 — Docstring obsoleto in `register_tools()`
**Repository:** `spark-framework-engine`
**File:** `spark-framework-engine.py`
**Problema:** Il docstring del metodo `register_tools()` dichiara ancora `"Register all 22 MCP tools"` ma il metodo registra effettivamente 23 tool.
**Conferme verificate:**
- commento di sezione riga 716: `Tools (23)`
- log finale riga 1504: `"Tools registered: 23 total"`
- conteggio decoratori `@self._mcp.tool()`: 23
**Checklist implementazione**
- [ ] Modificare il docstring da `22` a `23`
- [ ] Eseguire `pytest -q`
- [ ] Commit: `fix: correct register_tools docstring tool count from 22 to 23`
---
## CORREZIONE 2 — Rimuovere `.scf-registry-cache.json` dal tracking Git
**Repository:** `spark-framework-engine`
**Problema:** Il file `.github/.scf-registry-cache.json` è ancora tracciato da Git nonostante sia già escluso dal `.gitignore`.
**Checklist implementazione**
- [ ] Eseguire `git rm --cached .github/.scf-registry-cache.json`
- [ ] Verificare con `git status` che sia staged come deleted
- [ ] Commit: `chore: remove tracked registry cache file (already in .gitignore)`
- [ ] Verificare con `git ls-files .github/.scf-registry-cache.json` che non ritorni nulla
---
## CORREZIONE 3 — Aggiornare README di `scf-registry` con dati reali
**Repository:** `scf-registry`
**File:** `README.md`
**Problema:** Il README dice ancora "Nessun pacchetto disponibile". Dopo CORREZIONE 0, la versione da mostrare è `1.1.0`.
**Checklist implementazione**
- [ ] Sostituire la sezione "Nessun pacchetto disponibile"
- [ ] Inserire `scf-pycode-crafter` con versione `1.1.0`
- [ ] Aggiungere nota sul sync automatico
- [ ] Commit: `docs: update README with available packages from registry`
---
## CORREZIONE 4 — Aggiungere validazione schema in `registry-sync-gateway.yml`
**Repository:** `spark-framework-engine`
**File:** `.github/workflows/registry-sync-gateway.yml`
**Problema:** Il workflow aggiorna `registry.json` e può auto-mergiare senza validare la struttura del JSON risultante.
**Nota:** `valid_statuses` limitato a `active` e `deprecated` — gli unici documentati nello schema README del registry.
**Checklist implementazione**
- [ ] Inserire lo step di validazione nel workflow tra "Update registry.json" e "Create Pull Request"
- [ ] Verificare indentazione YAML corretta
- [ ] Verificare regex semver con `^...$`
- [ ] Commit: `feat: add registry.json schema validation to sync gateway workflow`
---
## CORREZIONE 5 — Rinominare `docs_manager.skill.md` e allineare frontmatter + manifest
**Repository:** `scf-pycode-crafter`
**Problema:** `docs_manager.skill.md` usa underscore; tutti gli altri skill usano kebab-case. Anche il frontmatter interno riporta `name: docs_manager`.
**Checklist implementazione**
- [ ] Rinominare il file in kebab-case (`git mv`)
- [ ] Aggiornare `name:` nel frontmatter
- [ ] Aggiornare il path in `package-manifest.json`
- [ ] Verificare con grep che non restino riferimenti a `docs_manager`
- [ ] Commit: `fix: rename docs_manager.skill.md to docs-manager.skill.md for kebab-case consistency`
---
## CORREZIONE 6 — NON NECESSARIA
**Motivo:** La regola `scripts/*.out` è già presente nel `.gitignore` di `spark-framework-engine`. Nessuna azione richiesta.
---
## Verifica finale dopo tutte le correzioni
### `spark-framework-engine`
```bash
pytest -q
grep -c "@self._mcp.tool()" spark-framework-engine.py
git ls-files .github/.scf-registry-cache.json
```
Atteso: test verdi, conteggio = `23`, nessun output per il cache file.
### `scf-registry`
```bash
python -m json.tool registry.json > /dev/null
grep -n '"latest_version"' registry.json
grep -n '"updated_at"' registry.json
```
Atteso: JSON valido, `latest_version` = `1.1.0`, `updated_at` aggiornato.
### `scf-pycode-crafter`
```bash
grep -n 'docs-manager.skill.md' package-manifest.json
grep -rn '^name: docs-manager$' .github/skills
grep -rn 'docs_manager' . || true
```
Atteso: manifest aggiornato, frontmatter aggiornato, nessun riferimento residuo a `docs_manager`.
---
## Riepilogo finale
| # | Correzione | Priorità | Stato |
|---|---|---|---|
| 0 | Riallineare registry a `scf-pycode-crafter 1.1.0` | CRITICA | ✅ |
| 1 | Correggere docstring `register_tools()` da 22 a 23 | ALTA | ✅ |
| 2 | Rimuovere `.scf-registry-cache.json` dal tracking Git | ALTA | ✅ |
| 3 | Aggiornare README di `scf-registry` con dati reali | ALTA | ✅ |
| 4 | Aggiungere validazione schema nel workflow gateway | ALTA | ✅ |
| 5 | Rinominare `docs_manager.skill.md` e aggiornare frontmatter/manifest | MEDIA | ✅ |
| 6 | `scripts/*.out` in `.gitignore` | — | GIA RISOLTA

