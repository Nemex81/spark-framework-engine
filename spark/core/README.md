# spark/core/ — Fondamenta del Motore

Questo package contiene i mattoni fondamentali del motore SPARK:
costanti immutabili, modelli di dati, e utility condivise.

**Zero dipendenze interne** — nessun modulo di `core/` importa
da altri package `spark.*`. Tutti gli altri package dipendono da `core/`.

---

## File

### `constants.py` — Costanti immutabili

Tutte le costanti del motore sono definite qui. Nessuna logica.

| Costante | Valore | Descrizione |
|----------|--------|-------------|
| `ENGINE_VERSION` | `"3.3.0"` | Versione semantica del motore |
| `_MANIFEST_FILENAME` | `".scf-manifest.json"` | Nome file manifest workspace |
| `_MANIFEST_SCHEMA_VERSION` | `"3.0"` | Schema versione corrente |
| `_SUPPORTED_MANIFEST_SCHEMA_VERSIONS` | `{"1.0","2.0","2.1","3.0"}` | Versioni accettate in lettura |
| `_BOOTSTRAP_PACKAGE_ID` | `"scf-engine-bootstrap"` | Owner placeholder per file Cat.A |
| `_REGISTRY_URL` | `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json` | Registry pubblico SCF |
| `_RESOURCE_TYPES` | `("agents","prompts","skills","instructions")` | Tipi URI resource riconosciuti |
| `_ALLOWED_UPDATE_MODES` | `{"ask","integrative","replace","conservative","selective"}` | Strategie di merge valide |
| `_CHANGELOGS_SUBDIR` | `"changelogs"` | Sottodirectory changelog nello store |
| `_SNAPSHOTS_SUBDIR` | `"snapshots"` | Sottodirectory snapshot |
| `_MERGE_SESSIONS_SUBDIR` | `"merge-sessions"` | Sottodirectory sessioni merge |
| `_BACKUPS_SUBDIR` | `"backups"` | Sottodirectory backup |

---

### `models.py` — Dataclass di dominio

Modelli immutabili condivisi in tutto il motore.

**`WorkspaceContext`** — contesto di un workspace attivo:
- `workspace_root: Path` — radice del progetto utente
- `github_root: Path` — `{workspace_root}/.github/`
- `engine_root: Path` — directory del motore SPARK

**`FrameworkFile`** — file SCF scoperto:
- `name: str`, `path: Path`, `category: str`, `summary: str`, `metadata: dict`

**`MergeConflict`** — conflitto in una sessione 3-way merge:
- `start_line: int`, `end_line: int`, `base_text: str`, `ours_text: str`, `theirs_text: str`

**`MergeResult`** — risultato di un'operazione merge:
- `status: str` — `MERGE_STATUS_IDENTICAL | MERGE_STATUS_CLEAN | MERGE_STATUS_CONFLICT`
- `merged_text: str`, `conflicts: list[MergeConflict]`, `sections: list`

Costanti status merge (definite in `models.py`):
- `MERGE_STATUS_IDENTICAL = "identical"`
- `MERGE_STATUS_CLEAN = "clean"`
- `MERGE_STATUS_CONFLICT = "conflict"`

---

### `utils.py` — Utility condivise

Funzioni helper senza effetti collaterali, usate da più package:
hashing, normalizzazione path, lettura sicura JSON, formattazione output.
