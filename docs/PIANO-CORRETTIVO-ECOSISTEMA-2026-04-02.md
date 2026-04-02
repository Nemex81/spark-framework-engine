# Piano correttivo per l'ecosistema SPARK — 2 aprile 2026

> Piano originale fornito dall'utente, **validato e corretto** da Copilot.
> Le sezioni marcate con ⚠️ contengono integrazioni o modifiche rispetto al piano originale.
> La CORREZIONE 6 è stata rimossa perché già risolta.

---

## Contesto

Ecosistema SPARK Framework composto da tre repository:

- `spark-framework-engine` — motore MCP Python (`spark-framework-engine.py`)
- `scf-registry` — registro JSON dei pacchetti (`registry.json`)
- `scf-pycode-crafter` — primo pacchetto SCF

Applicare le correzioni nell'ordine indicato. No refactoring non richiesti. Mantenere lo stile già presente nel codice.

---

## CORREZIONE 1 — Docstring obsoleto in `register_tools()`

**File:** `spark-framework-engine/spark-framework-engine.py`

**Problema:** Il docstring del metodo `register_tools()` dichiara `"Register all 22 MCP tools"` ma il metodo registra effettivamente 23 tool (confermato da: 23 decoratori `@self._mcp.tool()`, commento `Tools (23)` alla riga 716, log `"Tools registered: 23 total"` alla riga 1504).

**Cosa fare:** Trova questa riga:

```python
def register_tools(self) -> None:  # noqa: C901
    """Register all 22 MCP tools."""
```

Correggila in:

```python
def register_tools(self) -> None:  # noqa: C901
    """Register all 23 MCP tools."""
```

**Nota validazione:** Il test `test_tool_counter_consistency` verifica il commento `Tools (N)` e il log, non il docstring. Il docstring è comunque incoerente e va corretto.

### Checklist implementazione

- [ ] Modificare docstring da "22" a "23" nel metodo `register_tools()`
- [ ] Eseguire `pytest -q` — deve rimanere verde
- [ ] Commit: `fix: correct register_tools docstring tool count from 22 to 23`

---

## CORREZIONE 2 — Rimuovere `.scf-registry-cache.json` dal tracking Git

**Repository:** `spark-framework-engine`

**Problema:** Il file `.github/.scf-registry-cache.json` è tracciato da Git nonostante sia già presente in `.gitignore`. Verificato con `git ls-files`.

**Cosa fare:** Esegui nel terminale dalla root di `spark-framework-engine`:

```bash
git rm --cached .github/.scf-registry-cache.json
git commit -m "chore: remove tracked registry cache file (already in .gitignore)"
```

Non eliminare il file dal disco — solo dal tracking Git. Il `.gitignore` esistente già lo esclude dai commit futuri.

### Checklist implementazione

- [ ] Eseguire `git rm --cached .github/.scf-registry-cache.json`
- [ ] Verificare con `git status` che il file compaia come deleted (staged)
- [ ] Commit: `chore: remove tracked registry cache file (already in .gitignore)`
- [ ] Verificare con `git ls-files .github/.scf-registry-cache.json` che non restituisca nulla

---

## CORREZIONE 3 — Aggiornare README di `scf-registry`

**File:** `scf-registry/README.md`

**Problema:** Il README afferma "Nessun pacchetto disponibile" ma `scf-pycode-crafter` è presente in `registry.json` con status `active`.

**Cosa fare:** Sostituire la sezione "Pacchetti disponibili" con il contenuto aggiornato da `registry.json`:

```markdown
## Pacchetti disponibili

### scf-pycode-crafter

| Campo | Valore |
|-------|--------|
| **ID** | `scf-pycode-crafter` |
| **Versione** | `1.0.1` |
| **Engine minimo** | `1.2.1` |
| **Stato** | `active` |
| **Repository** | [Nemex81/scf-pycode-crafter](https://github.com/Nemex81/scf-pycode-crafter) |
| **Tag** | `python`, `development`, `copilot`, `agenti` |

Pacchetto SCF per progetti Python — agenti, skill e instruction per Copilot Agent mode.

Per installare:
```
scf_install_package("scf-pycode-crafter")
```

> **Nota:** il registro si aggiorna automaticamente via GitHub Action (`registry-sync-gateway.yml`)
> quando un pacchetto pubblica una nuova versione tramite `repository_dispatch`.
```

Mantenere il resto del README invariato.

### Checklist implementazione

- [ ] Sostituire sezione "Pacchetti disponibili" nel README
- [ ] Aggiungere nota sul sync automatico via GitHub Action
- [ ] Verificare rendering Markdown
- [ ] Commit: `docs: update README with available packages from registry`

---

## CORREZIONE 4 — Aggiungere validazione schema in `registry-sync-gateway.yml`

**File:** `spark-framework-engine/.github/workflows/registry-sync-gateway.yml`

**Problema:** Il workflow aggiorna `registry.json` e crea una PR con auto-merge, ma non valida la struttura del JSON risultante. Un output malformato passerebbe senza barriere.

**Cosa fare:** Aggiungere un nuovo step **tra** `Update registry.json` e `Create Pull Request on scf-registry`:

