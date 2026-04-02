# Piano Correttivo — Update Diff-Based, Tagging SPARK e Verify Tripartito

**Data:** 2026-04-02
**Motore target:** 1.4.0
**Pacchetto interessato:** scf-pycode-crafter (Step 1)
**Repo:** spark-framework-engine

---

## Contesto

Questo documento descrive tre interventi correlati da applicare in sequenza all'ecosistema SPARK Framework:

1. **Step 1** — Standardizzare il frontmatter SPARK nei file del pacchetto `scf-pycode-crafter`
2. **Step 2** — Aggiungere diff-based cleanup all'update nel motore (bump `1.4.0`)
3. **Step 3** — Estendere `verify_integrity` con classificazione tripartita

Problema di fondo: quando un pacchetto rinomina o rimuove file tra versioni, il motore attuale installa i nuovi file ma non rimuove i vecchi. Un utente che aggiorna da `scf-pycode-crafter v1.0.0` a `v1.2.0` si ritrova con i file agenti della versione precedente (11 file con naming vecchio) più i nuovi (11 con naming aggiornato), per un totale di 22 file invece di 11.

---

## Step 1 — Tagging frontmatter nei file di `scf-pycode-crafter`

**Repository:** `scf-pycode-crafter`
**Bump versione pacchetto:** `1.2.0` → `1.2.1`
**Nessuna modifica al motore richiesta.**

### Problema

Il frontmatter YAML dei file del pacchetto non include campi standardizzati che permettano al motore (e a un umano) di identificare:
- A quale pacchetto SCF appartiene il file
- In quale versione del pacchetto è stato installato
- Se il file è un componente gestito dall'ecosistema SPARK o un file locale dell'utente

### Soluzione

Aggiungere i seguenti campi al frontmatter di **tutti** i file installati dal pacchetto (agenti, skill, instruction, prompt):

```yaml
---
name: <nome-componente>
package: scf-pycode-crafter
version: 1.2.1
spark: true
---
```

Regole:
- `spark: true` — flag booleano obbligatorio per tutti i componenti SCF gestiti
- `package` — id del pacchetto esattamente come appare in `registry.json`
- `version` — versione del pacchetto al momento in cui il file è stato aggiunto/modificato
- `name` — nome del componente, deve corrispondere al nome file senza estensione

### File da aggiornare

Tutti i file nelle directory:
- `.github/agents/*.md`
- `.github/skills/*.skill.md` o `.github/skills/*/SKILL.md`
- `.github/instructions/*.instructions.md`
- `.github/prompts/*.prompt.md`

Verificare con:

```bash
# Conta quanti file mancano del campo spark
grep -rL "spark: true" .github/agents/ .github/skills/ .github/instructions/ .github/prompts/
```

### Cosa NON toccare

- `project-profile.md` — file di configurazione workspace, non un componente pacchetto
- `copilot-instructions.md` — idem
- `AGENTS.md` — indice, non componente
- `model-policy.instructions.md` — policy globale, non componente pacchetto

### Commit e bump

```bash
# Dopo aver aggiornato tutti i file
# Aggiornare anche package-manifest.json: campo "version" → "1.2.1"
git add .github/ package-manifest.json
git commit -m "feat: aggiungi frontmatter SPARK standardizzato a tutti i componenti (v1.2.1)"
git tag v1.2.1
git push && git push --tags
```

---

## Step 2 — Diff-based cleanup all'update nel motore

**Repository:** `spark-framework-engine`
**Bump versione motore:** `1.3.2` → `1.4.0`
**Richiede aggiornamento `engine_min_version` in `scf-pycode-crafter` → `1.4.0`**

### Problema

`scf_install_package` sovrascrive i file esistenti correttamente, ma non rimuove i file che il nuovo manifest del pacchetto non include più (file rinominati, rimossi o spostati tra versioni).

### Dove intervenire

File: `spark-framework-engine.py`
Classe: nessuna classe dedicata — la logica di installazione è inline nel tool `scf_install_package` all'interno di `register_tools`.

### Logica da aggiungere

Inserire **prima** della fase di download e scrittura dei file, questa sequenza:

```python
# --- INIZIO BLOCCO DA AGGIUNGERE in scf_install_package ---

# 1. Recupera lista file attualmente installati per questo pacchetto dal manifest
manifest_entries = manifest.load()
old_files: set[str] = {
    entry["file"]
    for entry in manifest_entries
    if entry.get("package") == package_id
}

# 2. Costruisci la lista dei file che il NUOVO manifest intende installare
#    (pkg_manifest è già disponibile a questo punto nel codice esistente)
new_files: set[str] = set()
for file_entry in pkg_manifest.get("files", []):
    dest_rel = file_entry.get("dest", "")
    if dest_rel:
        new_files.add(dest_rel)

# 3. File da rimuovere = presenti nell'installazione corrente ma assenti nel nuovo manifest
to_remove: set[str] = old_files - new_files

# 4. Rimuovi i file obsoleti (solo se non modificati dall'utente)
removed_files: list[str] = []
preserved_obsolete: list[str] = []

for rel_path in sorted(to_remove):
    is_modified = manifest.is_user_modified(rel_path)
    file_abs = ctx.github_root / rel_path
    if is_modified:
        preserved_obsolete.append(rel_path)
        _log.warning("File obsoleto preservato (modificato dall'utente): %s", rel_path)
    else:
        if file_abs.is_file():
            try:
                file_abs.unlink()
                removed_files.append(rel_path)
                _log.info("File obsoleto rimosso: %s", rel_path)
            except OSError as exc:
                _log.warning("Impossibile rimuovere file obsoleto %s: %s", rel_path, exc)

# --- FINE BLOCCO ---
```

Aggiungere `removed_files` e `preserved_obsolete` all'oggetto di ritorno del tool:

```python
return {
    "success": True,
    "package_id": package_id,
    "version_installed": new_version,
    # ... campi già esistenti ...
    "removed_obsolete_files": removed_files,          # <-- NUOVO
    "preserved_obsolete_files": preserved_obsolete,   # <-- NUOVO
}
```

### Test da aggiungere in `tests/`

Aggiungere un test case in `tests/test_manifest.py` (o creare `tests/test_update_diff.py`) che verifica:

1. Installa pacchetto fittizio v1.0.0 con file `["agents/OldAgent.md", "agents/Common.md"]`
2. Aggiorna a v2.0.0 con file `["agents/NewAgent.md", "agents/Common.md"]`
3. Verifica che `agents/OldAgent.md` sia stato rimosso
4. Verifica che `agents/Common.md` sia stato aggiornato (non rimosso)
5. Verifica che `agents/NewAgent.md` sia stato creato

Caso aggiuntivo con SHA:
6. Modifica `agents/OldAgent.md` su disco (SHA cambia)
7. Aggiorna il pacchetto
8. Verifica che `agents/OldAgent.md` sia stato **preservato** e compaia in `preserved_obsolete_files`

### Bump versione

```python
# spark-framework-engine.py — riga ENGINE_VERSION
ENGINE_VERSION: str = "1.4.0"
```

---

## Step 3 — Classificazione tripartita in `verify_integrity`

**Repository:** `spark-framework-engine`
**Va implementato insieme allo Step 2 nello stesso bump `1.4.0`.**

### Problema

