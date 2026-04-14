# SCF 3-Way Merge System — Piano Implementativo

**Versione documento**: 1.0.0
**Data**: 2026-04-14
**Stato**: Approvato per implementazione
**Target engine**: spark-framework-engine 2.0.0
**Documento di design di riferimento**: `docs/SCF-3WAY-MERGE-DESIGN.md`
**Autore**: spark-engine-maintainer

---

## Indice

1. Panoramica progetto
2. Fasi implementative
3. Dettaglio tecnico per fase
4. Matrice delle dipendenze tra fasi
5. Test strategy
6. Rischi e mitigazioni
7. Metriche di successo
8. Migration path

---

## 1. Panoramica progetto

### 1.1 Obiettivi

Il sistema di 3-way merge per SCF risolve il gap critico identificato nell'audit del 2026-04-13: i file classificati `preserve_tracked_modified` vengono saltati in silenzio durante gli aggiornamenti, causando la perdita silenziosa delle nuove versioni ufficiali dei template nei workspace con personalizzazioni utente.

L'obiettivo primario è introdurre una terza via tra "sovrascrivere" e "saltare": **unire** le modifiche dell'utente con quelle del pacchetto, usando uno snapshot BASE come antenato comune del merge a 3 vie.

**Obiettivi secondari**:

- Mantenere backward compatibility completa: `conflict_mode="abort"` e `conflict_mode="replace"` continuano a funzionare invariati.
- Zero dipendenze esterne: solo stdlib Python (`difflib`, `uuid`, `shutil`, `pathlib`, `dataclasses`).
- Audit trail completo: ogni sessione di merge è serializzata su disco.
- Accessibilità NVDA: output testuale ASCII, nessun HTML embedded, report strutturati.

### 1.2 Prerequisiti tecnici verificati

| Prerequisito | Versione / Stato | Necessario da |
|---|---|---|
| Python stdlib `difflib` | disponibile (Python 3.11+) | Fase 1 |
| Python stdlib `uuid` | disponibile | Fase 3 |
| Python stdlib `shutil` | disponibile | Fase 0 |
| `dataclasses` (Python 3.7+) | disponibile | Fase 1 |
| ENGINE_VERSION attuale | 1.9.0 | Fase 7 (bump a 2.0.0) |
| Test suite baseline | 84 test + 12 subtest | Tutte le fasi |
| `spark-framework-engine.py` | ~2420 righe, 29 tool, 15 risorse | Tutte le fasi |

### 1.3 Vincoli architetturali non negoziabili

1. `MergeEngine` deve essere una classe pura Python senza effetti collaterali su disco, senza import MCP e senza riferimenti a `SparkFrameworkEngine`.
2. Gli snapshot BASE risiedono in `.github/runtime/snapshots/<package-id>/<file-rel>` (percorso deterministico, non nel manifest).
3. Le sessioni merge risiedono in `.github/runtime/merge-sessions/<session-id>.json`.
4. Il formato del manifest `.github/.scf-manifest.json` (schema 1.0) non viene alterato.
5. Le modalità `abort` e `replace` devono superare i test di non-regressione esistenti senza modifiche.
6. I validator post-merge sono funzioni pure, non classi con stato.
7. Il tool log `Tools registered: N total` (riga 2407 del sorgente attuale) deve essere aggiornato dopo ogni aggiunta di tool.
8. La prima voce di `CHANGELOG.md` deve corrispondere a `ENGINE_VERSION` per invariante di `test_engine_coherence.py`.

### 1.4 Dipendenze tra deliverable

```
Fase 0 (Snapshot)  ───────────────────────────────────────┐
                                                           ├──▶ Fase 2 (Install/Update)
Fase 1 (MergeEngine) ──────────────────────────────────────┘
                                                                  │
                                                                  ▼
                                                           Fase 3 (Sessione) ──▶ Fase 4 (Auto) ──▶ Fase 5 (Assisted)
                                                                  │
                                                                  ▼
Fase 6 (Multi-owner) ◀─── Fase 2 (classify) ──────────────────────────────────────────────────────────────────────────
                                                                  │
                                                                  ▼
                                                           Fase 7 (Release)
```

**Fasi parallelizzabili**: Fase 0 e Fase 1 non hanno dipendenze tra loro e possono essere sviluppate in parallelo.
**Fase 6** dipende da Fase 2 solo per l'API `_classify_install_files`; può iniziare mentre Fase 3/4/5 sono in sviluppo.

---

## 2. Fasi implementative

### Fase 0 — Infrastruttura snapshot BASE

**Descrizione**: Implementare la classe `SnapshotManager` responsabile della persistenza degli snapshot BASE, e integrare il salvataggio automatico dello snapshot nei tool `scf_install_package` e `scf_bootstrap_workspace`.

**Deliverable**:

- Classe `SnapshotManager` con metodi CRUD completi.
- Integrazione save-snapshot in `scf_install_package` dopo ogni scrittura (righe ~1483–1733 del sorgente).
- Integrazione save-snapshot in `scf_bootstrap_workspace` dopo ogni copia file (righe ~2274–2406 del sorgente).
- Integrazione delete-snapshot in `scf_remove_package` dopo rimozione manifest (righe ~2147–2273 del sorgente).
- Test unitari per CRUD snapshot.
- Test di integrazione snapshot in install e bootstrap.

**Criterio di uscita**: i test `tests/test_snapshot_manager.py` passano tutti. `scf_install_package` su un pacchetto reale crea file sotto `.github/runtime/snapshots/`. `scf_bootstrap_workspace` crea snapshot per i file bootstrap. La suite completa non regredisce (84 test + nuovi).

---

### Fase 1 — MergeEngine core

**Descrizione**: Implementare la classe `MergeEngine` con l'algoritmo di merge a 3-vie basato su `difflib.SequenceMatcher`, i dataclass `MergeConflict` e `MergeResult`, la generazione dei marcatori per modalità `manual`, e il rilevamento dei marcatori residui.

**Deliverable**:

- Dataclass `MergeConflict` (sezione 4.2 del design).
- Dataclass `MergeResult` (sezione 4.2 del design).
- Classe `MergeEngine` con metodi:
  - `diff3_merge(base, ours, theirs) -> MergeResult`
  - `render_with_markers(result) -> str`
  - `has_conflict_markers(text) -> bool`
- Funzione helper privata `_validate_rel_path(file_rel) -> bool` (sicurezza path traversal).
- Test unitari per tutti i casi dell'algoritmo diff3.

**Criterio di uscita**: i test `tests/test_merge_engine.py` passano tutti, inclusi i casi merge clean, conflitto, identico, file vuoto, frontmatter, stesso cambio da ambo le parti. `MergeEngine` non importa nessun modulo MCP o tool engine.

---

### Fase 2 — Integrazione nel flusso install/update

**Descrizione**: Estendere `_classify_install_files` con la categoria `merge_candidate`, estendere `scf_install_package` e `scf_update_package` per supportare `conflict_mode="manual"`, e modificare il percorso `preserve_tracked_modified` per tentare il merge quando lo snapshot BASE è disponibile.

**Deliverable**:

- Nuova categoria `merge_candidate` in `_classify_install_files` (riga ~1394 del sorgente).
- Costante `SUPPORTED_CONFLICT_MODES = {"abort", "replace", "manual", "auto", "assisted"}` nel sorgente.
- Parametro `conflict_mode: str = "abort"` aggiunto a `scf_update_package` (riga ~1734).
- Parametro `conflict_mode: str = "abort"` aggiunto a `scf_install_package` (riga ~1483).
- Percorso `preserve_tracked_modified` → tentativo merge se snapshot disponibile → fallback preserve se snapshot assente.
- Nuovi campi in `_build_install_result`: `merge_clean`, `merge_conflict`, `session_id`, `session_status`, `session_expires_at`, `snapshot_written`, `snapshot_skipped` (riga ~1298).
- Test non-regressione espliciti per `abort` e `replace`.
- Test integrazione per `manual` end-to-end.

**Criterio di uscita**: `scf_update_package` con `conflict_mode="manual"` su un file modificato produce file con marcatori e ritorna `session_id`. Test `abort` e `replace` passano invariati. Test `tests/test_merge_integration.py` passano. Nessuna regressione sulla suite completa.

---

### Fase 3 — Sessione merge stateful

**Descrizione**: Implementare la classe `MergeSessionManager` per la gestione del ciclo di vita delle sessioni (create/load/update/finalize/cleanup), implementare il tool MCP `scf_finalize_update`, e aggiungere il timeout e garbage collection per sessioni scadute e orfane.

**Deliverable**:

- Classe `MergeSessionManager` con metodi: `create_session`, `load_session`, `update_session`, `finalize_session`, `cleanup_expired_sessions`, `is_session_active`.
- Schema JSON sessione completo (sezione 7.2 del design).
- Tool MCP `scf_finalize_update(session_id)` — nuovo tool, contatore tool da 29 a 30 (aggiornare commento classe e log).
- Verifica SHA `original_sha_at_session_open` in `scf_finalize_update` per rilevare modifiche esterne.
- Cleanup sessioni scadute/orfane all'avvio di `scf_update_package`, `scf_apply_updates`, `scf_finalize_update`.
- Test unitari per lifecycle sessione.