```yaml
      - name: Validate registry.json after update
        run: |
          python3 - <<'EOF'
          import json
          import sys

          registry_path = "scf-registry/registry.json"
          try:
              with open(registry_path, "r", encoding="utf-8") as f:
                  data = json.load(f)
          except json.JSONDecodeError as e:
              print(f"::error::registry.json is not valid JSON after update: {e}")
              sys.exit(1)

          required_root_fields = ["schema_version", "updated_at", "packages"]
          for field in required_root_fields:
              if field not in data:
                  print(f"::error::Missing required root field: '{field}'")
                  sys.exit(1)

          if not isinstance(data["packages"], list):
              print("::error::Field 'packages' must be a list")
              sys.exit(1)

          required_pkg_fields = ["id", "repo_url", "latest_version", "engine_min_version", "status"]
          import re
          semver_re = re.compile(r"^\d+\.\d+\.\d+")

          for pkg in data["packages"]:
              pkg_id = pkg.get("id", "<unknown>")
              for field in required_pkg_fields:
                  if field not in pkg:
                      print(f"::error::Package '{pkg_id}' missing required field: '{field}'")
                      sys.exit(1)
              for ver_field in ["latest_version", "engine_min_version"]:
                  if not semver_re.match(str(pkg.get(ver_field, ""))):
                      print(f"::error::Package '{pkg_id}' field '{ver_field}' is not a valid semver: '{pkg.get(ver_field)}'")
                      sys.exit(1)
              valid_statuses = {"active", "deprecated", "beta"}
              if pkg.get("status") not in valid_statuses:
                  print(f"::error::Package '{pkg_id}' has invalid status: '{pkg.get('status')}'. Must be one of: {valid_statuses}")
                  sys.exit(1)

          print(f"registry.json validation passed: {len(data['packages'])} package(s) checked.")
          EOF
```

⚠️ **Osservazione Copilot:** Il set `valid_statuses` include `"beta"` che il README schema del registry non elenca (dice solo `active` / `deprecated`). Non è un blocco — `"beta"` è un'estensione ragionevole — ma andrebbe allineata la documentazione README se si intende supportare lo status `beta` a regime. Valuteremo in fase di implementazione se aggiornare anche la tabella schema nel README del registry.

### Checklist implementazione

- [ ] Inserire step di validazione tra "Update registry.json" e "Create Pull Request"
- [ ] Verificare indentazione YAML corretta (6 spazi per `- name:`, 10 per `run:`)
- [ ] Commit: `feat: add registry.json schema validation to sync gateway workflow`

---

## CORREZIONE 5 — Rinominare `docs_manager.skill.md` in `scf-pycode-crafter`

**Repository:** `scf-pycode-crafter`

**Problema:** Tutti i file skill usano kebab-case (es. `clean-architecture-rules.skill.md`), ma `docs_manager.skill.md` usa underscore.

**Cosa fare:**

1. Rinominare il file da `docs_manager.skill.md` a `docs-manager.skill.md` nella directory `.github/skills/`

2. Aggiornare il riferimento in `package-manifest.json`: sostituire `docs_manager.skill.md` con `docs-manager.skill.md` nell'array `files`

3. ⚠️ **Integrazione Copilot — mancante nel piano originale:** aggiornare il frontmatter YAML dentro il file rinominato. Attualmente riga 2 contiene:
   ```yaml
   name: docs_manager
   ```
   Va corretto in:
   ```yaml
   name: docs-manager
   ```

4. Verificare che non ci siano altri riferimenti a `docs_manager` (con underscore) nel repo

### Checklist implementazione

- [ ] Rinominare file `.github/skills/docs_manager.skill.md` → `docs-manager.skill.md`
- [ ] Aggiornare frontmatter `name:` nel file rinominato da `docs_manager` a `docs-manager`
- [ ] Aggiornare riferimento in `package-manifest.json`
- [ ] Grep per `docs_manager` nel repo — nessun match residuo
- [ ] Commit: `fix: rename docs_manager.skill.md to docs-manager.skill.md for kebab-case consistency`

---

## ~~CORREZIONE 6~~ — RIMOSSA

**Motivo:** `scripts/*.out` è **già presente** nel `.gitignore` del motore (riga 59). La correzione non è necessaria.

---

## Verifica finale dopo tutte le correzioni

```bash
# Dal repo spark-framework-engine
pytest -q

# Verifica che il cache file non sia più tracciato
git status  # non deve comparire .github/.scf-registry-cache.json

# Verifica il conteggio tool nel sorgente
grep -c "@self._mcp.tool()" spark-framework-engine.py  # deve restituire 23
```

Risultato atteso: pytest verde, 23 tool confermati, nessun file di cache tracciato.

---

## Riepilogo validazione Copilot

| # | Correzione | Esito validazione | Note |
|---|---|---|---|
| 1 | Docstring `register_tools()` | ✅ Valida | Nessuna modifica al piano |
| 2 | Cache file tracking | ✅ Valida | Nessuna modifica al piano |
| 3 | README scf-registry | ✅ Valida | Nessuna modifica al piano |
| 4 | Validazione schema workflow | ✅ Valida | Osservazione: `beta` non documentato nel README schema |
| 5 | Rename docs_manager | ⚠️ Integrata | **Aggiunto:** aggiornamento frontmatter `name:` nel file skill |
| 6 | `.gitignore` scripts/*.out | ❌ Rimossa | Già presente nel `.gitignore` |
