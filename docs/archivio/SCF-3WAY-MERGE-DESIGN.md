# SCF 3-Way Merge System — Documento di Design

**Versione documento**: 1.0.0
**Data**: 2026-04-14
**Stato**: Finale
**Target engine**: spark-framework-engine 2.0.0
**Autore**: spark-engine-maintainer
**Riferimenti**:
- `docs/SCF-PACKAGE-UPDATE-SYSTEM-DESIGN.md`
- `docs/SPARK-ECOSYSTEM-AUDIT-2026-04-13.md`
- `docs/ROADMAP-FASE2.md`
- `spark-framework-engine.py` (ENGINE_VERSION 1.9.0)

---

## Indice

1. Executive Summary
2. Stato attuale e gap analysis
3. Architettura snapshot BASE
4. MergeEngine — specifica della classe
5. Flusso operativo detect → merge → report
6. Tool MCP nuovi
7. Sessione di merge stateful
8. Validator post-merge AI
9. Policy multi-owner
10. Impatto su scf_bootstrap_workspace e scf_install_package
11. Contratto di risultato
12. Vincoli di sicurezza e accessibilità
13. Casistiche edge
14. Dipendenze e prerequisiti
15. Decision log

---

## 1. Executive Summary

### Problema

Il motore SPARK Code Framework (v1.9.0) gestisce due scenari di aggiornamento in modo soddisfacente:

- `create_new`: file assente sul workspace → il motore scrive senza conflitti.
- `update_tracked_clean`: file tracciato dal manifest, non modificato dall'utente → il motore sovrascrive.

Il terzo scenario critico, `preserve_tracked_modified`, viene risolto con un semplice skip: se l'utente ha modificato un file tracciato, l'aggiornamento del pacchetto non raggiunge mai quel file. Il risultato concreto è che le nuove versioni dei template ufficiali non vengono mai integrate nei workspace con personalizzazioni. L'utente perde gli aggiornamenti in silenzio.

### Soluzione

Il sistema di aggiornamento integrativo a 3-way merge risolve il gap introducendo una terza via tra "sovrascrivere" e "saltare": **unire** le modifiche dell'utente con quelle ufficiali del pacchetto, usando uno snapshot BASE acquisito alla prima installazione come antenato comune.

Il sistema opera in tre modalità selezionabili:

- `manual`: l'utente riceve un file con marcatori di conflitto e risolve autonomamente.
- `auto`: un LLM integrato risolve i conflitti in autonomia, con validazione post-merge.
- `assisted`: l'LLM propone una risoluzione, l'utente approva o rifiuta per ogni file in conflitto.

### Impatto

- **Nessuna regressione**: i conflitti `update_tracked_clean` e `create_new` non cambiano comportamento.
- **Nessun dato silenziosamente perso**: le modifiche utente sono sempre visibili nel report.
- **Audit trail completo**: ogni sessione di merge è serializzata su disco nella cartella `runtime/merge-sessions/`.
- **Compatibilità NVDA**: nessun output con HTML embedded, diagrammi in testo ASCII, report strutturati navigabili.

---

## 2. Stato attuale e gap analysis

### 2.1 Componenti esistenti rilevanti

#### ManifestManager

Il file `.github/.scf-manifest.json` traccia ogni file installato con la struttura:

```json
{
  "schema_version": "1.0",
  "entries": [
    {
      "file": "agents/spark-guide.agent.md",
      "package": "scf-master-codecrafter",
      "package_version": "1.0.0",
      "installed_at": "2026-01-15T10:00:00Z",
      "sha256": "abc123..."
    }
  ]
}
```

Il metodo `is_user_modified(file_rel)` confronta l'SHA-256 memorizzato nel manifest con quello corrente sul disco: ritorna `True` se il file è stato modificato, `False` se intatto, `None` se non tracciato.

Il manifest non conserva il contenuto originale del file al momento dell'installazione; si limita a tracciare quale SHA era stato scritto.

#### _classify_install_files

La funzione `_classify_install_files(package_id, files)` in `spark-framework-engine.py` classifica ogni file target in una delle seguenti categorie:

```
create_new               → file non esiste sul workspace; il motore scrive
update_tracked_clean     → file tracciato, SHA non modificato; il motore sovrascrive
preserve_tracked_modified → file tracciato, SHA modificato; il motore SALTA (GAP)
conflict_untracked_existing → file esiste ma non tracciato; comportamento dipende da conflict_mode
conflict_cross_owner     → file posseduto da un altro pacchetto; errore bloccante
```

#### _build_install_result

Il contratto di ritorno già prevede i campi:

```python
{
    "success": bool,
    "installed": [],
    "preserved": [],
    "merged_files": [],          # già presente, sempre vuoto
    "requires_user_resolution": False,
    "resolution_applied": "none",
    ...
}
```

I campi `merged_files` e `requires_user_resolution` sono già presenti ma mai popolati.

### 2.2 Gap identificati dall'audit (2026-04-13)

**GAP-1 — Snapshot BASE assente**
Il motore non conserva il contenuto originale al momento della prima installazione. Senza il testo BASE, un merge a 3 vie (BASE, OURS, THEIRS) non è calcolabile. Il sistema attuale conosce solo l'SHA del file che ha scritto, non il testo.

**GAP-2 — preserve_tracked_modified non produce merge**
I file classificati `preserve_tracked_modified` vengono inseriti in `preserve_plan` e saltati senza tentare alcuna unione. L'utente non riceve le nuove modifiche ufficiali del pacchetto.

**GAP-3 — Nessuna sessione stateful**
Il motore non ha un meccanismo per mantenere lo stato tra invocazioni successive di tool MCP. Per gestire `assisted mode` serve una struttura di sessione persistente.

**GAP-4 — Nessun validator post-merge**
In caso di merge automatico, il motore non valida la correttezza strutturale del risultato (frontmatter YAML, heading Markdown, coerenza del blocco `tools:` nei file `.agent.md`).

**GAP-5 — Policy multi-owner non definita**
Il valore `file_ownership_policy: "error"` nei manifest package risolve solo il caso binario. Non esiste una policy `extend` o `delegate` per file condivisi tra due pacchetti diversi.

**GAP-6 — scf_apply_updates non è atomico**
L'audit ha confermato che `scf_apply_updates` applica i pacchetti in sequenza. Se un pacchetto successivo fallisce, i file del primo pacchetto sono già scritti su disco. Il merge batch deve aggiungere una fase preflight che eviti scritture parziali.

### 2.3 Cosa non cambia

- Il formato del manifest `.github/.scf-manifest.json` (schema 1.0) non viene alterato.
- I `conflict_mode` esistenti `abort` e `replace` continuano a funzionare invariati.
- I tool `scf_check_updates`, `scf_verify_workspace`, `scf_verify_system` non sono interessati.
- Il comportamento di `conflict_cross_owner` resta un errore bloccante.

---

## 3. Architettura snapshot BASE

### 3.1 Problema

Per eseguire un merge a 3-way è necessario conoscere il testo del file al momento dell'installazione originale (BASE). Il manifest attuale conserva solo l'SHA-256 del file installato, non il contenuto.

### 3.2 Dove vengono salvati gli snapshot

Percorso: `.github/runtime/snapshots/<package-id>/<file-rel-path>`

Esempio concreto:

```
.github/
  runtime/
    snapshots/
      scf-master-codecrafter/
        agents/
          spark-guide.agent.md
          spark-orchestrator.agent.md
        instructions/
          model-policy.instructions.md
      scf-pycode-crafter/
        instructions/
          python.instructions.md
```

La struttura replica esattamente la gerarchia dei file come sono installati sotto `.github/`, con il package-id come directory radice aggiuntiva. Questo garantisce unicità anche in presenza di due pacchetti con file a percorsi simili.

### 3.3 Formato e contenuto

Lo snapshot è il testo grezzo del file come scritto dal motore durante l'installazione, codificato in UTF-8 senza trasformazioni. Non è compresso né cifrato. Per file binari (vedere sezione 13) lo snapshot non viene creato.

### 3.4 Lifecycle

**Creazione**: al momento della prima installazione di un pacchetto (`scf_install_package`) o al bootstrap (`scf_bootstrap_workspace`), il motore scrive lo snapshot dopo aver scritto il file target.

**Aggiornamento**: quando un aggiornamento di pacchetto sovrascrive un file `update_tracked_clean`, lo snapshot esistente viene rimpiazzato con il nuovo contenuto ufficiale.