**Criterio di uscita**: `scf_finalize_update` su una sessione attiva scrive i file risolti, aggiorna manifest e snapshot, chiude la sessione con `status="finalized"`. Sessioni con `expires_at` nel passato vengono marcate `expired` al prossimo avvio tool. Test `tests/test_merge_session.py` passano tutti.

---

### Fase 4 — Modalità auto (risoluzione AI)

**Descrizione**: Implementare il tool `scf_resolve_conflict_ai`, implementare i 3 validator post-merge (`validate_structural`, `validate_completeness`, `validate_tool_coherence`, `run_post_merge_validators`), e integrare la pipeline auto nel flusso `conflict_mode="auto"`.

**Deliverable**:

- Tool MCP `scf_resolve_conflict_ai(session_id, conflict_id)` — contatore tool da 30 a 31.
- Funzioni validator pure (senza stato):
  - `validate_structural(merged_text, base_text) -> tuple[bool, str]`
  - `validate_completeness(merged_text, ours_text) -> tuple[bool, str]`
  - `validate_tool_coherence(merged_text, ours_text) -> tuple[bool, str]`
  - `run_post_merge_validators(merged_text, base_text, ours_text, file_rel) -> dict`
- Integrazione pipeline `auto` in `scf_update_package`: chiamata AI → validator → scrittura se pass, degradamento a `manual` se fail.
- Gestione `llm_unavailable` con fallback a `manual`.
- Contratto `validator_results` nel ritorno di `scf_finalize_update`.
- Test validators in isolamento e test pipeline auto end-to-end.

**Criterio di uscita**: `scf_update_package` con `conflict_mode="auto"` su file con conflitti chiama validators e scrive il risultato se tutti i check passano. Conflitti su frontmatter identici non vengono risolti automaticamente (degradano a `manual`). Test `tests/test_merge_validators.py` passano tutti.

---

### Fase 5 — Modalità assisted (approvazione utente)

**Descrizione**: Implementare i tool `scf_approve_conflict` e `scf_reject_conflict`, il flusso sessione con stato per-conflict (`pending`/`approved`/`rejected`/`manual`), e il comportamento di finalizzazione mixed (file con conflitti approvati + file con conflitti rifiutati → marcatori).

**Deliverable**:

- Tool MCP `scf_approve_conflict(session_id, conflict_id)` — contatore tool da 31 a 32.
- Tool MCP `scf_reject_conflict(session_id, conflict_id)` — contatore tool da 32 a 33.
- Campo `resolution_status` per ogni conflitto in sessione JSON: `pending`, `approved`, `rejected`, `manual`.
- Campo `proposed_lines` e `approved` in ogni conflitto nella sessione JSON.
- `scf_finalize_update` esteso: conflitti `approved` → applica proposed_lines; conflitti `rejected`/`manual` → inserisce marcatori.
- Campo `remaining_conflicts` nel ritorno di `scf_approve_conflict` e `scf_reject_conflict`.
- Test flusso assisted completo, approvazione parziale, rigetto totale.

**Criterio di uscita**: flusso `create_session → resolve_ai → approve → finalize` scrive il file risolto senza marcatori. Flusso `create_session → resolve_ai → reject → finalize` scrive il file con marcatori solo per il conflitto rifiutato. Test `tests/test_merge_assisted.py` passano tutti.

---

### Fase 6 — Policy multi-owner

**Descrizione**: Estendere il formato `package-manifest.json` con il campo `file_policies`, implementare il parsing `extend`/`delegate` in `_classify_install_files`, implementare la logica di sezione con marcatori `<!-- SCF:SECTION:<package-id>:BEGIN/END -->`.

**Deliverable**:

- Nuove categorie in `_classify_install_files`: `extend_section`, `delegate_skip`.
- Parser `file_policies` dal manifest remoto del pacchetto.
- Funzione `_update_package_section(file_path, package_id, new_content)` per aggiornare solo la sezione marcata.
- Funzione `_parse_section_markers(text, package_id) -> tuple[int, int] | None` per individuare la sezione del pacchetto nel file esistente.
- Funzione `_create_file_with_section(file_path, package_id, content)` per creare file con sola sezione quando il file non esiste.
- Regola di precedenza: policy per-file sovrascrive `file_ownership_policy` globale.
- Vincolo: policy `extend` non applicabile a file `.agent.md` (implementare guard e messaggio errore esplicito).
- Test isolati per ciascuna policy.

**Criterio di uscita**: un pacchetto con `policy: "extend"` su `.github/copilot-instructions.md` aggiorna solo la propria sezione senza toccare il contenuto utente né le sezioni di altri pacchetti. Un pacchetto con `policy: "delegate"` salta il file senza scrivere. Test `tests/test_multi_owner_policy.py` passano tutti.

---

### Fase 7 — Versioning, CHANGELOG, README, release

**Descrizione**: Bump `ENGINE_VERSION` da 1.9.0 a 2.0.0, aggiornamento CHANGELOG.md con voce versione 2.0.0, aggiornamento contatori tool (da 29 a 34: 29 + 5 nuovi) e risorse nel sorgente e nel log, aggiornamento README e marcatura `docs/ROADMAP-FASE2.md` come completata.

**Deliverable**:

- `ENGINE_VERSION = "2.0.0"` in `spark-framework-engine.py` (riga 40).
- Nuova voce `## [2.0.0] - 2026-MM-DD` in `CHANGELOG.md` come prima voce (invariante test).
- Commento classe `SparkFrameworkEngine` con `# Tools (34)` aggiornato.
- Log `Tools registered: 34 total` aggiornato (riga ~2407 del sorgente attuale).
- `README.md` aggiornato con sezione dedicata al sistema di merge e nuovi conflict_mode.
- `docs/ROADMAP-FASE2.md` aggiornato con stato "completata" per la voce "conflict_mode: merge".

**Criterio di uscita**: `test_engine_coherence.py` passa — la prima voce di `CHANGELOG.md` corrisponde a `ENGINE_VERSION`. Contatori tool allineati nel commento classe e nel log. `pytest -q` passa tutti i test senza regressioni.

---

## 3. Dettaglio tecnico per fase

### Dettaglio Fase 0 — Infrastruttura snapshot BASE

#### 3.0.1 File da creare

Nessun nuovo file Python; tutta l'implementazione va nel file esistente.

#### 3.0.2 File da modificare

**`spark-framework-engine.py`**:

- Posizionamento: inserire la classe `SnapshotManager` subito dopo `ManifestManager` (riga ~540), prima di `RegistryClient` (riga ~794).
- Integrare `SnapshotManager` in `SparkFrameworkEngine.__init__` (o nel metodo `register_tools`) come attributo `self._snapshot_mgr`.
- Modificare `scf_install_package` (riga ~1483): aggiungere passo post-`upsert_many` per salvare snapshot dei file scritti.
- Modificare `scf_bootstrap_workspace` (riga ~2274): aggiungere passo post-copia per salvare snapshot con `package_id="__bootstrap__"`.
- Modificare `scf_remove_package` (riga ~2147): aggiungere passo post-rimozione manifest per eliminare la directory snapshot del pacchetto.

#### 3.0.3 Interfaccia da implementare

```python
class SnapshotManager:
    """Gestisce gli snapshot BASE dei file installati dai pacchetti SCF."""

    BOOTSTRAP_PACKAGE_ID: str = "__bootstrap__"

    def __init__(self, snapshots_root: Path) -> None:
        """
        snapshots_root: percorso a .github/runtime/snapshots/
        """
        self._root = snapshots_root

    def _snapshot_path(self, package_id: str, file_rel: str) -> Path:
        """
        Calcola deterministicamente il percorso snapshot.
        Valida file_rel contro path traversal prima di comporre il percorso.
        Solleva ValueError se file_rel non è sicuro.
        """
        ...

    def save_snapshot(self, package_id: str, file_rel: str, content: bytes) -> Path:
        """
        Salva il contenuto come snapshot BASE.
        Crea le directory intermedie se non esistono.
        Ritorna il percorso del file snapshot scritto.
        """
        ...

    def load_snapshot(self, package_id: str, file_rel: str) -> bytes | None:
        """
        Carica il contenuto dello snapshot BASE.
        Ritorna None se lo snapshot non esiste.
        """
        ...

    def delete_snapshot(self, package_id: str, file_rel: str) -> bool:
        """
        Elimina un singolo snapshot.
        Ritorna True se il file esisteva ed è stato eliminato.
        """
        ...

    def list_snapshots(self, package_id: str) -> list[str]:
        """
        Elenca i percorsi relativi di tutti gli snapshot per un pacchetto.
        Ritorna lista vuota se la directory non esiste.
        """
        ...

    def delete_all_snapshots(self, package_id: str) -> int:
        """
        Elimina l'intera directory snapshot per un pacchetto.
        Ritorna il numero di file eliminati.
        """
        ...

    def snapshot_exists(self, package_id: str, file_rel: str) -> bool:
        """Ritorna True se lo snapshot esiste sul filesystem."""
        ...
```

**Integrazione in `scf_install_package`** (pseudo-diff):

```python
# Dopo upsert_many(...) -- riga ~1700 circa
snapshot_written: list[str] = []
snapshot_skipped: list[str] = []
for file_rel, dest_path in written_files:
    try:
        raw = dest_path.read_bytes()
        raw.decode("utf-8", errors="strict")  # skip binari
        self._snapshot_mgr.save_snapshot(package_id, file_rel, raw)
        snapshot_written.append(file_rel)
    except (UnicodeDecodeError, ValueError):
        snapshot_skipped.append(file_rel)
```