`ManifestManager.verify_integrity()` classifica i file in: `ok / missing / modified / orphan_candidates`. La categoria `orphan_candidates` include indistintamente:
- File utente legittimi (agenti e skill creati dall'utente, senza frontmatter SPARK)
- File che il motore non riesce a riconoscere (potenziale anomalia)

Questo genera falsi positivi nei report di `scf_verify_workspace` e rende il tool rumoroso per gli utenti che hanno componenti locali.

### Soluzione

Estendere `verify_integrity` per leggere il frontmatter dei file non tracciati e classificarli in tre categorie:

```
managed  → file con spark: true nel frontmatter E tracciato nel manifest (già ok/missing/modified)
user     → file NON tracciato nel manifest E (spark assente o spark: false nel frontmatter)
orphan   → file tracciato nel manifest ma assente su disco (già esistente come "missing")
untagged → file non tracciato E spark: true nel frontmatter (anomalia: SCF ma non nel manifest)
```

### Dove intervenire

Metodo `ManifestManager.verify_integrity()` — sezione finale che costruisce `orphan_candidates`.

Sostituire il blocco esistente:

```python
# CODICE ATTUALE (da sostituire)
orphan_candidates: list[str] = []
if self._github_root.is_dir():
    for path in sorted(candidate for candidate in self._github_root.rglob("*") if candidate.is_file()):
        rel_path = path.relative_to(self._github_root).as_posix()
        if rel_path in ignored_runtime_files:
            continue
        if rel_path not in tracked_files:
            orphan_candidates.append(rel_path)
```

Con questo blocco aggiornato:

```python
# CODICE NUOVO
user_files: list[str] = []
untagged_spark_files: list[str] = []
orphan_candidates: list[str] = []  # mantenuto per retrocompatibilità, ora = untagged

if self._github_root.is_dir():
    for path in sorted(
        candidate for candidate in self._github_root.rglob("*") if candidate.is_file()
    ):
        rel_path = path.relative_to(self._github_root).as_posix()
        if rel_path in ignored_runtime_files:
            continue
        if rel_path in tracked_files:
            continue  # già classificato come ok/missing/modified

        # Leggi frontmatter per classificare
        is_spark = False
        if path.suffix in (".md",):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                fm = parse_markdown_frontmatter(content)
                is_spark = bool(fm.get("spark", False))
            except OSError:
                pass

        if is_spark:
            # File con spark: true ma non nel manifest — anomalia
            untagged_spark_files.append(rel_path)
            orphan_candidates.append(rel_path)  # retrocompatibilità
        else:
            # File utente locale — normale, non segnalare come problema
            user_files.append(rel_path)
```

Aggiornare il dizionario di ritorno:

```python
return {
    "missing": missing,
    "modified": modified,
    "ok": ok,
    "duplicate_owners": duplicate_owners,
    "orphan_candidates": orphan_candidates,     # retrocompatibilità: ora = solo untagged_spark_files
    "user_files": user_files,                   # NUOVO: file locali utente, non SCF
    "untagged_spark_files": untagged_spark_files,  # NUOVO: SCF non tracciati (anomalia)
    "summary": {
        **summary,
        "user_file_count": len(user_files),         # NUOVO
        "untagged_spark_count": len(untagged_spark_files),  # NUOVO
    },
}
```

### Aggiornamento di `scf_verify_workspace`

Il tool `scf_verify_workspace` che espone `verify_integrity` all'esterno deve aggiornare il testo di output per includere le nuove categorie:

```python
# Nel tool scf_verify_workspace (inline in register_tools)
# Aggiungere alla risposta:
result["user_files"] = integrity.get("user_files", [])
result["untagged_spark_files"] = integrity.get("untagged_spark_files", [])
```

### Test da aggiungere

Aggiungere in `tests/test_manifest.py`:

1. File `.github/agents/CustomAgent.md` senza frontmatter → deve comparire in `user_files`, non in `orphan_candidates`
2. File `.github/agents/MysteryAgent.md` con `spark: true` ma non nel manifest → deve comparire in `untagged_spark_files` e in `orphan_candidates`
3. File `.github/agents/TrackedAgent.md` con `spark: true` e tracciato nel manifest → deve comparire in `ok`

---

## Sequenza di deploy

```
1. scf-pycode-crafter  → aggiorna frontmatter → tag v1.2.1 → push
2. spark-framework-engine → Step 2 + Step 3 → bump ENGINE_VERSION = "1.4.0" → pytest -q verde → push
3. scf-registry → aggiorna engine_min_version di scf-pycode-crafter → "1.4.0" → PR auto-merge
```

Il registry sync è automatico via GitHub Action. Non serve intervento manuale sul registry dopo il push del pacchetto.

---

## Verifica finale

Dopo il deploy completo:

```bash
# Motore: conferma versione
grep "ENGINE_VERSION" spark-framework-engine.py  # → "1.4.0"

# Test: tutto verde
pytest -q

# Integrità manifesta: nessun untagged_spark_files, nessun orphan
# Eseguire in VS Code Agent mode:
# scf_verify_workspace()  →  summary.untagged_spark_count == 0
```
