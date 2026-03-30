# Piano di Modifica — Supporto Doppio Formato Skill in SCF

**Data:** 30 marzo 2026
**Repo:** `spark-framework-engine`
**Ambito:** estendere `FrameworkInventory` per scoprire skill sia in formato legacy piatto che in formato standard Agent Skills a sottocartelle

---

## Contesto

Il motore attuale scopre le skill solo con pattern piatto `*.skill.md` in `.github/skills/`. Il formato standard Agent Skills usa sottocartelle `skill-name/SKILL.md`. Vogliamo supportare entrambi senza breaking change.

---

## File da modificare

Un solo file: `spark-framework-engine.py`

---

## Modifiche richieste

### 1. Metodo `FrameworkInventory.list_skills()`

**Posizione attuale:** classe `FrameworkInventory`, metodo `list_skills()`.

**Comportamento attuale:**
```python
def list_skills(self) -> list[FrameworkFile]:
    return self._list_by_pattern(
        self._ctx.github_root / "skills", "*.skill.md", "skill"
    )
```

**Comportamento nuovo:** scopre skill in due passate distinte e unisce i risultati senza duplicati, ordinati per nome.

- **Passata 1 — formato legacy piatto:** glob `*.skill.md` in `.github/skills/` — comportamento identico a prima, nessuna regressione
- **Passata 2 — formato standard Agent Skills:** itera le sottodirectory di `.github/skills/`, cerca `SKILL.md` in ciascuna, la tratta come skill con nome uguale al nome della directory
- **Deduplicazione:** se per qualche ragione esiste sia `foo.skill.md` che `foo/SKILL.md`, prevale il formato piatto (primo trovato vince)
- **Ordinamento:** lista finale ordinata per nome alfabetico

**Implementazione:**
```python
def list_skills(self) -> list[FrameworkFile]:
    """Discover SCF skills in both supported formats.

    Format 1 (legacy/SCF internal): .github/skills/*.skill.md
    Format 2 (Agent Skills standard): .github/skills/skill-name/SKILL.md
    Both formats are supported simultaneously. On name collision, flat format wins.
    """
    skills_root = self._ctx.github_root / "skills"

    # Passata 1: formato piatto legacy
    flat = self._list_by_pattern(skills_root, "*.skill.md", "skill")
    seen: set[str] = {ff.name for ff in flat}

    # Passata 2: formato standard Agent Skills (sottocartelle)
    standard: list[FrameworkFile] = []
    if skills_root.is_dir():
        for skill_dir in sorted(skills_root.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if skill_dir.is_dir() and skill_file.is_file():
                ff = self._build_framework_file(skill_file, "skill")
                # usa il nome della directory come nome skill, non "SKILL"
                ff = FrameworkFile(
                    name=skill_dir.name,
                    path=ff.path,
                    category=ff.category,
                    summary=ff.summary,
                    metadata=ff.metadata,
                )
                if ff.name not in seen:
                    standard.append(ff)
                    seen.add(ff.name)

    combined = flat + standard
    return sorted(combined, key=lambda ff: ff.name)
```

### 2. Resource `skills://{name}`

**Posizione attuale:** `register_resources()`, resource `skills://{name}`.

**Problema:** la lookup attuale normalizza il nome rimuovendo il suffisso `.skill`. Con il formato standard il nome è già la directory, quindi non ha suffisso da rimuovere. La logica attuale funziona già correttamente perché confronta `ff.name` — che nel nuovo metodo è già il nome normalizzato. **Nessuna modifica necessaria.**

### 3. Tool `scf_get_skill`

**Posizione attuale:** `register_tools()`, tool `scf_get_skill`.

**Stesso ragionamento:** la lookup usa `ff.name.lower().removesuffix(".skill")` per confrontare. Con il nuovo sistema il nome delle skill standard è già il nome directory senza suffisso, quindi il `removesuffix` non cambia nulla. **Nessuna modifica necessaria.**

### 4. Commento della classe `SparkFrameworkEngine`

**Posizione attuale:** docstring della classe, riga che descrive Resources e Tools.

**Modifica:** aggiornare il commento `Resources (14) and Tools (18)` — già corretto sul conteggio tools, nessuna variazione di conteggio da questa modifica. **Nessuna modifica necessaria.**

---

## Test da aggiornare o aggiungere

**File:** `tests/` — verificare se esistono test su `list_skills()`.

Se esistono, aggiungere un test case che:
- crea una struttura di directory temporanea con una skill in formato piatto (`foo.skill.md`) e una in formato standard (`bar/SKILL.md`)
- chiama `list_skills()` e verifica che entrambe siano presenti
- verifica che in caso di collisione nome il formato piatto prevalga
- verifica l'ordinamento alfabetico del risultato

---

## Invarianti da rispettare

- nessuna breaking change sui metodi pubblici di `FrameworkInventory`
- il comportamento su repo senza directory `.github/skills/` rimane identico: restituisce lista vuota
- il comportamento su `.github/skills/` esistente ma vuota rimane identico: restituisce lista vuota
- nessuna modifica a resource URI, tool signature, o formato di risposta

---

## Istruzioni per Copilot

Modifica il file `spark-framework-engine.py` nel repo `Nemex81/spark-framework-engine`.

Intervieni **solo** sul metodo `list_skills()` della classe `FrameworkInventory`. Non toccare nient'altro nel file.

Il metodo aggiornato deve:
1. eseguire prima la scoperta in formato piatto con `_list_by_pattern` — comportamento invariato rispetto a oggi
2. eseguire poi la scoperta in formato standard iterando le sottodirectory di `.github/skills/` e cercando `SKILL.md` in ciascuna
3. assegnare come nome della skill il nome della directory, non la stringa letterale `"SKILL"`
4. deduplicare per nome prima di unire le due liste — in caso di collisione il formato piatto ha priorità
5. restituire la lista unificata ordinata alfabeticamente per nome

Aggiungere o aggiornare i test in `tests/` per coprire il comportamento duale con fixture di directory temporanee.

Non modificare resource handler, tool handler, contatori, commenti di classe o qualsiasi altro metodo.

---

## Impatto

| Area | Impatto |
|---|---|
| Skill formato piatto esistenti | Nessuno — comportamento invariato |
| Skill formato standard nuove | Ora scoperte e servite correttamente |
| Resource `skills://list` | Mostra skill di entrambi i formati |
| Resource `skills://{name}` | Lookup funziona su entrambi i formati |
| Tool `scf_list_skills` | Restituisce skill di entrambi i formati |
| Tool `scf_get_skill` | Lookup funziona su entrambi i formati |
| Test esistenti | Nessuna regressione attesa |

---

## Note

Dopo l'implementazione, aggiornare `ENGINE_VERSION` da `1.0.0` a `1.1.0` in `spark-framework-engine.py` e creare la voce corrispondente nel `CHANGELOG.md` del motore.