**Conservazione durante merge**: durante un merge `preserve_tracked_modified`, lo snapshot BASE viene letto ma non modificato fino al completamento della sessione.

**Rimozione**: quando `scf_remove_package(package_id)` elimina le entry dal manifest, elimina anche la directory snapshot corrispondente (`runtime/snapshots/<package-id>/`).

**Assenza tollerata**: se lo snapshot BASE è assente (installazione precedente al sistema di merge), il motore adotta la strategia di fallback definita nella sezione 13 (casistica edge "Snapshot BASE assente").

### 3.5 Relazione con il manifest

Il manifest non viene esteso con il percorso snapshot; la posizione è deterministicamente calcolabile da `package_id` e `file_rel`. Il motore può sempre ricostruire il percorso snapshot senza dati aggiuntivi nel manifest.

### 3.6 Dimensione e costi

Gli snapshot aggiungono al massimo il doppio della dimensione dei file installati. Per un pacchetto come `scf-master-codecrafter` con 62 file Markdown (stimati in media 4 KB ciascuno), il costo è circa 250 KB. Accettabile.

---

## 4. MergeEngine — specifica della classe

### 4.1 Responsabilità

`MergeEngine` è una classe pura Python, senza effetti collaterali su disco, che:

1. Calcola il merge a 3-via tra BASE, OURS e THEIRS.
2. Restituisce un oggetto strutturato con il risultato del merge e i conflitti irrisolti.
3. Non modifica file, non legge dal filesystem, non usa il manifest.

L'accesso al filesystem e al manifest resta responsabilità del tool MCP chiamante.

### 4.2 Interfaccia

```python
from dataclasses import dataclass, field
from typing import Literal

MergeStatus = Literal["clean", "conflict", "identical", "binary_skip"]

@dataclass
class MergeConflict:
    """Rappresenta un singolo conflitto riga per riga non risolvibile automaticamente."""
    conflict_id: str          # UUID stabile per la sessione
    start_line: int           # riga iniziale nel file BASE (0-based)
    end_line: int             # riga finale nel file BASE (0-based, incluso)
    base_lines: list[str]     # righe originali (BASE)
    ours_lines: list[str]     # righe versione utente (OURS)
    theirs_lines: list[str]   # righe versione pacchetto (THEIRS)
    context_before: list[str] # righe di contesto prima del conflitto (max 3)
    context_after: list[str]  # righe di contesto dopo il conflitto (max 3)

@dataclass
class MergeResult:
    """Risultato di un merge a 3-via per un singolo file."""
    status: MergeStatus
    merged_lines: list[str]            # testo risultante (vuoto se conflict non risolto)
    conflicts: list[MergeConflict] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
    # stats conterrà: total_lines, clean_sections, conflict_count, identical_sections

class MergeEngine:
    """Motore di merge a 3-via puro. Nessun I/O."""

    BASE_MARKER = "<<<<<<< YOURS"
    SEP_MARKER  = "======="
    THEIR_MARKER = ">>>>>>> OFFICIAL"

    def diff3_merge(
        self,
        base: str,
        ours: str,
        theirs: str,
    ) -> MergeResult:
        """
        Calcola il merge a 3-via tra base, ours e theirs.

        Parametri:
            base   -- testo originale al momento dell'installazione (snapshot BASE)
            ours   -- testo corrente sul workspace (versione utente)
            theirs -- testo della nuova versione ufficiale del pacchetto

        Ritorna:
            MergeResult con tutti i blocchi merged e i conflitti espliciti.
        """
        ...

    def render_with_markers(self, result: MergeResult) -> str:
        """
        Produce un testo con marcatori di conflitto stile diff3.
        Usato dalla modalità manual.

            <<<<<<< YOURS
            ... righe versione utente ...
            =======
            ... righe versione pacchetto ...
            >>>>>>> OFFICIAL

        Ritorna il testo completo del file con marcatori inseriti.
        """
        ...

    def has_conflict_markers(self, text: str) -> bool:
        """
        Ritorna True se il testo contiene marcatori di conflitto non risolti.
        Usato da scf_finalize_update per la validazione finale.
        """
        ...
```

### 4.3 Algoritmo interno di diff3_merge

L'algoritmo usa `difflib.SequenceMatcher` dalla libreria standard Python. Nessuna dipendenza esterna.

#### Fase 1 — Calcolo dei delta

Vengono calcolati due diff separati:

```
delta_ours   = diff(BASE, OURS)    # cosa ha cambiato l'utente
delta_theirs = diff(BASE, THEIRS)  # cosa ha cambiato il pacchetto
```

Ogni delta è espresso come lista di operazioni `(tag, i1, i2, j1, j2)` nel formato `SequenceMatcher.get_opcodes()`:

- `equal`  — blocco invariato
- `replace` — blocco sostituito
- `delete` — righe rimosse
- `insert`  — righe aggiunte

#### Fase 2 — Intersezione dei range

I range di BASE toccati da `delta_ours` e `delta_theirs` vengono confrontati. Caso per caso:

```
Caso 1: solo OURS cambia un range BASE → applica OURS, nessun conflitto
Caso 2: solo THEIRS cambia un range BASE → applica THEIRS, nessun conflitto
Caso 3: entrambi cambiano lo stesso range BASE → CONFLITTO
Caso 4: nessuno cambia un range BASE (equal in entrambi) → copia BASE tal quale
Caso 5: entrambi fanno la stessa modifica identica → applica una volta (merge pulito)
```

Il Caso 5 è importante: se l'utente e il pacchetto hanno apportato la stessa modifica allo stesso blocco, il merge è clean e il contenuto viene incluso una sola volta.