**Integrazione in `scf_remove_package`** (pseudo-diff):

```python
# Dopo rimozione manifest -- riga ~2230 circa
count_deleted = self._snapshot_mgr.delete_all_snapshots(package_id)
_log.info("Snapshot rimossi per %s: %d file", package_id, count_deleted)
```

#### 3.0.4 Test da scrivere

File: `tests/test_snapshot_manager.py`

Nome test e scopo:

| Test | Scopo |
|---|---|
| `test_save_and_load_roundtrip` | save + load ritorna contenuto identico |
| `test_save_creates_directories` | crea directory intermedie automaticamente |
| `test_load_missing_returns_none` | load su snapshot assente ritorna None |
| `test_delete_existing_returns_true` | delete ritorna True se file esisteva |
| `test_delete_missing_returns_false` | delete ritorna False se file assente |
| `test_list_snapshots_empty_dir` | lista vuota se directory non esiste |
| `test_list_snapshots_returns_all_files` | lista tutti i file ricorsivamente |
| `test_delete_all_returns_count` | delete_all ritorna il conteggio corretto |
| `test_path_traversal_rejected` | `../` in file_rel solleva ValueError |
| `test_absolute_path_rejected` | percorso assoluto in file_rel solleva ValueError |
| `test_snapshot_exists_true_and_false` | snapshot_exists risponde correttamente |
| `test_bootstrap_package_id_accepted` | `__bootstrap__` è un package_id valido |

#### 3.0.5 Complessità relativa

**Media.** La logica è semplice (I/O filesystem), ma l'integrazione negli strumenti esistenti richiede attenzione ai percorsi di rollback e ai test di non-regressione.

---

### Dettaglio Fase 1 — MergeEngine core

#### 3.1.1 File da creare

Nessun nuovo file Python; tutta l'implementazione va nel file esistente.

#### 3.1.2 File da modificare

**`spark-framework-engine.py`**:

- Aggiungere gli import necessari nella sezione import iniziale: `from dataclasses import dataclass, field`, `from typing import Literal` (verificare se già presenti), `from difflib import SequenceMatcher`, `import uuid`.
- Inserire `MergeStatus`, `MergeConflict`, `MergeResult` come dataclass a livello di modulo, dopo `SnapshotManager` e prima di `RegistryClient`.
- Inserire `MergeEngine` come classe a livello di modulo, dopo i dataclass.
- Inserire la funzione helper `_validate_rel_path(file_rel: str) -> bool` a livello di modulo.

#### 3.1.3 Interfaccia da implementare

```python
from dataclasses import dataclass, field
from typing import Literal
from difflib import SequenceMatcher

MergeStatus = Literal["clean", "conflict", "identical", "binary_skip"]


@dataclass
class MergeConflict:
    """Rappresenta un singolo conflitto non risolvibile automaticamente."""
    conflict_id: str
    start_line: int
    end_line: int
    base_lines: list[str]
    ours_lines: list[str]
    theirs_lines: list[str]
    context_before: list[str]
    context_after: list[str]
    resolution_status: str = "pending"  # pending | approved | rejected | manual
    proposed_lines: list[str] | None = None
    approved: bool | None = None


@dataclass
class MergeResult:
    """Risultato di un merge a 3-via per un singolo file."""
    status: MergeStatus
    merged_lines: list[str]
    conflicts: list[MergeConflict] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    # stats: total_lines, clean_sections, conflict_count, identical_sections
    base_unavailable: bool = False  # True se BASE era assente (merge degradato)


class MergeEngine:
    """Motore di merge a 3-via puro. Nessun I/O. Nessuna dipendenza MCP."""

    BASE_MARKER = "<<<<<<< YOURS"
    SEP_MARKER = "======="
    THEIR_MARKER = ">>>>>>> OFFICIAL"
    CONTEXT_LINES = 3

    def diff3_merge(
        self,
        base: str,
        ours: str,
        theirs: str,
    ) -> MergeResult:
        """
        Calcola il merge a 3-via tra base, ours e theirs.

        Algoritmo:
          1. Calcola delta_ours = diff(base, ours) via SequenceMatcher.
          2. Calcola delta_theirs = diff(base, theirs) via SequenceMatcher.
          3. Interseca i range di BASE toccati dai due delta.
          4. Costruisce il risultato per ciascuna sezione:
             - Solo OURS cambia → applica OURS
             - Solo THEIRS cambia → applica THEIRS
             - Entrambi identici → applica una sola volta (merge pulito)
             - Entrambi diversi sullo stesso range → CONFLITTO
             - Nessuno cambia → copia BASE
          5. Assegna status: identical | clean | conflict.

        Ritorna MergeResult con tutti i blocchi e i conflitti.
        Non modifica alcun file su disco.
        """
        ...

    def render_with_markers(self, result: MergeResult) -> str:
        """
        Produce il testo completo del file con marcatori di conflitto inseriti.

        Formato marcatori:
            <<<<<<< YOURS
            ... righe utente ...
            =======
            ... righe ufficiali pacchetto ...
            >>>>>>> OFFICIAL

        Le sezioni non in conflitto vengono scritte senza marcatori.
        """
        ...

    def has_conflict_markers(self, text: str) -> bool:
        """
        Ritorna True se il testo contiene marcatori di conflitto non risolti.
        Controlla la presenza di BASE_MARKER, SEP_MARKER, THEIR_MARKER.
        """
        ...

    def _build_conflict_id(self) -> str:
        """Genera un UUID v4 stabile per un conflitto."""
        return str(uuid.uuid4())

    def _extract_context(
        self,
        lines: list[str],
        start: int,
        end: int,
    ) -> tuple[list[str], list[str]]:
        """
        Estrae CONTEXT_LINES righe prima di start e dopo end.
        Usato per popolare context_before e context_after di MergeConflict.
        """
        ...

    def _is_frontmatter_region(self, lines: list[str], start: int, end: int) -> bool:
        """
        Ritorna True se le righe [start, end] rientrano nel blocco frontmatter YAML
        (tra il primo --- e il secondo ---).
        """
        ...
```

**Algoritmo `diff3_merge` — fasi interne** (da implementare nel corpo del metodo):

```python
# Fase 1: calcola opcode entrambii diff
def _get_opcodes(a_lines, b_lines):
    return SequenceMatcher(None, a_lines, b_lines).get_opcodes()

ours_ops = _get_opcodes(base_lines, ours_lines)
theirs_ops = _get_opcodes(base_lines, theirs_lines)

# Fase 2: costruisce mappa range BASE → operazione per OURS e THEIRS
# Fase 3: itera sui range BASE in ordine, classifica e costruisce output
# Fase 4: se status == conflict e regione è frontmatter → forza conflict
#          indipendentemente da conflict_mode (gestito dal chiamante)
# Fase 5: calcola stats e assegna status finale
```

#### 3.1.4 Test da scrivere

File: `tests/test_merge_engine.py`

| Test | Scopo |
|---|---|
| `test_identical_files_returns_identical` | BASE=OURS=THEIRS → status=identical |
| `test_only_ours_changes_returns_clean` | solo OURS modifica → status=clean, contenuto OURS |
| `test_only_theirs_changes_returns_clean` | solo THEIRS modifica → status=clean, contenuto THEIRS |
| `test_same_change_both_returns_clean` | stessa modifica in OURS e THEIRS → una sola versione nel risultato |
| `test_different_sections_both_change_clean` | OURS e THEIRS modificano sezioni diverse → merge pulito |
| `test_same_section_both_different_conflict` | stesso blocco modificato diversamente → status=conflict |
| `test_conflict_has_correct_lines` | `MergeConflict.base_lines`, `ours_lines`, `theirs_lines` corretti |
| `test_conflict_has_context` | `context_before`/`context_after` max 3 righe |
| `test_conflict_id_is_uuid` | `conflict_id` è un UUID v4 valido |
| `test_empty_base_empty_ours_empty_theirs` | tre file vuoti → status=identical |
| `test_empty_base_nonempty_ours` | BASE vuoto, OURS con contenuto → status=clean |
| `test_empty_theirs_nonempty_base` | THEIRS vuoto (file rimosso) → status=clean/conflict |
| `test_frontmatter_only_ours_changes_clean` | OURS modifica campo frontmatter, THEIRS no → clean |
| `test_frontmatter_both_change_same_field_conflict` | entrambi modificano stesso campo → conflict |
| `test_frontmatter_theirs_adds_new_field_clean` | THEIRS aggiunge campo assente in OURS → clean |
| `test_render_with_markers_contains_all_markers` | render include tutti e tre i marcatori |
| `test_render_with_markers_clean_result_no_markers` | merge clean → nessun marcatore nel testo |
| `test_has_conflict_markers_detected` | testo con `<<<<<<<` → True |
| `test_has_conflict_markers_not_found` | testo pulito → False |
| `test_stats_populated` | `stats` contiene `total_lines`, `conflict_count`, ecc. |
| `test_merge_engine_no_mcp_import` | `MergeEngine` non importa moduli MCP (verifica con inspect) |

#### 3.1.5 Complessità relativa

**Alta.** L'algoritmo `diff3_merge` è l'implementazione centrale dell'intero sistema. L'uso di `SequenceMatcher` come primitiva per un diff3 custom introduce complessità di test elevata. I casi edge (file vuoti, solo frontmatter, stessa modifica da ambo le parti) richiedono cura specifica.

