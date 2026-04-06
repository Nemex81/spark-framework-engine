# Piano Correttivo — Diagnostica SPARK 2026-04-06

Generato da: analisi diagnostica del 6 aprile 2026  
Ambito: `spark-framework-engine` (motore MCP)  
Stato: **IMPLEMENTATO — IN ATTESA PUSH REMOTO**

---

## Riepilogo anomalie rilevate

| ID | Priorità | Descrizione |
|----|----------|-------------|
| A1 | CRITICA  | Tag git `v1.4.1` assente localmente; `v1.4.0` non pushato al remoto |
| A2 | MEDIA    | `README.md` dichiara 22 tool invece di 23; `scf_verify_system` non elencato |
| A3 | MEDIA    | `CHANGELOG.md` — formato date incoerente (ISO per 1.4.x, italiano per 1.3.x e precedenti) |
| A4 | BASSA    | `.github/.scf-registry-cache.json` presente nel worktree (già gitignored, non tracciato) |
| A5 | BASSA    | `mypy` non eseguibile nell'ambiente (DLL blocked da policy Windows — no code fix) |

---

## Strategia correttiva

### A1 — Tag git mancanti

- Creare tag `v1.4.1` localmente sul commit corrente HEAD (`592a062`) **prima** di qualsiasi modifica  
- Le modifiche di questo piano produrranno un nuovo commit → nuovo tag `v1.4.2`  
- Pushare i tag `v1.4.0`, `v1.4.1`, `v1.4.2` al remoto (**richiede conferma utente** — operazione di push)

### A2 — README tool count + voce mancante

- Sostituire `## Tools Disponibili (22)` → `## Tools Disponibili (23)`  
- Aggiungere `scf_verify_system()` alla lista tool, subito dopo `scf_verify_workspace()`

### A3 — Normalizzazione date CHANGELOG

Conversioni da applicare a tutte le voci `## [x.y.z]`:

| Da (italiano) | A (ISO 8601) |
|---------------|-------------|
| `2 aprile 2026` | `2026-04-02` |
| `31 marzo 2026` | `2026-03-31` |
| `30 marzo 2026` | `2026-03-30` |
| `20 febbraio 2026` | `2026-02-20` |

### A4 — Cache file nel worktree

Nessuna azione necessaria. Il file è in `.gitignore` e non è tracciato da git.  
È un artefatto runtime normale del `RegistryClient`.

### A5 — mypy DLL failure

Nessuna azione sul codice. Il problema è ambientale (Windows application control policy).  
Raccomandazione: usare un ambiente virtuale su Python non soggetto alla policy,  
o verificare con `ruff` (già funzionante, 0 violations).

---

## Piano implementazione

### Step 1 — Tag v1.4.1 (locale, pre-modifica)

```
git tag v1.4.1          # sulla HEAD corrente (592a062)
```

Sicuro: operazione locale reversibile (`git tag -d v1.4.1` per annullare).

### Step 2 — Fix README.md

File: `README.md`  
Modifica 1: `## Tools Disponibili (22)` → `## Tools Disponibili (23)`  
Modifica 2: aggiungere riga `scf_verify_system()` dopo `scf_verify_workspace()`

### Step 3 — Normalizza date CHANGELOG.md

File: `CHANGELOG.md`  
Sostituire tutte le date in formato italiano nelle voci `## [x.y.z]` con formato ISO 8601.

### Step 4 — Bump ENGINE_VERSION + nuova voce CHANGELOG

File: `spark-framework-engine.py`  
`ENGINE_VERSION: str = "1.4.1"` → `ENGINE_VERSION: str = "1.4.2"`

File: `CHANGELOG.md`  
Inserire nuova voce in cima (dopo le righe di intestazione):

```markdown
## [1.4.2] — 2026-04-06

### Fixed
- **README.md**: corretto conteggio tool da 22 a 23; aggiunto `scf_verify_system` nella lista.
- **CHANGELOG.md**: normalizzate le date delle versioni precedenti al formato ISO 8601 (YYYY-MM-DD).
```

### Step 5 — Validazione post-modifica

Eseguire:
```
pytest tests/test_engine_coherence.py -v   # verifica allineamento ENGINE_VERSION/CHANGELOG e contatori
ruff check spark-framework-engine.py       # zero violations
```

Criteri di superamento:
- `test_engine_version_changelog_alignment` PASSED → ENGINE_VERSION = primo entry CHANGELOG
- `test_tool_counter_consistency` PASSED → contatori allineati
- ruff: 0 errori

### Step 6 — Commit e tag v1.4.2 (locale)

```
git add README.md CHANGELOG.md spark-framework-engine.py
git commit -m "docs: fix README tool count 22→23, add scf_verify_system, normalize CHANGELOG dates, v1.4.2"
git tag v1.4.2
```

### Step 7 — Push tag e branch (RICHIEDE CONFERMA UTENTE)

```
git push origin main
git push origin v1.4.0 v1.4.1 v1.4.2
```

**BLOCCO**: step 7 non verrà eseguito automaticamente. Richiede conferma esplicita.

---

## Criteri di validazione del piano

Questo piano supera la convalida se:

1. ✅ Tutte le modifiche sono locali e reversibili (eccetto step 7 che è flaggato)
2. ✅ Nessuna rottura API MCP (solo modifiche a docs e version string)
3. ✅ `test_engine_version_changelog_alignment` verificabile: ENGINE_VERSION 1.4.2 = `## [1.4.2]` in CHANGELOG
4. ✅ `test_tool_counter_consistency` non impattato (non modifica il contatore dei decorator `@self._mcp.tool(`)
5. ✅ `ruff` non impattato (modifiche solo a file .md e version string)
6. ✅ La voce CHANGELOG per v1.4.2 copre tutte le modifiche applicate
7. ✅ Il tag v1.4.1 viene creato prima delle modifiche (retroattivo corretto)
8. ✅ Il tag v1.4.2 viene creato dopo il commit delle modifiche

**Esito atteso: VALIDO — implementazione automatica autorizzata per step 1–6.**

---

## Stato esecuzione

- [x] Step 1 — Crea tag v1.4.1 (commit 592a062)
- [x] Step 2 — Fix README.md
- [x] Step 3 — Normalizza date CHANGELOG
- [x] Step 4 — Bump ENGINE_VERSION + nuova voce CHANGELOG [1.4.2]
- [x] Step 5 — Validazione post-modifica (2/2 test passed, ruff 0 violations)
- [x] Step 6 — Commit 22f76e5 e tag v1.4.2
- [ ] Step 7 — Push (IN ATTESA CONFERMA UTENTE)