Regola esplicita (deduplicazione): quando si verifica il pattern "OURS == THEIRS != BASE" (cioè l'utente e il pacchetto hanno applicato la stessa modifica rispetto a BASE), il motore tratta la sezione come un merge "clean" e applica il delta una sola volta nel risultato finale. Questa regola evita duplicazioni di contenuto e garantisce che il testo condiviso non compaia due volte nel file risultante.

#### Fase 3 — Costruzione del risultato

Le sezioni vengono concatenate in ordine mantenendo la sequenza originale di BASE. Per i conflitti viene istanziato un `MergeConflict` con il testo delle tre versioni e le righe di contesto adiacenti.

#### Fase 4 — Classificazione finale

- `identical` se OURS e THEIRS sono identici a BASE (nessun delta in nessuno dei due).
- `clean` se il merge ha prodotto un testo senza conflitti.
- `conflict` se almeno un `MergeConflict` è presente.
- `binary_skip` se il file non è testo UTF-8 (rilevato prima di avviare il merge).

### 4.4 Gestione del frontmatter YAML

Il frontmatter YAML (blocco tra `---` iniziale e `---` finale) viene trattato come una regione speciale a priorità utente. La regola è:

1. Se solo il pacchetto modifica un campo frontmatter → applica.
2. Se solo l'utente modifica un campo frontmatter → preserva.
3. Se entrambi modificano lo stesso campo → CONFLITTO esplicito, NON risolto automaticamente in nessuna modalità (inclusa `auto`).
4. Se il pacchetto aggiunge un nuovo campo non presente in BASE né in OURS → applica (add-only).

Il frontmatter non viene trattato come YAML strutturato a livello del `MergeEngine`; viene trattato come blocco di testo con righe chiave-valore. Questo mantiene la semplicità dell'implementazione e la correttezza per i casi non-YAML-standard presenti nei file `.agent.md`.

### 4.5 Limiti di progetto

- `MergeEngine` non conosce la semantica dei file Markdown SCF (agenti, prompt, istruzioni).
- La validazione semantica (validator post-merge AI) è responsabilità della sezione 8.
- File con encoding non UTF-8, file binari, e file vuoti vengono gestiti come casi edge (sezione 13).

---

## 5. Flusso operativo detect → merge → report

### 5.1 Flusso generale (tutte le modalità)

```
[scf_update_package(package_id, conflict_mode)]
        |
        v
[1. Fetch manifest remoto del pacchetto (RegistryClient)]
        |
        v
[2. _classify_install_files(package_id, files)]
        |
        |-- create_new            --> scrive, aggiorna snapshot, aggiorna manifest
        |-- update_tracked_clean  --> sovrascrive, aggiorna snapshot, aggiorna manifest
        |-- conflict_cross_owner  --> ERRORE BLOCCANTE (nessuna scrittura)
        |-- conflict_untracked    --> dipende da conflict_mode (abort/replace)
        |
        `-- preserve_tracked_modified -->
                    |
                    v
             [3. Carica snapshot BASE da runtime/snapshots/]
                    |
                    | BASE assente?
                    |--- Sì --> usa THEIRS come BASE (merge degradato, registra nel report)
                    |--- No --> procede con merge completo
                    |
                    v
             [4. Legge OURS dal filesystem]
                    |
                    v
             [5. Scarica THEIRS dal registry (RegistryClient.fetch_raw_file)]
                    |
                    v
             [6. MergeEngine.diff3_merge(base, ours, theirs)]
                    |
                    |-- status == identical --> nessuna azione (già aggiornato)
                    |-- status == clean     --> scrive risultato, aggiorna manifest e snapshot
                    |
                    `-- status == conflict -->
                            |
                            v
                     [7. Dispatcher per modalità]
                            |
                            |-- manual   --> render_with_markers, scrive file, apre sessione
                            |-- auto     --> scf_resolve_conflict_ai, valida, scrive, chiude sessione
                            `-- assisted --> crea sessione, aspetta approvazione utente
```

### 5.2 Modalità manual

```
Utente invoca: scf_update_package(package_id, conflict_mode="manual")
        |
        v
[MergeEngine rileva conflitti]
        |
        v
[render_with_markers produce il file con marcatori]
        |
        v
[Il file viene scritto su disco con i marcatori]
        |
        v
[Viene creata una sessione merge in runtime/merge-sessions/<session-id>.json]
        |
        v
[Tool ritorna: session_id, file_list, istruzioni per la risoluzione]
        |
        v
[Utente modifica manualmente i file, rimuove i marcatori]
        |
        v
Utente invoca: scf_finalize_update(session_id)
        |
        v
[MergeEngine.has_conflict_markers() controlla ogni file della sessione]
        |
        |-- Marcatori trovati --> ritorna errore con lista file non risolti
        `-- Nessun marcatore  -->
                    |
                    v
              [Aggiorna SHA nel manifest per ogni file risolto]
                    |
                    v
              [Aggiorna snapshot BASE con il risultato finale]
                    |
                    v
              [Chiude la sessione (stato: "finalized")]
                    |
                    v
              [Ritorna report finale]
```

### 5.3 Modalità auto

```
Utente invoca: scf_update_package(package_id, conflict_mode="auto")
        |
        v
[MergeEngine rileva conflitti]
        |
        v
[Viene creata una sessione merge in runtime/merge-sessions/<session-id>.json]
        |
        v
[Per ogni file con conflitti]
        |
        v
[scf_resolve_conflict_ai(session_id, conflict_id) invocato internamente]
        |
        v
[LLM produce risoluzione testuale per ogni MergeConflict]
        |
        v
[Validator post-merge AI (sezione 8) — 3 check]
        |
        |-- Almeno un check fallisce --> il file viene degradato a manual
        `-- Tutti i check passano  -->
                    |
                    v
              [File scritto su disco]
                    |
                    v
              [Manifest e snapshot aggiornati]
        |
        v
[Sessione chiusa (stato: "auto_completed")]
        |
        v
[Report finale: auto_resolved, degraded_to_manual, failed]
```

### 5.4 Modalità assisted

```
Utente invoca: scf_update_package(package_id, conflict_mode="assisted")
        |
        v
[MergeEngine rileva conflitti]
        |
        v
[Viene creata una sessione merge stateful]
        |
        v
[Per ogni file con conflitti]
        |
        v
[scf_resolve_conflict_ai(session_id, conflict_id) propone risoluzione]
        |
        v
[Tool ritorna la proposta all'utente]
        |
        v
Utente invoca: scf_approve_conflict(session_id, conflict_id)
           oppure: scf_reject_conflict(session_id, conflict_id)
        |
        |-- Approvato --> proposta applicata al buffer del file
        `-- Rifiutato --> conflitto salvato come manual per quel conflict_id
        |
        v
[Quando tutti i conflitti della sessione sono risolti o rifiutati]
        |
        v
Utente invoca: scf_finalize_update(session_id)
        |
        v
[Per i file con conflitti rifiutati: render_with_markers → scrittura con marcatori]
[Per i file con conflitti approvati: scrittura del buffer risolto]
        |
        v
[Aggiornamento manifest e snapshot]
        |
        v
[Sessione chiusa (stato: "finalized")]
        |
        v
[Report finale con dettaglio per conflitto]
```

---

## 6. Tool MCP nuovi

### 6.1 Estensione di scf_update_package

**Modifica**: aggiunta di `conflict_mode` con i nuovi valori `manual`, `auto`, `assisted` (oltre agli esistenti `abort` e `replace`).

```python
@mcp.tool()
async def scf_update_package(
    package_id: str,
    conflict_mode: str = "abort",
) -> dict[str, Any]:
    """
    Aggiorna un singolo pacchetto SCF nel workspace.

    conflict_mode (default "abort"):
        abort    -- se esistono file modificati dall'utente, interrompe senza scrivere.
        replace  -- sovrascrive i file modificati dall'utente con la versione ufficiale.
        manual   -- inserisce marcatori di conflitto nei file, apre sessione.
        auto     -- risolve automaticamente i conflitti via LLM, con validazione.
        assisted -- propone risoluzione LLM per ogni conflitto, attende approvazione.

    Ritorna:
        dict con campi: success, session_id (se modalità stateful), merged_files,
        requires_user_resolution, resolution_applied, conflicts_detected, ...
    """
```

**Comportamento esteso per preserve_tracked_modified**:
- `abort`: nessuna modifica (comportamento invariato).
- `replace`: sovrascrive (comportamento invariato).
- `manual`: genera file con marcatori, crea sessione, ritorna `session_id`.
- `auto`: invoca pipeline AI, ritorna risultato direttamente.
- `assisted`: crea sessione con proposte AI, ritorna `session_id` e lista conflitti.

**Validazione del conflict_mode**:

```python
SUPPORTED_CONFLICT_MODES = {"abort", "replace", "manual", "auto", "assisted"}
if conflict_mode not in SUPPORTED_CONFLICT_MODES:
    return _build_install_result(
        False,
        error=f"Unsupported conflict_mode '{conflict_mode}'. "
              f"Supported: {', '.join(sorted(SUPPORTED_CONFLICT_MODES))}.",
        package=package_id,
        conflict_mode=conflict_mode,
    )
```

### 6.2 scf_resolve_conflict_ai

```python
@mcp.tool()
async def scf_resolve_conflict_ai(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Invoca l'LLM per proporre una risoluzione di un singolo conflitto.

    Parametri:
        session_id  -- ID della sessione merge attiva.
        conflict_id -- UUID del conflitto da risolvere (da MergeConflict.conflict_id).

    Comportamento:
        Legge il MergeConflict dalla sessione JSON.
        Costruisce un prompt strutturato con base_lines, ours_lines, theirs_lines
        e il contesto adiacente.
        Invoca il modello linguistico e restituisce la proposta come testo.
        Salva la proposta nella sessione (stato pendente di approvazione).

    Ritorna:
        {
          "success": bool,
          "session_id": str,
          "conflict_id": str,
          "proposed_lines": list[str],   # righe proposte dall'LLM
          "confidence": float,           # stima 0.0-1.0 della quality dell proposta
          "reasoning": str               # breve spiegazione della scelta dell'LLM
        }

    Errori:
        session_id non trovato o scaduto → success: False, error: "session_not_found"
        conflict_id non trovato nella sessione → success: False, error: "conflict_not_found"
        sessione non in stato attivo → success: False, error: "session_not_active"
    """
```

**Nota sul contesto LLM**: il prompt inviato all'LLM non deve includere path assoluti di sistema, SHA-256 o dati di sistema sensibili. Include solo: nome file relativo, testo BASE, OURS, THEIRS e contesto di 3 righe adiacenti.

### 6.3 scf_approve_conflict

```python
@mcp.tool()
async def scf_approve_conflict(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Approva la proposta AI per un conflitto nella modalità assisted.

    La proposta deve essere stata generata da scf_resolve_conflict_ai.
    L'approvazione applica le proposed_lines al buffer del file in memoria
    (la sessione) senza scrivere su disco.
    La scrittura avviene solo al momento di scf_finalize_update.

    Ritorna:
        {
          "success": bool,
          "session_id": str,
          "conflict_id": str,
          "approved": True,
          "remaining_conflicts": int   # conflitti ancora da risolvere nella sessione
        }
    """
```

### 6.4 scf_reject_conflict

```python
@mcp.tool()
async def scf_reject_conflict(
    session_id: str,
    conflict_id: str,
) -> dict[str, Any]:
    """
    Rifiuta la proposta AI per un conflitto nella modalità assisted.

    Il conflitto viene marcato come "manual" nella sessione.
    Al momento di scf_finalize_update, verrà inserito il marcatore di conflitto
    nel file corrispondente, per risoluzione manuale successiva.

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

### 6.5 scf_finalize_update

```python
@mcp.tool()
async def scf_finalize_update(
    session_id: str,
) -> dict[str, Any]:
    """
    Finalizza una sessione di merge e scrive i file risolti su disco.

    Operazioni eseguite:
        1. Legge la sessione da runtime/merge-sessions/<session_id>.json.
        2. Per ogni file della sessione:
           - Se tutti i conflitti sono approvati: scrive il buffer risolto.
           - Se alcuni conflitti sono "manual": scrive con marcatori per quei blocchi.
        3. Verifica che nessun file approvato contenga ancora marcatori (MergeEngine.has_conflict_markers).
        4. Aggiorna il manifest per ogni file scritto (nuovo SHA, nuova versione pacchetto).
        5. Aggiorna lo snapshot BASE con il contenuto scritto.
        6. Imposta lo stato della sessione su "finalized".

    Ritorna:
        {
          "success": bool,
          "session_id": str,
          "written_files": list[str],
          "manual_pending": list[str],   # file con marcatori ancora presenti
          "manifest_updated": bool,
          "snapshot_updated": bool,
          "error": str | None
        }

    Pre-condizioni:
        La sessione deve esistere e non essere già finalizzata.
        I file su disco non devono essere stati modificati dall'apertura della sessione.
        Se su disco sono stati rilevati cambiamenti fuori sessione, l'operazione viene
        interrotta con error: "external_modification_detected".
    """
```

---

## 7. Sessione di merge stateful

### 7.1 Percorso e formato

Le sessioni vengono salvate in:

```
.github/runtime/merge-sessions/<session-id>.json
```

Il `session_id` è un UUID v4 generato al momento della creazione della sessione.

### 7.2 Schema JSON della sessione

```json
{
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "package_id": "scf-master-codecrafter",
  "target_version": "1.1.0",
  "conflict_mode": "assisted",
  "created_at": "2026-04-14T10:00:00Z",
  "expires_at": "2026-04-14T11:00:00Z",
  "status": "active",
  "files": [
    {
      "file_rel": "agents/spark-guide.agent.md",
      "base_snapshot_path": "runtime/snapshots/scf-master-codecrafter/agents/spark-guide.agent.md",
      "original_sha_at_session_open": "abc123...",
      "merge_status": "conflict",
      "conflicts": [
        {
          "conflict_id": "c1a2b3c4-...",
          "start_line": 15,
          "end_line": 22,
          "base_lines": ["tools:", "  - scf_get_workspace_info"],
          "ours_lines": ["tools:", "  - scf_get_workspace_info", "  - scf_my_custom_tool"],
          "theirs_lines": ["tools:", "  - scf_get_workspace_info", "  - scf_list_agents"],
          "context_before": ["---", ""],
          "context_after": ["", "## Istruzioni"],
          "resolution_status": "pending",
          "proposed_lines": null,
          "approved": null
        }
      ]
    }
  ],
  "clean_files_written": ["instructions/model-policy.instructions.md"],
  "finalized_at": null
}
```

### 7.3 Stati della sessione

```
active       → sessione aperta, conflitti in attesa di risoluzione
auto_completed → tutti i conflitti risolti automaticamente (modalità auto)
finalized    → scf_finalize_update completato con successo
expired      → timeout superato, sessione non più utilizzabile
orphaned     → crash rilevato, sessione in stato inconsistente
```

### 7.4 Timeout e cleanup

**Timeout**: le sessioni scadono dopo 60 minuti dalla creazione (configurabile). Il campo `expires_at` è impostato al momento della creazione.

**Cleanup automatico**: all'avvio dei tool `scf_update_package`, `scf_apply_updates` e `scf_finalize_update`, il motore verifica la presenza di sessioni scadute o orfane e le sposta in uno stato `expired`/`orphaned` senza eliminarle. I file sessione non vengono eliminati automaticamente: è compito dell'amministratore o di un tool futuro di manutenzione.

**Rilevamento crash**: se il campo `finalized_at` è `null` e `expires_at` è nel passato, la sessione è considerata orfana. Il motore non riprende mai automaticamente una sessione orfana; deve essere scartata dall'utente o da un tool esplicito.

**Nota helper cleanup**: il meccanismo di pulizia delle sessioni è implementato come helper interno invocato dai tool session-related (cleanup chiamato internamente da `scf_update_package`, `scf_apply_updates`, `scf_finalize_update`). `scf_cleanup_sessions` NON è un tool MCP pubblico in questa release 2.0.0; non va esposto come entrypoint tool nel registro pubblico. Questa scelta mantiene il conteggio finale dei tool a 33 (vedi piano implementativo).

**Conflitto sessione concorrente**: non possono esistere due sessioni `active` per lo stesso `package_id` contemporaneamente. Prima di creare una nuova sessione, il motore verifica l'assenza di sessioni attive per il pacchetto target.

### 7.6 Atomicità delle scritture JSON di sessione

Tutte le scritture sui file di sessione (`.json`) devono essere atomiche. L'implementazione obbligatoria usa la tecnica "write-to-temp-then-rename" con un file temporaneo creato nella STESSA directory del file di destinazione e il rename effettuato tramite `os.replace()` (o equivalente), per garantire compatibilità su Windows e comportamento deterministico nei test.

Esempio (pseudocodice):

```
tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
with open(tmp_path, "w", encoding="utf-8") as f:
  json.dump(data, f, ensure_ascii=False, indent=2)
os.replace(tmp_path, target_path)
```

Note operative:
- Il file temporaneo deve essere creato nella stessa directory del target per evitare problemi cross-filesystem su Windows.
- Se un file `.tmp` esiste già all'avvio, il motore lo considera un artefatto di scrittura interrotta e la sessione relativa deve essere marcata `orphaned` o riesaminata dal `cleanup`.
- Questa regola si applica anche alle scritture atomiche degli snapshot e alle scritture di sessione nella `MergeSessionManager`.

### 7.5 Sicurezza delle sessioni

- Il file di sessione non deve contenere credenziali, token, SHA di dati sensibili o path di sistema assoluti al di fuori del workspace.
- I percorsi nel JSON sono sempre relativi a `.github/`.

---

## 8. Validator post-merge AI

I validator post-merge vengono eseguiti dopo che il LLM ha proposto una risoluzione, prima di scrivere il file su disco. Tutti e tre i check devono passare; un singolo fallimento degrada il file alla modalità `manual`.

### 8.1 Check 1 — Strutturale (Markdown valido, frontmatter intatto)

**Obiettivo**: verificare che il testo risultante sia un Markdown ben formato e che il blocco frontmatter YAML sia sintatticamente valido.

**Regole**:
- Il file deve iniziare con `---` su riga separata se il file BASE aveva frontmatter.
- Il blocco frontmatter deve chiudersi con `---` su riga separata.
- Non devono esserci marcatori di conflitto (`<<<<<<<`, `=======`, `>>>>>>>`) nel testo.
- Il numero di heading `#` nel file risultante non deve essere zero se il file BASE ne aveva almeno uno (il validator non permette elminazione totale degli heading).

**Implementazione**: regex su testo, nessuna dipendenza esterna, nessuna richiesta LLM.

```python
def validate_structural(merged_text: str, base_text: str) -> tuple[bool, str]:
    """
    Ritorna (True, "") se OK oppure (False, "descrizione problema") se fallisce.
    """
```

### 8.2 Check 2 — Completezza (heading preservati)

**Obiettivo**: verificare che le sezioni principali del file non siano state eliminate dal merge.

**Regole**:
- Ogni heading di livello H1 e H2 presente nel file OURS deve comparire nel risultato del merge.
- L'ordine degli heading non è vincolato.
- Heading aggiunti da THEIRS e non presenti in OURS sono accettati.

**Motivazione**: i template degli agenti SPARK hanno heading strutturalmente significativi (es. `## Istruzioni contestuali`, `## Skill di riferimento`). Un merge mal riuscito che elimina heading farebbe perdere sezioni operative all'agente.

**Implementazione**: estrazione heading con regex, confronto set.

```python
def validate_completeness(merged_text: str, ours_text: str) -> tuple[bool, str]:
    """
    Ritorna (True, "") se tutti gli H1/H2 di OURS sono presenti nel risultato.
    """
```

### 8.3 Check 3 — Coerenza tool (blocco tools: nel frontmatter .agent.md)

**Obiettivo**: verificare che il blocco `tools:` nel frontmatter dei file `.agent.md` sia coerente e completo dopo il merge.

**Regole**:
- Se il file ha estensione `.agent.md`, il frontmatter deve contenere una chiave `tools:` con almeno un elemento.
- Nessun tool presente in OURS deve essere stato rimosso dal risultato del merge (i tool dell'utente non possono sparire).
- I tool aggiunti da THEIRS sono accettati.
- La duplicazione di tool è segnalata come warning ma non come errore bloccante.

**Implementazione**: parsing semplificato del blocco `tools:` come lista YAML inline, senza libreria YAML esterna per mantenere la portabilità.

```python
def validate_tool_coherence(merged_text: str, ours_text: str) -> tuple[bool, str]:
    """
    Applicabile solo ai file .agent.md.
    Ritorna (True, "") se il blocco tools è coerente.
    """
```

### 8.4 Orchestrazione dei validator

```python
def run_post_merge_validators(
    merged_text: str,
    base_text: str,
    ours_text: str,
    file_rel: str,
) -> dict[str, Any]:
    """
    Esegue tutti i validator in sequenza.
    Ritorna un dict con:
        passed: bool
        results: list di {"check": str, "passed": bool, "message": str}
    """
    results = []
    v1_ok, v1_msg = validate_structural(merged_text, base_text)
    results.append({"check": "structural", "passed": v1_ok, "message": v1_msg})
    v2_ok, v2_msg = validate_completeness(merged_text, ours_text)
    results.append({"check": "completeness", "passed": v2_ok, "message": v2_msg})
    if file_rel.endswith(".agent.md"):
        v3_ok, v3_msg = validate_tool_coherence(merged_text, ours_text)
        results.append({"check": "tool_coherence", "passed": v3_ok, "message": v3_msg})
    passed = all(r["passed"] for r in results)
    return {"passed": passed, "results": results}
```

---

## 9. Policy multi-owner

### 9.1 Scenario

Due pacchetti installati nello stesso workspace dichiarano ownership sullo stesso file. Il sistema attuale usa `file_ownership_policy: "error"` a livello globale di pacchetto, bloccando ogni tentativo di sovrapposizione.

Il design del merge a 3-vie introduce una policy granulare per-file che permette scenari cooperativi o delegati tra pacchetti.

### 9.2 Dove viene dichiarata la policy per-file

La policy per-file viene dichiarata nel `package-manifest.json` dei pacchetti SCF, nella sezione `file_policies`:

```json
{
  "id": "scf-master-codecrafter",
  "version": "1.0.0",
  "file_ownership_policy": "error",
  "file_policies": [
    {
      "path": ".github/copilot-instructions.md",
      "policy": "extend",
      "section_marker": "<!-- SCF:SECTION:scf-master-codecrafter -->"
    },
    {
      "path": ".github/agents/spark-guide.agent.md",
      "policy": "delegate",
      "delegate_to": "scf-master-codecrafter"
    }
  ]
}
```

Il campo `file_ownership_policy` a livello root rappresenta il default per tutti i file non elencati in `file_policies`. Se un file è elencato in `file_policies`, la policy per-file sovrascrive quella globale.

### 9.3 Policy disponibili

#### Policy `error` (default)

Il file non può essere condiviso tra pacchetti. Se un secondo pacchetto dichiara ownership sullo stesso file, l'installazione viene bloccata con `conflict_cross_owner`.

Comportamento invariato rispetto all'attuale.

#### Policy `extend`

Il file appende le proprie sezioni a una sezione marcata nel file, senza sovrascrivere il contenuto degli altri pacchetti o dell'utente. Ogni pacchetto scrive solo all'interno del proprio marcatore sezione.

Formato dei marcatori:

```
<!-- SCF:SECTION:scf-master-codecrafter:BEGIN -->
... contenuto del pacchetto master ...
<!-- SCF:SECTION:scf-master-codecrafter:END -->
```

**Regole di merge `extend`**:
- Solo i byte tra `BEGIN` e `END` del proprio marcatore possono essere modificati dal pacchetto.
- Il motore non tocca le sezioni degli altri pacchetti o le sezioni non marcate (proprietà utente).
- Se la sezione marcata non esiste nel file, viene aggiunta in fondo al file.
- Se il file stesso non esiste, viene creato con la sola sezione del pacchetto.
- Un aggiornamento di pacchetto con policy `extend` non avvia un merge a 3-vie: cerca e aggiorna solo la propria sezione.

#### Policy `delegate`

Il file è di proprietà logica di un altro pacchetto (`delegate_to`). Il pacchetto corrente non dichiara ownership esclusiva e non aggiorna il file.

**Utilizzo**: un plugin specializzato può dichiarare che certi file del framework base vengono aggiornati solo dal pacchetto master, evitando conflitti accidentali.

**Regole di merge `delegate`**:
- Il pacchetto con policy `delegate` salta il file nella propria lista di file da installare/aggiornare.
- Non scrive snapshot per il file delegato.
- Il manifest traccia il file solo sotto il pacchetto `delegate_to`.

### 9.4 Impatto su _classify_install_files

La funzione `_classify_install_files` deve essere estesa per leggere le policy per-file dal manifest remoto e applicare la classificazione corretta:

```
conflict_cross_owner    → policy "error" (default) per file con più owner
extend_section          → policy "extend": solo la sezione del pacchetto viene aggiornata
delegate_skip           → policy "delegate": file saltato per questo pacchetto
```

La chiamata a `get_file_owners()` rimane il punto di rilevamento dei conflitti. La policy per-file viene consultata solo se `conflict_cross_owner` inizialmente sussisterebbe.

### 9.5 Formato marcatori sezione

```
<!-- SCF:SECTION:<package-id>:BEGIN -->
<contenuto del pacchetto>
<!-- SCF:SECTION:<package-id>:END -->
```

I marcatori devono essere su righe proprie. Il parser del motore usa regex per isolare le sezioni. I marcatori sono visibili nel sorgente HTML ma non nel rendering Markdown: questo è intenzionale per non interrompere la leggibilità visuale del documento.

Per i file `.agent.md` e file di configurazione YAML, i marcatori sezione non sono supportati perché strutturalmente vincolanti. Per quei file, la policy `extend` non è applicabile; è applicabile solo `error` o `delegate`.

---

## 10. Impatto su scf_bootstrap_workspace e scf_install_package

### 10.1 scf_bootstrap_workspace

**Comportamento attuale**: copia i file base del workspace (agenti, istruzioni, guide) senza tracking manifest completo. Preserva i file già esistenti.

**Modifica richiesta**: dopo la scrittura di ogni file bootstrap, il motore deve salvare lo snapshot BASE nella posizione standard:

```
.github/runtime/snapshots/<bootstrap-package-id>/<file-rel>/
```

Il `bootstrap-package-id` per i file di bootstrap è `__bootstrap__` (identificatore riservato, non corrisponde a un pacchetto registrato).

**Impatto**: nessuna modifica al contratto di ritorno di `scf_bootstrap_workspace`. L'operazione snapshot è trasparente.

**Comportamento su clash**: se un file bootstrap già esiste con modifiche utente, il comportamento di skip rimane invariato. Non viene creato lo snapshot per file skippati.

### 10.2 scf_install_package

**Comportamento attuale**: per ogni file scritto su disco (sia `create_new` che `update_tracked_clean`), aggiorna il manifest tramite `upsert_many`.

**Modifica richiesta**: dopo `upsert_many`, viene aggiunto un passo di snapshot:

```python
# Dopo upsert_many(...)
for file_rel, dest in written_files:
    snapshot_path = snapshot_root / package_id / file_rel
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_bytes(dest.read_bytes())
```

Dove `snapshot_root = self._ctx.github_root / "runtime" / "snapshots"`.

**Atomicità**: se la scrittura su disco di un file fallisce, né il manifest né lo snapshot vengono aggiornati per quel file. Il rollback atomico esistente non viene modificato.

**File già con snapshot**: se uno snapshot esistente viene aggiornato (scenario `update_tracked_clean`), il vecchio snapshot viene rimpiazzato. Non si mantiene una storia di versioni precedenti degli snapshot; per quello esiste il version control del progetto utente.

### 10.3 scf_remove_package

**Modifica richiesta**: al completamento della rimozione, la directory `runtime/snapshots/<package-id>/` viene eliminata se esiste.

```python
snapshot_dir = self._ctx.github_root / "runtime" / "snapshots" / package_id
if snapshot_dir.exists():
    shutil.rmtree(snapshot_dir)
```

I file nella directory snapshot che appartengono anche ad altri pacchetti (scenario raro, coperto da policy `extend`) non vengono eliminati. Il motore verifica l'ownership prima dell'eliminazione.

---

## 11. Contratto di risultato

### 11.1 Estensione di _build_install_result

Il contratto JSON di ritorno esistente viene esteso con i seguenti campi per supportare le modalità merge:

```json
{
  "success": true,
  "package": "scf-master-codecrafter",
  "version": "1.1.0",
  "conflict_mode": "assisted",

  "installed": ["agents/spark-guide.agent.md"],
  "preserved": [],
  "removed_obsolete_files": [],
  "preserved_obsolete_files": [],

  "conflicts_detected": ["agents/spark-orchestrator.agent.md"],
  "blocked_files": [],
  "replaced_files": [],

  "merged_files": ["instructions/model-policy.instructions.md"],
  "merge_clean": ["instructions/model-policy.instructions.md"],
  "merge_conflict": ["agents/spark-orchestrator.agent.md"],

  "requires_user_resolution": true,
  "resolution_applied": "assisted",

  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "session_status": "active",
  "session_expires_at": "2026-04-14T11:00:00Z",

  "snapshot_written": ["agents/spark-guide.agent.md"],
  "snapshot_skipped": []
}
```

**Campi nuovi**:

| Campo | Tipo | Significato |
|---|---|---|
| `merge_clean` | `list[str]` | File con merge completato senza conflitti |
| `merge_conflict` | `list[str]` | File con conflitti che richiedono risoluzione |
| `session_id` | `str\|null` | Presente solo per modalità stateful (manual, assisted) |
| `session_status` | `str\|null` | Stato sessione: `active`, `auto_completed`, ... |
| `session_expires_at` | `str\|null` | Scadenza sessione ISO 8601 |
| `snapshot_written` | `list[str]` | Snapshot BASE creati o aggiornati |
| `snapshot_skipped` | `list[str]` | File per cui lo snapshot è stato saltato (es. binari) |

### 11.2 Contratto di ritorno di scf_finalize_update

```json
{
  "success": true,
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "written_files": ["agents/spark-guide.agent.md"],
  "manual_pending": [],
  "manifest_updated": true,
  "snapshot_updated": true,
  "validator_results": {
    "agents/spark-guide.agent.md": {
      "passed": true,
      "results": [
        {"check": "structural", "passed": true, "message": ""},
        {"check": "completeness", "passed": true, "message": ""},
        {"check": "tool_coherence", "passed": true, "message": ""}
      ]
    }
  }
}
```

### 11.3 Compatibilità con contratti esistenti

I campi già esistenti in `_build_install_result` non vengono rinominati né eliminati:

- `success`, `installed`, `preserved`, `removed_obsolete_files`, `preserved_obsolete_files`
- `conflicts_detected`, `blocked_files`, `replaced_files`, `merged_files`
- `requires_user_resolution`, `resolution_applied`

I nuovi campi sono aggiunti come estensioni additive. I client che consumano la risposta ignorando i campi sconosciuti non saranno impattati.

### 11.4 Mapping dettagliato e casi di valore null/empty

Questo paragrafo mappa esplicitamente il contratto esistente `_build_install_result` con i nuovi campi introdotti dal sistema di merge e specifica i casi in cui i campi possono risultare vuoti o `null`.

- `success` (esistente): riflette l'esito complessivo dell'operazione batch; `False` indica errore bloccante (es. `conflict_cross_owner`), `True` anche se sono presenti conflitti risolvibili tramite sessione.
- `installed` / `preserved` (esistenti): rispettano il comportamento storico. Un file che è stato merge-committato con successo compare in `installed` o in `merged_files` a seconda del percorso di applicazione.
- `merged_files` (esistente): viene mantenuto come elenco generale di file su cui è stato effettuato un merge (sia clean che conflict). Dal punto di vista semantico: `merged_files == merge_clean ∪ merge_conflict`.
- `merge_clean` (nuovo): lista di file per cui `MergeEngine` ha prodotto un risultato `clean` e il sistema ha scritto il contenuto risultante su disco. Può essere vuota (`[]`) se nessun merge è stato eseguito o se tutti i merge hanno generato conflitti.
- `merge_conflict` (nuovo): lista di file con conflitti non risolti automaticamente. Se vuota (`[]`) non è necessario intervento utente. Se non presente o `null`, il chiamante deve considerare che non sono state avviate sessioni stateful.
- `conflicts_detected` (esistente): rimane una lista di file dove sono stati individuati conflitti; in pratica è sinonimo iniziale di `merge_conflict` al termine della fase di detection.
- `requires_user_resolution` (esistente): `True` se `merge_conflict` non è vuoto o se `resolution_applied` indica che è necessaria interazione (`manual` o `assisted`). Può essere `False` anche se `conflicts_detected` contiene voci, quando la modalità `auto` ha risolto tutti i conflitti con successo.
- `resolution_applied` (esistente): stringa che indica quale strategia è stata applicata per i file nel batch. Valori possibili: `none`, `replace`, `manual`, `auto`, `assisted`. Se `none`, non è stata applicata alcuna risoluzione; se `manual` o `assisted`, è possibile che `session_id` sia presente.
- `session_id` (nuovo): `str` o `null`. Presente solo per operazioni stateful (`manual`, `assisted`) o quando `auto` ha creato una sessione per tracking. `null` per operazioni sincrone non-stateful (`abort`, `replace`) o quando non è stata creata alcuna sessione.
- `session_status` (nuovo): `str` o `null`. Valori: `active`, `auto_completed`, `finalized`, `expired`, `orphaned`. `null` se `session_id` è `null`.
- `session_expires_at` (nuovo): timestamp ISO 8601 o `null`. Presente solo se `session_id` non è `null`.
- `snapshot_written` (nuovo): lista dei file per cui lo snapshot BASE è stato creato o aggiornato durante l'operazione. Può essere vuota `[]` se non sono stati creati snapshot in questo batch.
- `snapshot_skipped` (nuovo): lista dei file per cui lo snapshot non è stato creato (file binari, errori I/O). Può essere vuota `[]` se tutti gli snapshot sono stati scritti.
- `validator_results` (nuovo, opzionale): presente principalmente nel ritorno di `scf_finalize_update` e nelle risposte `auto`/`finalize`. È una mappa per-file con l'esito dei validator post-merge. Se non popolato, significa che non sono stati eseguiti validator per quel batch.

Alcune regole pratiche di interpretazione:
- Se `session_id` è non-`null` ma `merged_files` è vuoto, la sessione è stata aperta ma non sono state scritture definitive (es. sessione `active` in attesa di finalize).
- `merged_files` mantiene la compatibilità con client esistenti: i client che leggono solo `merged_files` vedranno l'elenco generale; i client aggiornati dovrebbero preferire `merge_clean` e `merge_conflict` per dettagli.
- I campi non applicabili sono preferibilmente restituiti come valori vuoti (`[]`) o `null` per evitare ambiguità: liste vuote per insiemi, `null` per singoli identificatori (es. `session_id`).

## 12. Vincoli di sicurezza e accessibilità

### 12.1 Sicurezza — OWASP Top 10 rilevanti

**A01 — Broken Access Control**
- Gli snapshot BASE sono file locali nel workspace utente. Non vengono mai esposti come risorse MCP esterne.
- I session file in `runtime/merge-sessions/` non devono essere leggibili tramite `scf://` resource URI senza autenticazione esplicita.

**A03 — Injection**
- I contenuti di BASE, OURS e THEIRS vengono passati all'LLM come testo sanitizzato, mai come template interpolati con f-string non escapate.
- Il `file_rel` usato per costruire i percorsi snapshot viene validato contro path traversal (`..`, percorsi assoluti, separatori Windows/Unix misti) prima di qualsiasi operazione su disco.

```python
def _validate_rel_path(file_rel: str) -> bool:
    """Ritorna False se il path contiene sequenze di traversal o è assoluto."""
    p = Path(file_rel)
    if p.is_absolute():
        return False
    if ".." in p.parts:
        return False
    return True
```

**A04 — Insecure Design**
- Il prompt LLM per `scf_resolve_conflict_ai` non deve includere nomi di file assoluti, SHA di commit, token di accesso o variabili d'ambiente.
- La risposta LLM viene trattata sempre come testo non affidabile: i validator post-merge verificano strutturalmente il risultato prima di scriverlo su disco.

**A08 — Software and Data Integrity Failures**
- Lo snapshot BASE non è firmato digitalmente in questa versione. Il rischio di manomissione è mitigato dal fatto che lo snapshot risiede nello stesso repository dell'utente e qualsiasi modifica è visibile nel version control.
- Se il sistema di merge è critico per la sicurezza, una versione futura può aggiungere HMAC o firme sui snapshot.

### 12.2 Dati sensibili nelle snapshot

Gli snapshot non devono includere:
- Token di accesso o credenziali (se un file agente le contiene, è un problema di design separato).
- Path assoluti di sistema al di fuori del workspace.
- Informazioni personali dell'utente non presenti nei file sorgente.

Il motore non filtra il contenuto degli snapshot: copia byte-per-byte dal file origine. La responsabilità del contenuto è dei package maintainer.

### 12.3 Accessibilità (NVDA-friendly)

- Tutti i report JSON ritornati dai tool sono navigabili con screen reader attraverso il lettore di output di VS Code.
- I marcatori di conflitto (`<<<<<<<`, `=======`, `>>>>>>>`) sono testo ASCII puro, leggibili da screen reader.
- I diagrammi in questo documento sono in formato testo ASCII (non immagini, non HTML).
- Il documento non usa tabelle HTML; usa solo tabelle Markdown.
- I file sessione e gli snapshot sono UTF-8 senza BOM.
- Nessun output usa colori ANSI o caratteri di controllo terminale.

### 12.4 No regressioni screen reader

Il sistema di merge non modifica il comportamento degli agenti SPARK a runtime. I file `.agent.md` scritti dal merge contengono gli stessi heading e frontmatter letti dagli agenti. Qualsiasi modifica strutturale è bloccata dai validator post-merge (sezione 8).

---

## 13. Casistiche edge

### 13.1 Manifest mancante o corrotto durante merge

**Scenario**: durante `scf_update_package`, il file `.github/.scf-manifest.json` è assente o contiene JSON malformato.

**Comportamento**: `ManifestManager.load()` ritorna `[]` in caso di errore (comportamento esistente). Con manifest vuoto, tutti i file risultano `untracked`. Il conflict_mode `merge`, `manual`, `auto`, `assisted` richiedono un manifesto valido per procedere (senza il manifest, la classificazione `preserve_tracked_modified` non è calcolabile).

**Risoluzione**: il tool interrompe con `success: False`, `error: "manifest_unreadable"`, suggerisce di eseguire `scf_verify_workspace` per diagnosi e ricostruzione.

### 13.2 Snapshot BASE assente (installazione pre-merge)

**Scenario**: un pacchetto è stato installato con engine < 2.0.0, prima del sistema di snapshot. La directory `runtime/snapshots/<package-id>/` non esiste.

**Comportamento (merge degradato)**:
- Il motore tenta il merge usando THEIRS come BASE (cioè BASE = THEIRS).
- Il result del merge con BASE = THEIRS e OURS ≠ THEIRS mostrerà **tutte le modifiche utente come conflitti di inserzione**, non come merge clean.
- Il file sarà classificato `merge_conflict` anche se l'utente aveva fatto modifiche non sovrapposte alla nuova versione.
- Il report include `"base_unavailable": true` per indicare la degradazione.
- Il campo `reasoning` nella risposta AI indica che la baseline è degradata.

**Alternativa proposta all'utente**: usare `conflict_mode="preserve"` (alias di `abort`) per primo, eseguire `scf_install_package` con `conflict_mode="replace"` e ricreare le modifiche utente in un secondo momento. Non c'è una opzione automatica sicura in questo scenario.

### 13.3 File binario o non-Markdown nel pacchetto

**Scenario**: il pacchetto include un file non UTF-8 (es. immagine, font, file binario).

**Rilevamento**: il motore tenta di decodificare il contenuto come UTF-8 con `errors="strict"`. Se fallisce, classifica il file come binario.

**Comportamento**:
- Per file binari, il `conflict_mode` merge non è applicabile.
- Il comportamento torna a `abort` (default) o `replace` se specificato esplicitamente.
- `MergeResult.status` = `binary_skip`.
- Lo snapshot non viene creato per file binari.
- Il report include il file in `snapshot_skipped`.

### 13.4 Conflitto su frontmatter YAML

**Scenario**: sia l'utente (OURS) che il nuovo pacchetto (THEIRS) modificano lo stesso campo nel frontmatter YAML di un file `.agent.md`.

**Comportamento**: come descritto nella sezione 4.4, i conflitti su campi frontmatter identici non vengono risolti automaticamente in nessuna modalità (inclusa `auto`). Il campo `auto` degrada a `manual` per il blocco frontmatter in conflitto. Il report lo indica esplicitamente:

```json
{
  "check": "structural",
  "passed": false,
  "message": "Frontmatter conflict on field 'tools': both OURS and THEIRS modified it. Manual resolution required."
}
```

### 13.5 Sessione merge orfana dopo crash

**Scenario**: il processo MCP crasha durante una sessione `active`. Al riavvio, la sessione è in stato `active` ma `expires_at` è nel passato (o la sessione non è mai stata aggiornata).

**Rilevamento**: all'avvio del tool `scf_update_package` o `scf_finalize_update`, il motore scansiona `runtime/merge-sessions/*.json` e segna come `orphaned` tutte le sessioni con `status="active"` e `expires_at` nel passato.

**Comportamento**: le sessioni orfane non vengono riprese. L'utente può eliminare manualmente il file JSON della sessione o attendere un futuro tool di cleanup. I file su disco scritti parzialmente durante la sessione (es. con marcatori) rimangono invariati.

### 13.6 file_ownership_policy: "error" vs nuova policy per-file

**Scenario**: il manifest globale di un pacchetto ha `file_ownership_policy: "error"` ma un file specifico ha `policy: "extend"` nella sezione `file_policies`.

**Regola di precedenza**: la policy per-file sovrascrive la policy globale. Se un file è in `file_policies` con policy `extend`, il conflitto multi-owner su quel file è gestito con `extend`, non con `error`.

**Caso ambiguo**: un pacchetto B non conosce la policy `extend` di un pacchetto A sullo stesso file. In questo caso, B troverà `conflict_cross_owner` con owner = A. Il motore segnala il conflitto al chiamante con le policy dei due pacchetti, e blocca l'installazione. La risoluzione richiede che B aggiorni il proprio manifest aggiungendo una policy `delegate` per quel file, delegando ad A.

### 13.7 Multi-package update con conflitti misti

**Scenario**: `scf_apply_updates(None)` deve aggiornare due pacchetti. Il primo ha file `preserve_tracked_modified` con `conflict_mode="auto"`. Il secondo ha file con `conflict_cross_owner`.

**Comportamento**:
- Il preflight `_classify_install_files` viene eseguito per tutti i pacchetti prima di qualsiasi scrittura (rispettando GAP-6 dell'audit).
- Se uno qualsiasi dei pacchetti ha `conflict_cross_owner`, l'intero batch viene bloccato prima di qualsiasi scrittura.
- Solo dopo che tutti i pacchetti hanno superato il preflight senza blocchi critici, iniziano le scritture in ordine dependency-aware.
- I file `preserve_tracked_modified` vengono gestiti con il `conflict_mode` specificato per ciascun pacchetto.

### 13.8 Rollback parziale dopo merge fallito

**Scenario**: durante `scf_finalize_update`, la scrittura di un file fallisce a metà sessione (es. disco pieno).

**Comportamento**: il rollback atomico esistente in `scf_install_package` viene esteso a `scf_finalize_update`. Prima di scrivere qualsiasi file, il motore cattura gli SHA correnti di tutti i file target. Se una scrittura fallisce, i file già scritti vengono ripristinati al loro contenuto precedente (SHA catturato). Il manifest non viene aggiornato per nessun file della sessione. La sessione rimane in stato `active`.

**Limitazione**: il rollback ripristina i file al loro stato precedente la finalizzazione, non allo stato pre-sessione. Se i file contenevano già marcatori di conflitto (sessione `manual`), i marcatori tornano visibili.

### 13.9 Utente che modifica file durante sessione merge attiva

**Scenario**: l'utente modifica su disco un file che fa parte di una sessione `active` dopo che la sessione è stata creata.

**Rilevamento**: `scf_finalize_update` confronta l'SHA corrente di ogni file target con `original_sha_at_session_open` (salvato nella sessione al momento della creazione). Se l'SHA è cambiato, il file è stato modificato esternamente.

**Comportamento**:
- Il file con modifica esterna non viene sovrascritto.
- L'operazione di finalizzazione per quel file viene saltata con warning.
- Il report include il file in `external_modifications_detected`.
- La sessione viene chiusa comunque per i file non impattati.
- La classificazione del file torna a `preserve_tracked_modified` per un futuro update.

### 13.10 Plugin che dichiara extend su file non ancora esistente

**Scenario**: un pacchetto B dichiara `policy: "extend"` per il file `.github/copilot-instructions.md`, ma quel file non esiste ancora nel workspace.

**Comportamento**: il motore tratta il file come `create_new`. Crea il file con solo la sezione marcata del pacchetto B:

```markdown
<!-- SCF:SECTION:scf-package-b:BEGIN -->
... contenuto del pacchetto B ...
<!-- SCF:SECTION:scf-package-b:END -->
```

Viene creato lo snapshot BASE con questo contenuto. Quando in futuro l'utente aggiunge contenuto proprio o il pacchetto A installa la sua sezione, il file cresce in modo addizionale senza conflitti.

---

## 14. Dipendenze e prerequisiti

### 14.1 Prerequisiti tecnici

| Prerequisito | Stato attuale | Necessario per |
|---|---|---|
| Python stdlib `difflib` | disponibile (Python 3.11+) | MergeEngine.diff3_merge |
| Python stdlib `uuid` | disponibile | session_id generazione |
| Python stdlib `shutil` | disponibile | cleanup snapshot su remove |
| `runtime/snapshots/` directory | non esiste | snapshot BASE |
| `runtime/merge-sessions/` directory | non esiste | sessioni stateful |
| `ENGINE_VERSION >= 2.0.0` | attuale: 1.9.0 | tutti i nuovi tool |

### 14.2 Prerequisiti di design implementati in precedenza

Prima di implementare il sistema di merge, devono essere in produzione:

1. **Sistema di snapshot BASE** (sezione 3): deve essere attivo prima di qualsiasi aggiornamento di pacchetto, altrimenti tutti gli update ricadono nel fallback "BASE assente" (sezione 13.2).

2. **scf_plan_install batch** (dalla Roadmap Fase 2, engine 1.10.0): il preflight multi-package per `scf_apply_updates` richiede un sistema di planning batch. Senza questo, GAP-6 (non-atomicità batch) non è risolvibile.

3. **Contatore tool aggiornato**: ogni tool aggiunto deve aggiornare il commento `# Tools registered: N total` nel sorgente e il test `test_engine_coherence.py`.

### 14.3 Prerequisiti di registry

Per supportare la policy per-file multi-owner (sezione 9), i `package-manifest.json` nei repository pacchetto devono adottare il campo `file_policies`. Questo è un prerequisito di adozione incrementale: funziona con il default `"error"` per tutti i file senza `file_policies`.

### 14.4 Prerequisiti LLM

I tool `scf_resolve_conflict_ai` richiedono un contesto LLM attivo. Il motore MCP non gestisce direttamente le invocazioni LLM; delega al chiamante (agente VS Code Copilot) tramite il protocollo MCP standard di sampling. Il design parte dall'assunzione che il client MCP supporti le richieste di sampling.

In ambienti senza LLM (CLI, client MCP non interattivi), i tool `auto` e `assisted` devono ritornare `success: False` con `error: "llm_unavailable"` e degradare a `manual`.

---

## 15. Decision log

### D-01 — Stdlib difflib vs libreria esterna diff3

**Decisione**: usare `difflib.SequenceMatcher` dalla libreria standard Python.

**Alternative considerate**:
- `diff-match-patch` (Google): più sofisticata, gestisce testo e byte, ma dipendenza esterna.
- Exec di `/usr/bin/diff3`: non portabile su Windows, dipendenza dal sistema operativo.
- `whatthepatch`: Python puro ma orientata a patch diff, non diff3.

**Motivazione**: nessuna nuova dipendenza esterna. Il motore SPARK ha un vincolo forte di portabilità (Windows, macOS, Linux) e di minimizzazione del `requirements.txt`. `difflib` è sufficientemente potente per file Markdown di dimensioni tipiche (1–50 KB). I limiti di `difflib` su file molto grandi non sono rilevanti per il caso d'uso SPARK.

**Trade-off accettato**: `difflib` non implementa nativamente un diff3. L'algoritmo nella sezione 4.3 è un'implementazione custom che usa `SequenceMatcher` come primitive. Questo introduce complessità di test aggiuntiva.

### D-02 — Snapshot in filesystem vs SHA nel manifest

**Decisione**: conservare il testo integrale degli snapshot sul filesystem, non nel manifest JSON.

**Alternative considerate**:
- Estendere il manifest con un campo `installed_content_b64` per ogni entry.
- Conservare gli snapshot in un file ZIP unico.
- Usare solo l'SHA e ricucire il testo dalla versione remota del pacchetto.

**Motivazione**: l'SHA-256 non è reversibile; il testo non può essere ricostruito da esso. Scaricare di nuovo la versione originale dal registry non è sempre possibile (versione rimossa, registry non raggiungibile). Il filesystem locale è la posizione più semplice e disponibile. I file snapshot sono human-readable e versionabili con git.

**Trade-off accettato**: duplicazione di storage (ogni file installato ha una copia snapshot). Per i pacchetti attuali (< 1 MB totale) il costo è trascurabile.

### D-03 — Timeout sessioni: 60 minuti

**Decisione**: timeout default di 60 minuti per le sessioni merge.

**Motivazione**: un merge assisted richiede input utente; 60 minuti è ragionevole per una sessione di editing interattiva. Sessioni più corte aumenterebbero in modo sproporzionato il friction operativo.

**Trade-off accettato**: sessioni orfane dopo crash rimangono su disco per 60 minuti prima di essere marcate expired. Il cleanup esplicito richiede un futuro tool di manutenzione.

### D-04 — Conflitti frontmatter sempre manuali in modalità auto

**Decisione**: anche in `conflict_mode="auto"`, i conflitti su campi frontmatter identici non vengono risolti automaticamente.

**Motivazione**: il frontmatter dei file `.agent.md` controlla quali tool sono accessibili all'agente. Una risoluzione automatica errata del blocco `tools:` potrebbe rendere un agente silenziosamente non funzionale. Il rischio supera il beneficio di automazione completa.

**Trade-off accettato**: la modalità `auto` non è pienamente automatica in presenza di conflitti frontmatter. L'utente deve sempre risolvere quel tipo di conflitto manualmente.

### D-05 — Validator come funzioni pure, non classi

**Decisione**: i validator post-merge sono funzioni pure (non classi con stato) per semplicità di test e composabilità.

**Motivazione**: non è necessario mantenere stato tra invocazioni. Le funzioni pure sono più facili da testare in isolamento, riducono la superficie di bug e non richiedono inizializzazione.

### D-06 — Nessun diff visuale nel report MCP

**Decisione**: i contratti di ritorno dei tool non includono una rappresentazione diff visuale (es. unified diff) delle modifiche.

**Motivazione**: i report MCP sono consumati da agenti AI, non da terminali umani. Un diff visuale aggiunge dimensione al payload senza valore per l'agente. Se necessario, l'agente può costruire un diff dalla sessione JSON usando gli stessi dati strutturati.

### D-07 — session_id come UUID v4 statico per sessione

**Decisione**: il `session_id` è un UUID v4 generato una volta alla creazione della sessione e non ricalcolato.

**Motivazione**: la stabilità del `session_id` permette al chiamante di fare riferimento alla stessa sessione attraverso invocazioni successive senza rischi di collisione. UUID v4 garantisce unicità pratica senza necessità di coordinazione centralizzata.

### D-08 — Policy multi-owner come primo-class nel manifest pacchetto

**Decisione**: la policy per-file viene dichiarata nel `package-manifest.json` del pacchetto, non in un file di configurazione del workspace.

**Motivazione**: la policy di ownership è una decisione del package maintainer, non dell'utente workspace. Centralizzarla nel manifest del pacchetto garantisce che tutti i workspace che installano il pacchetto adottino la stessa policy, riducendo il rischio di configurazioni divergenti.

**Trade-off accettato**: l'utente workspace non può sovrascrivere la policy del pacchetto. Questo è intenzionale: la policy è un contratto tra pacchetti, non tra pacchetto e workspace.

---

*Fine documento SCF-3WAY-MERGE-DESIGN v1.0.0*