---

### Dettaglio Fase 2 — Integrazione nel flusso install/update

#### 3.2.1 File da creare

Nessun nuovo file Python.

#### 3.2.2 File da modificare

**`spark-framework-engine.py`**:

- `_classify_install_files` (riga ~1394): aggiungere categoria `merge_candidate` per file `preserve_tracked_modified` + snapshot disponibile; aggiungere categoria `merge_candidate_no_base` per `preserve_tracked_modified` senza snapshot.
- `scf_install_package` (riga ~1483): aggiungere parametro `conflict_mode: str = "abort"`, validazione del valore, e percorso merge per `merge_candidate`.
- `scf_update_package` (riga ~1734): stesso parametro `conflict_mode`, stessa validazione, stesso percorso merge.
- `_build_install_result` (riga ~1298): aggiungere nuovi campi nel dict di ritorno.
- Costante di modulo `SUPPORTED_CONFLICT_MODES: frozenset[str]`.

#### 3.2.3 Interfacce/funzioni da implementare

```python
# Costante a livello di modulo
SUPPORTED_CONFLICT_MODES: frozenset[str] = frozenset({
    "abort", "replace", "manual", "auto", "assisted"
})


def _validate_conflict_mode(conflict_mode: str, package_id: str) -> dict[str, Any] | None:
    """
    Verifica che conflict_mode sia un valore supportato.
    Ritorna None se valido, oppure un dict errore (da ritornare direttamente) se non valido.
    """
    if conflict_mode not in SUPPORTED_CONFLICT_MODES:
        return _build_install_result(
            False,
            error=(
                f"conflict_mode '{conflict_mode}' non supportato. "
                f"Valori accettati: {', '.join(sorted(SUPPORTED_CONFLICT_MODES))}."
            ),
            package=package_id,
            conflict_mode=conflict_mode,
        )
    return None


# Percorso merge in scf_install_package / scf_update_package:
# (pseudocodice da implementare nel corpo del tool)

async def _handle_merge_candidate(
    self,
    file_rel: str,
    package_id: str,
    dest_path: Path,
    new_content: bytes,
    conflict_mode: str,
    session_id: str | None,
) -> dict[str, Any]:
    """
    Gestisce un singolo file merge_candidate.
    Ritorna un dict con: action (merged_clean|merged_conflict|preserved), session_id.
    """
    base_bytes = self._snapshot_mgr.load_snapshot(package_id, file_rel)
    if base_bytes is None:
        # Snapshot assente: fallback a preserve (migration path)
        return {"action": "preserved", "base_unavailable": True, "file_rel": file_rel}

    try:
        base_text = base_bytes.decode("utf-8")
        ours_text = dest_path.read_text(encoding="utf-8")
        theirs_text = new_content.decode("utf-8")
    except UnicodeDecodeError:
        return {"action": "preserved", "reason": "binary_skip", "file_rel": file_rel}

    engine = MergeEngine()
    result = engine.diff3_merge(base_text, ours_text, theirs_text)

    if result.status == "identical":
        return {"action": "identical", "file_rel": file_rel}

    if result.status == "clean":
        # Scrivi direttamente
        dest_path.write_text("".join(result.merged_lines), encoding="utf-8")
        self._snapshot_mgr.save_snapshot(package_id, file_rel, dest_path.read_bytes())
        return {"action": "merged_clean", "file_rel": file_rel}

    # status == "conflict"
    if conflict_mode == "manual":
        marked = engine.render_with_markers(result)
        dest_path.write_text(marked, encoding="utf-8")
        # La sessione viene creata/aggiornata dal chiamante
        return {"action": "merged_conflict", "file_rel": file_rel, "conflicts": result.conflicts}

    # conflict_mode == "auto" o "assisted": gestito dalle Fasi 4 e 5
    ...
```

#### 3.2.4 Test da scrivere

File: `tests/test_merge_integration.py`

| Test | Scopo |
|---|---|
| `test_abort_mode_preserves_modified_file` | abort con file modificato → file invariato (non-regressione) |
| `test_replace_mode_overwrites_modified_file` | replace con file modificato → sovrascrittura (non-regressione) |
| `test_manual_mode_clean_merge_writes_file` | merge clean in manual → file scritto, nessuna sessione |
| `test_manual_mode_conflict_creates_session` | merge conflict in manual → file con marcatori, session_id nel ritorno |
| `test_manual_mode_returns_session_id` | ritorno contiene `session_id` non-None |
| `test_no_snapshot_falls_back_to_preserve` | snapshot assente → file preservato, `base_unavailable: True` |
| `test_update_tracked_clean_still_overwrites` | file non modificato → sovrascrittura normale (non-regressione) |
| `test_create_new_still_creates` | file non esistente → creazione normale (non-regressione) |
| `test_unsupported_conflict_mode_returns_error` | mode sconosciuto → success False, messaggio errore |
| `test_binary_file_skipped_in_merge` | file binario → preserved, non viene aperto come testo |
| `test_identical_merge_no_write` | OURS == THEIRS == BASE → nessuna scrittura su disco |
| `test_new_fields_in_result_dict` | ritorno include `snapshot_written`, `merge_clean`, ecc. |

#### 3.2.5 Complessità relativa

**Alta.** Questa fase tocca la logica centrale di install/update che ha molti percorsi di esecuzione e storicamente ha avuto bug di rollback. Il rischio di regressione è elevato. Richiede test di non-regressione espliciti e dettagliati.

---

### Dettaglio Fase 3 — Sessione merge stateful

#### 3.3.1 File da creare

Nessun nuovo file Python (MergeSessionManager va nel sorgente principale).

#### 3.3.2 File da modificare

**`spark-framework-engine.py`**:

- Inserire `MergeSessionManager` dopo `MergeEngine` e prima di `SparkFrameworkEngine` (riga ~906).
- Aggiungere `self._session_mgr` come attributo di `SparkFrameworkEngine`.
- Aggiungere tool MCP `scf_finalize_update` in `register_tools()`.
- Aggiornare commento classe da `# Tools (29)` a `# Tools (30)`.
- Aggiornare log `Tools registered: 30 total`.
- Aggiungere chiamata a `self._session_mgr.cleanup_expired_sessions()` all'inizio di `scf_update_package`, `scf_apply_updates` e nel nuovo `scf_finalize_update`.

#### 3.3.3 Interfaccia da implementare

```python
class MergeSessionManager:
    """Gestisce il ciclo di vita delle sessioni di merge stateful."""

    SESSION_TIMEOUT_MINUTES: int = 60
    SESSION_STATES: frozenset[str] = frozenset({
        "active", "auto_completed", "finalized", "expired", "orphaned"
    })

    def __init__(self, sessions_root: Path) -> None:
        """
        sessions_root: percorso a .github/runtime/merge-sessions/
        """
        self._root = sessions_root

    def create_session(
        self,
        package_id: str,
        target_version: str,
        conflict_mode: str,
        files: list[dict[str, Any]],
        clean_files_written: list[str],
    ) -> str:
        """
        Crea una nuova sessione di merge.
        Verifica che non esistano sessioni attive per lo stesso package_id.
        Ritorna il session_id (UUID v4).
        """
        ...

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """
        Carica una sessione dal disco.
        Ritorna None se non trovata.
        """
        ...

    def update_session(self, session_id: str, patch: dict[str, Any]) -> bool:
        """
        Aggiorna campi specifici di una sessione esistente.
        Ritorna True se aggiornata, False se sessione non trovata.
        Usa scrittura atomica (scrivi su file temporaneo, poi rinomina).
        """
        ...

    def finalize_session(self, session_id: str) -> bool:
        """
        Imposta status="finalized" e finalized_at=<timestamp ISO 8601>.
        Ritorna True se riuscito.
        """
        ...

    def is_session_active(self, session_id: str) -> bool:
        """
        Ritorna True se la sessione esiste e ha status="active".
        """
        ...

    def has_active_session_for_package(self, package_id: str) -> str | None:
        """
        Ritorna il session_id della sessione attiva per il pacchetto, o None se assente.
        """
        ...

    def cleanup_expired_sessions(self) -> list[str]:
        """
        Segna come "expired" tutte le sessioni active con expires_at nel passato.
        Segna come "orphaned" tutte le sessioni active con finalized_at=null e expires_at passato.
        Non elimina i file JSON.
        Ritorna lista di session_id modificati.
        """
        ...

    def _session_path(self, session_id: str) -> Path:
        """Calcola il percorso del file JSON della sessione."""
        return self._root / f"{session_id}.json"

    def _atomic_write_json(self, path: Path, data: dict[str, Any]) -> None:
        """
        Scrive il JSON su file temporaneo nella stessa directory, poi rinomina.
        Garantisce che il file non sia mai in stato parzialmente scritto.
        """
        ...
```

**Schema JSON della sessione** (costante o docstring nel codice):

```json
{
  "session_id": "UUID v4",
  "package_id": "scf-master-codecrafter",
  "target_version": "1.1.0",
  "conflict_mode": "manual",
  "created_at": "ISO 8601",
  "expires_at": "ISO 8601 (created_at + 60 min)",
  "status": "active",
  "files": [
    {
      "file_rel": "agents/spark-guide.agent.md",
      "base_snapshot_path": "runtime/snapshots/.../spark-guide.agent.md",
      "original_sha_at_session_open": "sha256hex",
      "merge_status": "conflict",
      "conflicts": [
        {
          "conflict_id": "UUID v4",
          "start_line": 0,
          "end_line": 0,
          "base_lines": [],
          "ours_lines": [],
          "theirs_lines": [],
          "context_before": [],
          "context_after": [],
          "resolution_status": "pending",
          "proposed_lines": null,
          "approved": null
        }
      ]
    }
  ],
  "clean_files_written": [],
  "finalized_at": null
}
```

**Tool MCP `scf_finalize_update`**:

```python
@mcp.tool()
async def scf_finalize_update(session_id: str) -> dict[str, Any]:
    """
    Finalizza una sessione di merge e scrive i file risolti su disco.

    Verifica SHA di ogni file per rilevare modifiche esterne alla sessione.
    Per conflitti approvati: scrive il buffer risolto.
    Per conflitti rifiutati/manual: scrive con marcatori di conflitto.
    Aggiorna manifest e snapshot per ogni file scritto con successo.
    Chiude la sessione con status="finalized".
    """
```

#### 3.3.4 Test da scrivere

File: `tests/test_merge_session.py`

| Test | Scopo |
|---|---|
| `test_create_session_returns_uuid` | session_id è UUID valido |
| `test_create_session_writes_json_file` | file JSON creato nel percorso corretto |
| `test_load_session_reads_created_session` | load della sessione appena creata |
| `test_load_session_missing_returns_none` | load su ID inesistente ritorna None |
| `test_update_session_modifies_field` | update modifica un campo e persiste |
| `test_update_session_uses_atomic_write` | scrittura non lascia file parziali |
| `test_finalize_session_sets_status` | finalize imposta status=finalized |
| `test_finalize_session_sets_timestamp` | finalize imposta finalized_at non-null |
| `test_is_session_active_true` | sessione appena creata è active |
| `test_is_session_active_false_after_finalize` | sessione finalizzata non è active |
| `test_no_two_active_sessions_same_package` | seconda create per stesso package solleva errore |
| `test_cleanup_marks_expired` | sessione con expires_at passato → expired |
| `test_cleanup_marks_orphaned` | sessione active con expires_at passato e finalized_at null → orphaned |
| `test_cleanup_returns_modified_ids` | cleanup ritorna lista dei session_id modificati |
| `test_finalize_tool_writes_file` | scf_finalize_update scrive il file risolto |
| `test_finalize_tool_updates_manifest` | scf_finalize_update aggiorna SHA nel manifest |
| `test_finalize_tool_external_modification_detected` | SHA cambiato → external_modification_detected |
| `test_session_expires_at_60_minutes_from_created_at` | expires_at = created_at + 60 min |

#### 3.3.5 Complessità relativa

**Media.** La struttura dati è definita, il ciclo di vita è chiaro. La complessità principale è nella gestione delle sessioni concorrenti e nell'atomicità delle scritture JSON.

---

### Dettaglio Fase 4 — Modalità auto (AI)

#### 3.4.1 File da creare

Nessun nuovo file Python.

#### 3.4.2 File da modificare

**`spark-framework-engine.py`**:

- Aggiungere funzioni validator pure a livello di modulo (prima di `SparkFrameworkEngine`): `validate_structural`, `validate_completeness`, `validate_tool_coherence`, `run_post_merge_validators`.
- Aggiungere tool MCP `scf_resolve_conflict_ai` in `register_tools()`.
- Aggiornare contatore `# Tools (31)` e log `Tools registered: 31 total`.
- Estendere `scf_update_package` per gestire `conflict_mode="auto"`.
- Estendere `scf_finalize_update` per includere `validator_results` nel ritorno.

#### 3.4.3 Interfacce/funzioni da implementare

```python
def validate_structural(merged_text: str, base_text: str) -> tuple[bool, str]:
    """
    Check 1: struttura Markdown valida, frontmatter intatto, nessun marcatore conflitto.

    Regole verificate:
    - Se base_text inizia con '---', merged_text deve iniziare con '---'.
    - Il blocco '---' frontmatter deve chiudersi con un secondo '---'.
    - Non devono esserci marcatori '<<<<<<<', '=======', '>>>>>>>' nel testo.
    - Se base_text contiene almeno un heading '#', merged_text non deve avere zero heading.

    Ritorna (True, "") se ok, (False, "descrizione") se fallisce.
    Implementazione: regex puro, nessuna libreria YAML.
    """
    ...


def validate_completeness(merged_text: str, ours_text: str) -> tuple[bool, str]:
    """
    Check 2: tutti gli H1/H2 del testo utente (OURS) sono presenti nel risultato.

    Implementazione: estrae heading con regex r'^#{1,2}\s+(.+)$',
    costruisce set di titoli normalizzati, verifica sottoinsieme.
    Heading presenti in THEIRS ma non in OURS sono accettati nel risultato.

    Ritorna (True, "") se ok, (False, "heading mancanti: ...") se fallisce.
    """
    ...


def validate_tool_coherence(merged_text: str, ours_text: str) -> tuple[bool, str]:
    """
    Check 3: blocco 'tools:' nel frontmatter dei file .agent.md è coerente.

    Applicabile solo se il file è .agent.md (il chiamante verificherà l'estensione).
    Regole:
    - merged_text deve contenere 'tools:' nel frontmatter.
    - Ogni stringa 'scf_...' presente in ours_text deve essere in merged_text.
    - Duplicati segnalati come warning nel messaggio, non come errore.

    Ritorna (True, "") se ok, (False, "tool mancanti: scf_X, scf_Y") se fallisce.
    """
    ...


def run_post_merge_validators(
    merged_text: str,
    base_text: str,
    ours_text: str,
    file_rel: str,
) -> dict[str, Any]:
    """
    Esegue i validator in sequenza.

    Ritorna:
        {
            "passed": bool,
            "results": [
                {"check": "structural", "passed": bool, "message": str},
                {"check": "completeness", "passed": bool, "message": str},
                {"check": "tool_coherence", "passed": bool, "message": str}
                # tool_coherence solo se file_rel.endswith(".agent.md")
            ]
        }
    """
    ...
```

**Tool MCP `scf_resolve_conflict_ai`**:

```python
@mcp.tool()
async def scf_resolve_conflict_ai(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Propone una risoluzione AI per un singolo conflitto in una sessione attiva.

    Costruisce un prompt strutturato con base_lines, ours_lines, theirs_lines
    e contesto adiacente. Non include path assoluti, SHA o credenziali nel prompt.
    Salva la proposta nella sessione con resolution_status="pending".

    Ritorna proposed_lines, confidence, reasoning.
    In assenza di LLM: success=False, error="llm_unavailable".
    """
```

#### 3.4.4 Test da scrivere

File: `tests/test_merge_validators.py`

| Test | Scopo |
|---|---|
| `test_validate_structural_ok` | testo valido + frontmatter ok → (True, "") |
| `test_validate_structural_markers_detected` | testo con `<<<<<<<` → (False, messaggio) |
| `test_validate_structural_frontmatter_not_closed` | `---` senza chiusura → (False, messaggio) |
| `test_validate_structural_headings_removed` | tutti i heading rimossi → (False, messaggio) |
| `test_validate_structural_no_frontmatter_in_base` | base senza frontmatter, merged senza → ok |
| `test_validate_completeness_all_preserved` | tutti gli H1/H2 di OURS presenti → (True, "") |
| `test_validate_completeness_missing_h2` | heading H2 di OURS mancante → (False, messaggio) |
| `test_validate_completeness_extra_theirs_headings_ok` | heading aggiuntivi da THEIRS → ok |
| `test_validate_tool_coherence_ok` | tutti i tool di OURS nella merged → (True, "") |
| `test_validate_tool_coherence_missing_tool` | scf_X di OURS assente → (False, messaggio) |
| `test_validate_tool_coherence_theirs_tool_added_ok` | tool nuovo da THEIRS accettato |
| `test_run_post_merge_validators_all_pass` | tutti i check passano |
| `test_run_post_merge_validators_one_fails` | un check fallisce → passed=False |
| `test_run_post_merge_validators_skips_tool_for_non_agent` | file non .agent.md → nessun check 3 |
| `test_resolve_conflict_ai_session_not_found` | session_id inesistente → error="session_not_found" |
| `test_resolve_conflict_ai_conflict_not_found` | conflict_id inesistente → error="conflict_not_found" |
| `test_resolve_conflict_ai_session_not_active` | sessione expired → error="session_not_active" |
| `test_auto_mode_clean_conflict_writes_file` | auto mode con conflitto risolvibile → file scritto |
| `test_auto_mode_validator_fail_degrades_to_manual` | validator fallisce → file con marcatori, sessione aperta |
| `test_auto_mode_frontmatter_conflict_degrades_to_manual` | conflitto frontmatter → degradazione (D-04) |
| `test_llm_unavailable_fallback` | LLM non disponibile → success=False, error="llm_unavailable" |

#### 3.4.5 Complessità relativa

**Media.** I validator sono logica regex pura, semplice da testare. La complessità è nell'integrazione del tool `scf_resolve_conflict_ai` con il client LLM MCP e nella gestione del fallback quando il LLM non è disponibile.

---

### Dettaglio Fase 5 — Modalità assisted (approvazione utente)

#### 3.5.1 File da creare

Nessun nuovo file Python.

#### 3.5.2 File da modificare

**`spark-framework-engine.py`**:

- Aggiungere tool MCP `scf_approve_conflict` in `register_tools()`.
- Aggiungere tool MCP `scf_reject_conflict` in `register_tools()`.
- Aggiornare contatore `# Tools (33)` e log `Tools registered: 33 total`.
- Estendere `scf_update_package` per gestire `conflict_mode="assisted"`.
- Estendere `scf_finalize_update` per gestire il mixed finalization (approved + rejected).

#### 3.5.3 Interfaccia da implementare

```python
@mcp.tool()
async def scf_approve_conflict(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Approva la proposta AI per un conflitto nella modalità assisted.

    Imposta resolution_status="approved" e approved=True nel conflitto della sessione.
    Non scrive ancora su disco: la scrittura avviene alla finalizzazione.

    Ritorna:
        {
            "success": bool,
            "session_id": str,
            "conflict_id": str,
            "approved": True,
            "remaining_conflicts": int
        }

    Pre-condizioni:
        La sessione deve essere active.
        Il conflitto deve essere in stato pending (aveva proposed_lines non null).
    """


@mcp.tool()
async def scf_reject_conflict(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Rifiuta la proposta AI per un conflitto nella modalità assisted.

    Imposta resolution_status="rejected" nel conflitto della sessione.
    Al momento di scf_finalize_update, il conflitto riceverà marcatori manuali.

    Ritorna:
        {
            "success": bool,
            "session_id": str,
            "conflict_id": str,
            "rejected": True,
            "fallback": "manual",
            "remaining_conflicts": int
        }
    """
```

**Logica `_count_remaining_conflicts(session_data) -> int`**:

```python
def _count_remaining_conflicts(session_data: dict[str, Any]) -> int:
    """
    Conta i conflitti con resolution_status="pending" in tutti i file della sessione.
    Usato da scf_approve_conflict e scf_reject_conflict per il campo remaining_conflicts.
    """
    count = 0
    for file_entry in session_data.get("files", []):
        for conflict in file_entry.get("conflicts", []):
            if conflict.get("resolution_status") == "pending":
                count += 1
    return count
```

#### 3.5.4 Test da scrivere

File: `tests/test_merge_assisted.py`

| Test | Scopo |
|---|---|
| `test_approve_sets_resolution_status` | approve → resolution_status="approved" nella sessione |
| `test_approve_requires_proposed_lines` | approve senza proposed_lines → errore |
| `test_reject_sets_resolution_status` | reject → resolution_status="rejected" nella sessione |
| `test_remaining_conflicts_decrements` | approve/reject decrementano remaining_conflicts |
| `test_remaining_conflicts_zero_when_all_resolved` | tutti approved/rejected → remaining=0 |
| `test_finalize_writes_approved_without_markers` | conflitto approved → file scritto senza marcatori |
| `test_finalize_writes_rejected_with_markers` | conflitto rejected → file con marcatori per quel blocco |
| `test_finalize_mixed_approved_rejected` | alcuni approved, alcuni rejected → mix corretto nel file scritto |
| `test_finalize_checks_sha_at_session_open` | SHA cambiato → external_modification_detected |
| `test_finalize_session_status_finalized` | dopo finalize → session.status="finalized" |
| `test_approve_on_inactive_session_fails` | approve su sessione expired → success=False |
| `test_reject_on_inactive_session_fails` | reject su sessione expired → success=False |
| `test_full_assisted_flow` | create → resolve_ai → approve → finalize (end-to-end) |
| `test_full_assisted_reject_flow` | create → resolve_ai → reject → finalize → file con marcatori |

#### 3.5.5 Complessità relativa

**Bassa.** I tool `scf_approve_conflict` e `scf_reject_conflict` sono thin wrapper sulla mutazione dello stato sessione. La logica di finalizzazione è già implementata in Fase 3; questa fase la estende con la distinzione approved/rejected.

---

### Dettaglio Fase 6 — Policy multi-owner

#### 3.6.1 File da creare

Nessun nuovo file Python.

#### 3.6.2 File da modificare

**`spark-framework-engine.py`**:

- `_classify_install_files` (riga ~1394): aggiungere parsing di `file_policies` dal manifest remoto e applicazione categorie `extend_section`, `delegate_skip`.
- Aggiungere funzioni helper:
  - `_parse_file_policies(pkg_manifest) -> dict[str, dict]`
  - `_update_package_section(file_path, package_id, new_content) -> bool`
  - `_parse_section_markers(text, package_id) -> tuple[int, int] | None`
  - `_create_file_with_section(file_path, package_id, content) -> None`
  - `_validate_extend_policy_file(file_rel) -> bool`

#### 3.6.3 Interfaccia da implementare

```python
def _parse_file_policies(pkg_manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    Estrae la mappa {file_rel: policy_dict} dalla sezione file_policies del manifest.
    La policy globale file_ownership_policy resta il default per file non elencati.

    Esempio input:
        {
            "file_ownership_policy": "error",
            "file_policies": [
                {"path": ".github/copilot-instructions.md", "policy": "extend",
                 "section_marker": "<!-- SCF:SECTION:pkg:BEGIN -->"}
            ]
        }

    Esempio output:
        {
            ".github/copilot-instructions.md": {
                "policy": "extend",
                "section_marker": "<!-- SCF:SECTION:pkg:BEGIN -->"
            }
        }
    """
    ...


def _validate_extend_policy_file(file_rel: str) -> bool:
    """
    Ritorna True se il file supporta la policy extend.
    I file .agent.md NON supportano extend (strutturalmente vincolanti).
    I file .yaml / .yml NON supportano extend.
    """
    ...


def _parse_section_markers(
    text: str,
    package_id: str,
) -> tuple[int, int] | None:
    """
    Cerca i marcatori <!-- SCF:SECTION:<package_id>:BEGIN --> e :END --> nel testo.
    Ritorna (start_line, end_line) del contenuto interno (esclude i marcatori stessi).
    Ritorna None se i marcatori non sono presenti.

    Pattern atteso (su righe proprie):
        <!-- SCF:SECTION:package-id:BEGIN -->
        <contenuto>
        <!-- SCF:SECTION:package-id:END -->
    """
    ...


def _update_package_section(
    file_path: Path,
    package_id: str,
    new_content: str,
) -> bool:
    """
    Aggiorna solo la sezione del pacchetto nel file esistente.
    Se la sezione non esiste, la aggiunge in fondo al file.
    Ritorna True se il file è stato modificato.
    """
    ...


def _create_file_with_section(
    file_path: Path,
    package_id: str,
    content: str,
) -> None:
    """
    Crea un nuovo file con solo la sezione del pacchetto.
    Formato:
        <!-- SCF:SECTION:<package-id>:BEGIN -->
        <content>
        <!-- SCF:SECTION:<package-id>:END -->
    """
    ...
```

#### 3.6.4 Test da scrivere

File: `tests/test_multi_owner_policy.py`

| Test | Scopo |
|---|---|
| `test_parse_file_policies_empty` | manifest senza file_policies → dict vuoto |
| `test_parse_file_policies_extend` | policy extend estratta correttamente |
| `test_parse_file_policies_delegate` | policy delegate estratta correttamente |
| `test_validate_extend_agent_md_rejected` | .agent.md → False |
| `test_validate_extend_yaml_rejected` | .yaml → False |
| `test_validate_extend_md_accepted` | .md generico → True |
| `test_parse_section_markers_found` | testo con marcatori → (start, end) corretto |
| `test_parse_section_markers_not_found` | testo senza marcatori → None |
| `test_update_package_section_replaces_content` | contenuto sezione aggiornato |
| `test_update_package_section_other_content_untouched` | contenuto fuori sezione invariato |
| `test_update_package_section_no_markers_appends` | sezione assente → aggiunta in fondo |
| `test_create_file_with_section_format` | file creato ha formato marker corretto |
| `test_classify_extend_returns_extend_section` | classificazione per file extend → extend_section |
| `test_classify_delegate_returns_delegate_skip` | classificazione per file delegate → delegate_skip |
| `test_delegate_skip_no_snapshot_created` | file con delegate → nessuno snapshot |
| `test_error_policy_blocks_cross_owner` | policy error (default) → conflict_cross_owner |
| `test_per_file_policy_overrides_global` | policy per-file extend sovrascrive global error |

#### 3.6.5 Complessità relativa

**Media.** Il parsing dei marcatori con regex richiede attenzione ai dettagli. Il rischio principale è la fragilità dei pattern regex su file con encoding o whitespace non previsti.

---

### Dettaglio Fase 7 — Versioning, CHANGELOG, README, release

#### 3.7.1 File da creare

Nessun nuovo file Python o di documentazione aggiuntivo.

#### 3.7.2 File da modificare

**`spark-framework-engine.py`**:

- Riga 40: `ENGINE_VERSION: str = "2.0.0"`.
- Commento classe `SparkFrameworkEngine`: `# Tools (34)` (29 originali + 5 nuovi: `scf_finalize_update`, `scf_resolve_conflict_ai`, `scf_approve_conflict`, `scf_reject_conflict`, e un eventuale `scf_cleanup_sessions` se aggiunto).
- Riga ~2407: `_log.info("Tools registered: 34 total")`.

**`CHANGELOG.md`**:

- Aggiungere nuova voce `## [2.0.0] - 2026-MM-DD` come **prima voce** del file (invariante test_engine_coherence.py).
- Sezioni: Added (nuovi tool, sistema merge, snapshot, sessioni), Changed (scf_update_package con conflict_mode esteso), Notes (nessuna regressione su abort/replace).

**`README.md`**:

- Aggiungere sezione `## Sistema di merge a 3-via` con descrizione delle 3 modalità e workflow di base.
- Aggiornare contatore tool nella tabella funzionalità (da 29 a 34).

**`docs/ROADMAP-FASE2.md`**:

- Aggiornare la voce "conflict_mode: 'merge'" con stato "completata (v2.0.0)".

#### 3.7.3 Test da scrivere

Nessun nuovo test. I test esistenti fungono da criterio di uscita:

- `test_engine_coherence.py`: verifica allineamento `ENGINE_VERSION` ↔ prima voce CHANGELOG ↔ contatori tool.
- Intera suite `pytest -q`: 84 test baseline + tutti i nuovi test delle Fasi 0–6 devono passare.

#### 3.7.4 Complessità relativa

**Bassa.** Modifiche meccaniche guidate dall'invariante del test e dalle convenzioni esistenti.

---

## 4. Matrice delle dipendenze tra fasi

```
           F0   F1   F2   F3   F4   F5   F6   F7
       F0   -    -    -    -    -    -    -    -
       F1   -    -    -    -    -    -    -    -
       F2   X    X    -    -    -    -    -    -
       F3   -    -    X    -    -    -    -    -
       F4   -    -    -    X    -    -    -    -
       F5   -    -    -    X    X    -    -    -
       F6   -    -    X    -    -    -    -    -
       F7   X    X    X    X    X    X    X    -

X = la fase (riga) dipende dalla fase (colonna)
```

**Legenda percorsi critici**:

- **Percorso critico A** (Merge full): F0 → F2 → F3 → F4 → F5 → F7
- **Percorso critico B** (Merge base): F1 → F2 → F3 → F7
- **Percorso secondario** (Multi-owner): F0 → F2 → F6 → F7
- **Parallelizzabile subito**: F0 e F1 (zero dipendenze tra loro)
- **F6** può iniziare in parallelo con F3/F4/F5 una volta F2 completata

**Blocchi di sviluppo suggeriti**:

```
Sprint 1 (parallelo): F0 + F1
Sprint 2 (sequenziale): F2 (richiede F0 e F1 completi)
Sprint 3 (parallelo): F3 + F6 (entrambi dipendono solo da F2)
Sprint 4 (sequenziale): F4 (richiede F3)
Sprint 5 (sequenziale): F5 (richiede F3 e F4)
Sprint 6 (finale): F7 (richiede tutte le fasi precedenti)
```

---

## 5. Test strategy

### 5.1 Principi generali

- Ogni fase ha il proprio file di test dedicato.
- I test di non-regressione per le modalità `abort` e `replace` vanno in `tests/test_merge_integration.py` (Fase 2) e DEVONO passare prima di considerare Fase 2 completa.
- I test di integrazione live (quelli in `tests/test_integration_live.py`) non vengono modificati.
- La suite `pytest -q` deve passare interamente a ogni fase completata.
- I test usano `tmp_path` di pytest per isolare il filesystem.
- `MergeEngine` e i validator sono testabili senza fixture di engine (pura logica Python).

### 5.2 File di test per fase

| Fase | File di test | Tipo |
|---|---|---|
| 0 | `tests/test_snapshot_manager.py` | Unitario + integrazione |
| 1 | `tests/test_merge_engine.py` | Unitario (puro Python) |
| 2 | `tests/test_merge_integration.py` | Integrazione |
| 3 | `tests/test_merge_session.py` | Unitario + integrazione MCP |
| 4 | `tests/test_merge_validators.py` | Unitario + integrazione MCP |
| 5 | `tests/test_merge_assisted.py` | Integrazione MCP |
| 6 | `tests/test_multi_owner_policy.py` | Unitario + integrazione |
| 7 | (suite completa) | Verifica invarianti |

### 5.3 Test di non-regressione obbligatori (Fase 2)

I seguenti test devono passare prima di considerare il flusso di merge integrato. Fallire uno di questi blocca il completamento della Fase 2:

```
tests/test_merge_integration.py::test_abort_mode_preserves_modified_file
tests/test_merge_integration.py::test_replace_mode_overwrites_modified_file
tests/test_merge_integration.py::test_update_tracked_clean_still_overwrites
tests/test_merge_integration.py::test_create_new_still_creates
tests/test_package_installation_policies.py (suite completa esistente)
```

### 5.4 Test parametrizzati consigliati

Per `test_merge_engine.py`, usare `@pytest.mark.parametrize` sui casi diff3:

```python
MERGE_CASES = [
    pytest.param(
        "base\n", "base\n", "base\n",
        "identical", [], 0,
        id="all_identical"
    ),
    pytest.param(
        "line1\nline2\n",
        "line1\nmodified\n",
        "line1\nline2\n",
        "clean", ["line1\n", "modified\n"], 0,
        id="only_ours_changes"
    ),
    # ... altri casi
]

@pytest.mark.parametrize("base,ours,theirs,expected_status,expected_lines,expected_conflicts", MERGE_CASES)
def test_diff3_merge_parametrized(base, ours, theirs, expected_status, expected_lines, expected_conflicts):
    engine = MergeEngine()
    result = engine.diff3_merge(base, ours, theirs)
    assert result.status == expected_status
    assert result.conflicts.__len__() == expected_conflicts
```

### 5.5 Comandi di validazione per fase

Eseguire prima di completare ogni fase:

```powershell
# Fase 0
.venv\Scripts\python.exe -m pytest -q tests/test_snapshot_manager.py tests/test_package_installation_policies.py

# Fase 1
.venv\Scripts\python.exe -m pytest -q tests/test_merge_engine.py

# Fase 2
.venv\Scripts\python.exe -m pytest -q tests/test_merge_integration.py tests/test_package_installation_policies.py tests/test_bootstrap_workspace.py

# Fase 3
.venv\Scripts\python.exe -m pytest -q tests/test_merge_session.py tests/test_merge_integration.py

# Fase 4
.venv\Scripts\python.exe -m pytest -q tests/test_merge_validators.py tests/test_merge_session.py

# Fase 5
.venv\Scripts\python.exe -m pytest -q tests/test_merge_assisted.py tests/test_merge_validators.py

# Fase 6
.venv\Scripts\python.exe -m pytest -q tests/test_multi_owner_policy.py tests/test_merge_integration.py

# Fase 7 (completa)
.venv\Scripts\python.exe -m pytest -q
```

---

## 6. Rischi e mitigazioni

### 6.1 Rischi Fase 0 — Snapshot Manager

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Snapshot scritto su installazione esistente sovrascrive dati utente | Bassa | Alto | Lo snapshot è una copia del file come scritto dal motore, non del file corrente sul workspace; viene scritto solo dopo `dest.write_bytes()` confermato |
| Path traversal su `file_rel` contaminato | Media | Alto | Validazione obbligatoria in `_snapshot_path` con check `is_absolute()` e `".." in path.parts` |
| Errore I/O durante save snapshot non blocca l'installazione | Media | Medio | Eccezione catturata in try/except; il file è già scritto; snapshot fallisce → aggiunto a `snapshot_skipped`, log warning |

### 6.2 Rischi Fase 1 — MergeEngine

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| `SequenceMatcher` produce risultati controintuitivi su file molto diversi | Media | Medio | Test parametrizzati con casi edge documentati; accettare che merge molto divergenti producano molti conflitti anziché una risoluzione magica |
| Off-by-one nelle righe di contesto di `MergeConflict` | Alta | Medio | Test espliciti su `context_before` e `context_after`; clamping degli indici a `[0, len(lines))` |
| `diff3_merge` non gestisce correttamente file con `\r\n` (Windows) | Media | Medio | Normalizzare a `\n` in ingresso, denormalizzare in uscita se necessario; test su `\r\n` |
| `render_with_markers` su merge clean inserisce marcatori | Bassa | Alto | Test `test_render_with_markers_clean_result_no_markers` obbligatorio |

### 6.3 Rischi Fase 2 — Integrazione install/update

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Regressione su `abort`/`replace` per refactoring `_classify_install_files` | Alta | Alto | Test di non-regressione eseguiti prima di completare la fase; CI bloccante |
| File con merge clean + fallback a preserve corrompe il manifest | Media | Alto | Il merge clean aggiorna sia il file che lo snapshot e il manifest in modo coerente; rollback al pre-merge se qualsiasi passo fallisce |
| Snapshot assente durante primo aggiornamento (fase di transizione) | Certa | Medio | Il fallback a preserve (con `base_unavailable: True` nel report) è il comportamento documentato; utente informato |

### 6.4 Rischi Fase 3 — Sessione merge stateful

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Sessione orfana blocca un pacchetto all'infinito | Media | Alto | `has_active_session_for_package` verificato all'inizio di ogni `scf_update_package`; sessioni orfane (expired + active) vengono marcate da `cleanup_expired_sessions` |
| File JSON di sessione corrotto dopo crash | Bassa | Alto | Scrittura atomica: scrivi su file `.tmp`, rinomina; se `.tmp` esiste all'avvio, sessione marcata orphaned |
| Race condition su due invocazioni concorrenti di `scf_update_package` | Bassa | Alto | Non supportato in questo design; documentare che le invocazioni devono essere sequenziali |

### 6.5 Rischi Fase 4 — Auto AI

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| LLM propone risoluzione che passa i validator ma è semanticamente errata | Media | Alto | Questa è una limitazione by design; la modalità `auto` è documentata come best-effort; `assisted` è la modalità raccomandato per file critici |
| LLM include path assoluti o dati sensibili nel reasoning | Bassa | Medio | Il prompt rimuove esplicitamente qualsiasi path assoluto o SHA prima di inviare al LLM |
| Conflitti frontmatter risolti automaticamente rendono agenti non funzionali | Certa senza guardia | Critico | D-04 del design: conflitti frontmatter sono sempre degradati a manual anche in auto mode |

### 6.6 Rischi Fase 5 — Assisted

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Utente approva proposta non ancora generata | Bassa | Medio | `scf_approve_conflict` verifica che `proposed_lines` non sia null prima di approvare |
| Finalizzazione parziale su errore I/O lascia file in stato inconsistente | Bassa | Alto | Rollback pre-scrittura: cattura SHA di ogni file prima di scrivere; se scrittura fallisce, ripristina |

### 6.7 Rischi Fase 6 — Multi-owner

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| Regex marcatori sezione non matcha varianti whitespace | Alta | Medio | Strip delle righe prima del confronto; test con spazi extra e tab |
| Sezione BEGIN senza END (marcatori incompleti nel file) | Media | Medio | Parser tratta marcatori incompleti come assenti; aggiunge sezione in fondo |
| Pacchetto B dichiara extend su file .agent.md (non supportato) | Media | Alto | Guard in `_validate_extend_policy_file`; errore esplicito con messaggio diagnostico |

### 6.8 Rischi Fase 7 — Release

| Rischio | Probabilità | Impatto | Mitigazione |
|---|---|---|---|
| CHANGELOG.md con voce Unreleased come prima voce viola invariante test | Alta se non si segue l'istruzione | Alto | La voce `## [2.0.0]` DEVE essere la prima voce nel file; nessuna voce `[Unreleased]` |
| Contatore tool nel commento classe e nel log disallineati | Media | Alto | Aggiornare entrambi contemporaneamente (multi_replace_string_in_file) |

---

## 7. Metriche di successo

### 7.1 Metriche funzionali

| Metrica | Target | Verifica |
|---|---|---|
| Test suite completa | 0 fallimenti | `pytest -q` da root |
| Test di non-regressione abort/replace | 0 fallimenti | `pytest -q tests/test_merge_integration.py -k "abort or replace"` |
| ENGINE_VERSION allineata a CHANGELOG | Prima voce = 2.0.0 | `test_engine_coherence.py` |
| Contatori tool allineati | Commento classe = Log = n. tool reali | `test_engine_coherence.py` |
| SnapshotManager path traversal bloccato | ValueError su input malevoli | `test_snapshot_manager.py::test_path_traversal_rejected` |
| MergeEngine senza import MCP | Zero import da mcp o SparkFrameworkEngine | `test_merge_engine.py::test_merge_engine_no_mcp_import` |
| Merge clean scrive file correttamente | File su disco = join(merged_lines) | `test_merge_integration.py::test_manual_mode_clean_merge_writes_file` |
| Modalità manual apre sessione | session_id nel ritorno | `test_merge_integration.py::test_manual_mode_conflict_creates_session` |
| Validator bloccano conflitti non risolti | has_conflict_markers → False in finalize | `test_merge_session.py::test_finalize_tool_writes_file` |
| Auto mode degrada frontmatter a manual | Decisione D-04 rispettata | `test_merge_validators.py::test_auto_mode_frontmatter_conflict_degrades_to_manual` |
| Extend policy aggiorna solo sezione | Contenuto utente invariato | `test_multi_owner_policy.py::test_update_package_section_other_content_untouched` |

### 7.2 Metriche di qualità codice

| Metrica | Target |
|---|---|
| Copertura test MergeEngine | ≥ 90% (misurato con `pytest --cov`) |
| Copertura test SnapshotManager | ≥ 85% |
| Copertura test MergeSessionManager | ≥ 85% |
| Nessuna dipendenza esterna aggiunta | `requirements.txt` invariato |
| Nessun `print()` a stdout nel codice nuovo | Verificato con grep o ruff |

### 7.3 Audit di coerenza finale (Fase 7)

Prima del bump di versione, eseguire l'audit completo con la skill `scf-coherence-audit`:

1. Numero tool dichiarati nel commento classe == numero di `@mcp.tool()` nel sorgente.
2. Numero tool nel log == stesso valore.
3. Nessun tool senza docstring.
4. Nessun tool con docstring vuota o placeholder.
5. `ENGINE_VERSION` == prima voce CHANGELOG.
6. README aggiornato con nuovi tool e conflict_mode.

---

## 8. Migration path

### 8.1 Scenario: workspace installati con engine < 2.0.0

I workspace che hanno eseguito `scf_install_package` o `scf_bootstrap_workspace` prima del rilascio di engine 2.0.0 **non hanno snapshot BASE**. La directory `.github/runtime/snapshots/` non esiste o è vuota.

### 8.2 Comportamento garantito (nessuna azione manuale richiesta)

Il sistema di merge tollera l'assenza di snapshot senza blocchi operativi:

1. L'utente esegue `scf_update_package` con qualsiasi `conflict_mode`.
2. Il tool classifica i file modificati come `merge_candidate_no_base`.
3. Senza snapshot BASE, il merge a 3 vie non è calcolabile.
4. Il motore **non tenta un merge degradato** per default: il file viene classificato come `preserved` e aggiunto a `snapshot_skipped`.
5. Il report include `"base_unavailable": true` per ogni file saltato.
6. La modalità `abort` e `replace` continuano a funzionare invariate (non richiedono snapshot).

**Eccezione documentata nel design (sezione 13.2)**: se `conflict_mode="auto"` viene specificato esplicitamente, il motore tenta un merge degradato con `BASE = THEIRS`. Questo è documentato e l'utente riceve il campo `"base_unavailable": true` come warning. Il comportamento è opt-in, non il default.

### 8.3 Come ottenere gli snapshot per workspace esistenti

La strategia raccomandata per ottenere gli snapshot senza perdere dati:

**Opzione A — Reinstallazione pulita** (zero rischi):

```
1. scf_verify_workspace()
   → identifica file modificati dall'utente (hash mismatch)
2. Backup manuale dei file modificati fuori dal workspace
3. scf_install_package(package_id, conflict_mode="replace")
   → sovrascrive i file (inclusi quelli modificati) e crea gli snapshot
4. Riapplicare le modifiche utente dai backup
5. scf_verify_workspace() → conferma stato pulito
```

**Opzione B — Prima installazione aggiornamento** (best-effort):

```
1. scf_update_package(package_id, conflict_mode="replace")
   → sovrascrive file modificati, aggiorna snapshot
   → i file con modifiche utente vengono persi in questa operazione
2. Il prossimo aggiornamento avrà snapshot validi per il merge
```

**Opzione C — Snapshot bootstrap manuale** (non implementata in 2.0.0):

Un futuro tool `scf_backfill_snapshots(package_id)` potrebbe scaricare le versioni originali dei file installati dal registry e creare gli snapshot retroattivamente. Non è nel perimetro di questa implementazione.

### 8.4 Comportamento specifico del migration path in ogni fase

| Fase | Comportamento se snapshot assente | Campo nel report |
|---|---|---|
| Fase 0 | Fase 0 crea i snapshot → problema non si pone per nuove installazioni | — |
| Fase 2 | `merge_candidate_no_base` → preserved | `base_unavailable: true` in merge_conflict |
| Fase 3 | Nessuna sessione creata (skip al preserve) | — |
| Fase 4 | `conflict_mode="auto"` → merge degradato (BASE=THEIRS) oppure preserved | `base_unavailable: true` |
| Fase 5 | `conflict_mode="assisted"` → merge degradato come sopra | `base_unavailable: true` |

### 8.5 Comunicazione all'utente

Il tool deve comunicare esplicitamente la situazione nei workspace senza snapshot:

```json
{
  "success": true,
  "preserved": ["agents/spark-guide.agent.md"],
  "merge_conflict": [],
  "merge_clean": [],
  "snapshot_skipped": ["agents/spark-guide.agent.md"],
  "base_unavailable_files": ["agents/spark-guide.agent.md"],
  "note": "1 file preservato: snapshot BASE non disponibile (installazione pre-2.0.0). Per abilitare il merge, reinstallare il pacchetto con conflict_mode='replace' e riapplicare le personalizzazioni."
}
```

### 8.6 Bootstrap workspace esistente (scf_bootstrap_workspace)

`scf_bootstrap_workspace` con engine 2.0.0 crea automaticamente gli snapshot `__bootstrap__` per i file copiati. I workspace già bootstrappati che eseguono nuovamente il bootstrap (raro, ma può avvenire dopo un rollback) riceveranno lo snapshot aggiornato con il contenuto corrente del file, non con l'originale. Questo è accettabile: il bootstrap è un'operazione di setup, non di aggiornamento.

---

*Fine documento SCF-3WAY-MERGE-IMPLEMENTATION-PLAN v1.0.0*
*Generato il 2026-04-14 da spark-engine-maintainer*
*Documento di design di riferimento: `docs/SCF-3WAY-MERGE-DESIGN.md` v1.0.0*
