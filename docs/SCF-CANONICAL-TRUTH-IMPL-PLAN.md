# SCF — Canonical Truth Architecture: Piano di Implementazione

**Data redazione:** 2026-03-31
**Stato:** Attivo
**Versione documento:** 1.1 (revisione post-analisi)

---

## Contesto e diagnosi

Il problema che questo piano risolve non è un bug isolato. È un problema strutturale: dati identici esistono in più posti senza che nessuno li tenga in sync sistematicamente. La soluzione non è "stare più attenti" — è ridisegnare il sistema in modo che la necessità di essere attenti venga eliminata alla fonte.

L'esempio concreto che ha motivato il piano: il contatore dei tool MCP era dichiarato a 21 nel commento e nel log, mentre i tool effettivi nel sorgente erano 22. Nessun test lo ha rilevato perché nessun test verificava quella invariante.

---

## Principio fondamentale: Canonical Truth Architecture

Ogni dato ha esattamente **una fonte canonica**. Tutto il resto è:

- **derivato** — calcolato a runtime dalla fonte canonica, mai scritto a mano
- **sincronizzato** — aggiornato da automazione quando la fonte canonica cambia

Quando un dato non è nella sua fonte canonica, non è attendibile per definizione.

### Distribuzione delle fonti canoniche

| Dato | Fonte canonica | Repo |
|------|---------------|------|
| `ENGINE_VERSION` | `spark-framework-engine.py` | spark-framework-engine |
| Contatore tool MCP | sorgente Python (decorator count) | spark-framework-engine |
| Prima voce CHANGELOG | `CHANGELOG.md` | spark-framework-engine |
| `version` del pacchetto | `package-manifest.json` | scf-pycode-crafter |
| `min_engine_version` | `package-manifest.json` | scf-pycode-crafter |
| `latest_version` in registry | `registry.json` | scf-registry |
| `engine_min_version` in registry | `registry.json` | scf-registry |

L'**unica relazione di sync cross-repo** che richiede automazione è:
`package-manifest.json` (scf-pycode-crafter) → `registry.json` (scf-registry)

Tutto il resto è interno al singolo repo e si verifica con test locali.

### Confini di responsabilità tra componenti

Questi confini devono essere espliciti e rispettati. Diventano bug quando cambiano senza essere dichiarati.

- Il **motore** non deve mai conoscere i dettagli interni di un pacchetto oltre a `id`, `version`, `min_engine_version` e `repo_url`.
- Il **registry** non deve mai sostituire la logica di installazione del motore: è un indice, non un orchestratore.
- Il **pacchetto** è l'unica fonte autorevole della propria versione e dei propri requisiti. Il registry è un riflesso del pacchetto, non il contrario.

---

## Strategia in quattro livelli

### Livello 1 — Test di coerenza interna

**Obiettivo:** trasformare le invarianti implicite in assertion esplicite verificabili con pytest.
**Costo:** nessuna dipendenza nuova, nessuna infrastruttura aggiuntiva.
**Prerequisito immediato (da fare prima dei test):** correggere la guard in `scf_remove_package` — vedi sezione dedicata.

#### File: `tests/test_engine_coherence.py`

```python
# tests/test_engine_coherence.py
import re
from pathlib import Path

_SOURCE = Path(__file__).parent.parent / "spark-framework-engine.py"
_CHANGELOG = Path(__file__).parent.parent / "CHANGELOG.md"


def test_tool_counter_consistency():
    """
    Conta i decorator @self._mcp.tool( nel sorgente via regex,
    estrae il valore nel commento Tools (N) e nel log Tools registered: N total,
    e asserisce che i tre numeri coincidano.

    NOTA: il pattern usa @self._mcp.tool( senza la parentesi chiusa
    per catturare sia @self._mcp.tool() che @self._mcp.tool(name="...").
    """
    source = _SOURCE.read_text(encoding="utf-8")

    # Pattern aperto: cattura tool() e tool(name="...") e qualsiasi variante con argomenti
    actual = len(re.findall(r'@self\._mcp\.tool\(', source))

    comment_match = re.search(r'Tools \((\d+)\)', source)
    log_match = re.search(r'Tools registered: (\d+) total', source)

    assert comment_match, "Commento 'Tools (N)' non trovato nel sorgente"
    assert log_match, "Log 'Tools registered: N total' non trovato nel sorgente"

    comment_n = int(comment_match.group(1))
    log_n = int(log_match.group(1))

    assert actual == comment_n, f"Tool reali: {actual}, commento: {comment_n}"
    assert actual == log_n, f"Tool reali: {actual}, log: {log_n}"


def test_engine_version_changelog_alignment():
    """
    Verifica che ENGINE_VERSION nel sorgente coincida
    con la prima voce versionale di CHANGELOG.md.
    """
    source = _SOURCE.read_text(encoding="utf-8")
    version_match = re.search(r'ENGINE_VERSION: str = "([^"]+)"', source)
    assert version_match, "ENGINE_VERSION non trovata nel sorgente"
    engine_ver = version_match.group(1)

    changelog = _CHANGELOG.read_text(encoding="utf-8")
    entry_match = re.search(r'## \[([^\]]+)\]', changelog)
    assert entry_match, "Nessuna voce versionale trovata in CHANGELOG.md"
    changelog_ver = entry_match.group(1)

    assert engine_ver == changelog_ver, (
        f"ENGINE_VERSION={engine_ver} non allineata con CHANGELOG={changelog_ver}"
    )
```

**Nota sull'approccio:** questo file usa `Path.read_text()` + regex puri, senza importare il modulo engine. È una scelta deliberata: verifica la coerenza del sorgente come testo, indipendentemente dai mock di `mcp`. Il file `test_framework_versions.py` esistente usa invece `importlib` per testare il comportamento runtime — i due approcci sono complementari, non sovrapposti.

Questi test vanno aggiunti alla suite esistente e devono girare su ogni PR e su ogni commit in `main`.

#### Correzione immediata: guard in `scf_remove_package`

Questa correzione va applicata **prima** dei test, perché è un falso positivo silenzioso attivo in produzione ora.

```python
# In scf_remove_package, prima della chiamata a manifest.remove_package():
installed = manifest.get_installed_versions()
if package_id not in installed:
    return {
        "success": False,
        "error": (
            f"Pacchetto '{package_id}' non trovato nel manifest. "
            "Usa scf_list_installed_packages per vedere i pacchetti installati."
        ),
        "package": package_id,
    }
```

---

### Livello 2 — Tool MCP `scf_verify_system`

**Obiettivo:** verificare la coerenza cross-component a runtime — versione pacchetto installato vs `latest_version` nel registry vs `package-manifest.json` remoto.

#### Implementazione

```python
@self._mcp.tool()
async def scf_verify_system() -> dict[str, Any]:
    """Verifica la coerenza cross-component tra motore, pacchetti e registry."""
    issues: list[dict[str, Any]] = []
    warnings: list[str] = []
    installed = manifest.get_installed_versions()

    # Caso edge: manifest vuoto o non trovato — distinguere "tutto ok" da "niente da controllare"
    if not installed:
        return {
            "engine_version": ENGINE_VERSION,
            "packages_checked": 0,
            "issues": [],
            "warnings": [],
            "manifest_empty": True,
            "is_coherent": True,
        }

    try:
        reg_packages = registry.list_packages()
    except Exception as exc:
        return {"success": False, "error": f"Registry non raggiungibile: {exc}"}

    reg_index = {p["id"]: p for p in reg_packages if "id" in p}

    for pkg_id, installed_ver in installed.items():
        reg_entry = reg_index.get(pkg_id)
        if reg_entry is None:
            warnings.append(f"Pacchetto '{pkg_id}' non trovato nel registry")
            continue
        try:
            pkg_manifest_data = registry.fetch_package_manifest(reg_entry["repo_url"])
        except Exception as exc:
            warnings.append(f"Manifest non raggiungibile per '{pkg_id}': {exc}")
            continue

        manifest_ver = str(pkg_manifest_data.get("version", "")).strip()
        registry_ver = str(reg_entry.get("latest_version", "")).strip()
        if manifest_ver != registry_ver:
            issues.append({
                "type": "registry_stale",
                "package": pkg_id,
                "registry_version": registry_ver,
                "manifest_version": manifest_ver,
                "fix": f"Aggiornare registry.json: latest_version → {manifest_ver}",
            })

        min_engine_pkg = str(pkg_manifest_data.get("min_engine_version", "")).strip()
        min_engine_reg = str(reg_entry.get("engine_min_version", "")).strip()
        if min_engine_pkg and min_engine_reg and min_engine_pkg != min_engine_reg:
            issues.append({
                "type": "engine_min_mismatch",
                "package": pkg_id,
                "registry_engine_min": min_engine_reg,
                "manifest_engine_min": min_engine_pkg,
                "fix": f"Aggiornare registry.json: engine_min_version → {min_engine_pkg}",
            })

    return {
        "engine_version": ENGINE_VERSION,
        "packages_checked": len(installed),
        "issues": issues,
        "warnings": warnings,
        "manifest_empty": False,
        "is_coherent": len(issues) == 0,
    }
```

**Note tecniche:**

- Il tool va aggiunto a `register_tools()` con i contatori aggiornati (incrementare commento e log).
- Va referenziato in `scf-status.prompt.md` come controllo opzionale di sistema.
- **Debito tecnico noto:** le chiamate `fetch_package_manifest` sono sequenziali (una per pacchetto). Con N pacchetti diventa N richieste HTTP in serie. Da risolvere in futuro con `asyncio.gather` o una cache con TTL. Con un solo pacchetto installato non è un problema ora.

---

### Livello 3 — GitHub Action per sync automatico del registry

**Obiettivo:** il registry non deve mai essere aggiornato manualmente. Quando `package-manifest.json` cambia in un repo pacchetto, viene aperta automaticamente una PR su `scf-registry`.

#### File: `.github/workflows/sync-registry.yml` (in scf-pycode-crafter)

```yaml
# .github/workflows/sync-registry.yml
# In: scf-pycode-crafter (e ogni futuro scf-pack-*)
name: Sync registry on manifest change

on:
  push:
    branches: [main]
    paths: [package-manifest.json]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Extract manifest fields
        id: manifest
        run: |
          echo "pkg_id=$(jq -r '.package' package-manifest.json)" >> $GITHUB_OUTPUT
          echo "version=$(jq -r '.version' package-manifest.json)" >> $GITHUB_OUTPUT
          echo "engine_min=$(jq -r '.min_engine_version' package-manifest.json)" >> $GITHUB_OUTPUT

      - name: Checkout scf-registry
        uses: actions/checkout@v4
        with:
          repository: Nemex81/scf-registry
          token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
          path: registry-repo

      - name: Update registry.json
        run: |
          cd registry-repo
          python3 - <<'EOF'
          import json, os
          from datetime import datetime, timezone

          with open('registry.json', 'r') as f:
              data = json.load(f)

          pkg_id = os.environ['PKG_ID']
          found = False
          for pkg in data['packages']:
              if pkg['id'] == pkg_id:
                  pkg['latest_version'] = os.environ['VERSION']
                  pkg['engine_min_version'] = os.environ['ENGINE_MIN']
                  found = True
                  break

          if not found:
              raise ValueError(f"Pacchetto '{pkg_id}' non trovato in registry.json. Aggiungilo manualmente prima di usare il workflow.")

          data['updated_at'] = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

          with open('registry.json', 'w') as f:
              json.dump(data, f, indent=2, ensure_ascii=False)
          EOF
        env:
          PKG_ID: ${{ steps.manifest.outputs.pkg_id }}
          VERSION: ${{ steps.manifest.outputs.version }}
          ENGINE_MIN: ${{ steps.manifest.outputs.engine_min }}

      - name: Open PR on scf-registry
        uses: peter-evans/create-pull-request@v6
        with:
          path: registry-repo
          token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
          commit-message: "sync: ${{ steps.manifest.outputs.pkg_id }} → ${{ steps.manifest.outputs.version }}"
          title: "sync: ${{ steps.manifest.outputs.pkg_id }} ${{ steps.manifest.outputs.version }}"
          body: "Auto-generata da sync-registry.yml in ${{ github.repository }}"
          branch: "sync/${{ steps.manifest.outputs.pkg_id }}-${{ steps.manifest.outputs.version }}"
```

**Correzioni rispetto alla versione originale:**

1. Il blocco Python ora verifica esplicitamente che `pkg_id` esista nel registry con un `raise ValueError` descrittivo. Se il pacchetto non è ancora registrato, il workflow fallisce visibilmente invece di scrivere silenziosamente dati parziali.

2. **Rischio failure silenziosa:** se il workflow fallisce (token scaduto, rate limit GitHub, rete), il registry rimane stale senza notifica. Soluzione consigliata: aggiungere uno step di notifica fallimento via `actions/github-script` che apre un'issue di warning nel repo del pacchetto. Questo è opzionale ma raccomandato per ambienti con più pacchetti.

**Prerequisito cross-repo da verificare:** il campo `.package` in `package-manifest.json` deve coincidere con il campo `.id` in `registry.json`. Questa assunzione non è verificata da nessun test automatico. Aggiungere in `scf-pycode-crafter` un test che legga entrambi i file e asserta l'uguaglianza prima di fare affidamento sul workflow.

**Setup una-tantum:**
- Creare `REGISTRY_WRITE_TOKEN` come GitHub Secret in `scf-pycode-crafter` (PAT con write su `scf-registry`).
- Aggiornare `registry.json` manualmente per allinearlo allo stato attuale (`version: 1.0.1`, `engine_min_version: "1.2.1"`) — questa è l'**ultima sincronizzazione manuale** prevista dall'architettura.

---

### Livello 4 — Protocollo di release formale

**Obiettivo:** estendere `scf-release-check` con gate cross-component e documentare il ciclo di vita di un rilascio.

#### Estensione di `scf-release-check`

Aggiungere due passi al check esistente:

1. Invocare `scf_verify_system` come gate obbligatorio. Se `is_coherent: False` o se `issues` contiene voci di tipo `registry_stale`, il check deve riportare **CRITICAL** e bloccare il rilascio.

2. Il passo "proposta tag git" viene esteso con la checklist post-tag:
   - [ ] Verificare che la GitHub Action abbia aperto la PR su `scf-registry`
   - [ ] Controllare che la PR sia stata mergiata
   - [ ] Eseguire `scf_verify_system` una seconda volta post-merge per conferma
   - [ ] Solo dopo: dichiarare il rilascio completo

#### Documentazione da aggiungere a `SCF-PROJECT-DESIGN.md`

Aggiungere una sezione **"Protocollo di rilascio pacchetto"** che documenta:
- La gerarchia delle fonti canoniche (tabella sopra)
- I confini di responsabilità tra componenti (sezione sopra)
- Il ciclo di vita di un rilascio: `package-manifest.json` modificato → push su `main` → GitHub Action → PR su `scf-registry` → merge → sistema coerente
- I gate obbligatori pre-tag: `scf_verify_system` verde, CHANGELOG aggiornato, `ENGINE_VERSION` allineata

#### Operazioni di archivio

- Chiudere il blocco E in `SCF-CORRECTIVE-PLAN.md`
- Spostare `IMPLEMENTATION_PLAN_MULTI_PACKAGE.md` in `docs/DONE-IMPLEMENTATION_PLAN_MULTI_PACKAGE.md`

---

## Piano di implementazione: fasi ordinate

### Fase 1 — Immediata (stimato: 1 ora)

**Priorità assoluta — da fare prima dei test:**
- [ ] Correggere la guard in `scf_remove_package` (falso positivo silenzioso attivo ora)

**Poi:**
- [ ] Aggiungere `tests/test_engine_coherence.py` con i due test descritti
- [ ] Correggere il commento `Tools (21)` → `Tools (22)`
- [ ] Aggiornare CHANGELOG con bump patch **1.2.2**
- [ ] Eseguire `pytest -q` per confermare suite verde

Corrisponde ai problemi C2 e C3 di `SCF-CORRECTIVE-PLAN.md`.

### Fase 2 — Un pomeriggio

- [ ] Aggiungere `scf_verify_system` in `register_tools()` con i contatori aggiornati
- [ ] Gestire il caso edge `manifest_empty` nel response
- [ ] Aggiornare `scf-status.prompt.md` per includere il nuovo tool
- [ ] Bump minor **1.3.0**
- [ ] Eseguire `pytest -q` per confermare suite verde

### Fase 3 — Setup una-tantum (cross-repo)

- [ ] Creare `REGISTRY_WRITE_TOKEN` come GitHub Secret in `scf-pycode-crafter`
- [ ] Aggiungere `.github/workflows/sync-registry.yml` in `scf-pycode-crafter`
- [ ] Aggiungere in `scf-pycode-crafter` il test di verifica cross-repo `package` == `id`
- [ ] Testare il workflow su un branch: modificare `package-manifest.json` e verificare che la PR arrivi su `scf-registry`
- [ ] Aggiornare `registry.json` manualmente per l'ultima volta (versione attuale)

### Fase 4 — Documentazione e chiusura

- [ ] Aggiungere sezione "Protocollo di rilascio" a `SCF-PROJECT-DESIGN.md`
- [ ] Chiudere il blocco E in `SCF-CORRECTIVE-PLAN.md`
- [ ] Spostare `IMPLEMENTATION_PLAN_MULTI_PACKAGE.md` → `docs/DONE-IMPLEMENTATION_PLAN_MULTI_PACKAGE.md`
- [ ] Aggiornare questo file con stato "Completato"

---

## Risultato atteso

A implementazione completata, rilasciare una nuova versione di `scf-pycode-crafter` richiede esattamente **tre azioni umane**:

1. Modificare `package-manifest.json`
2. Pushare su `main`
3. Fare merge della PR auto-generata su `scf-registry`

Tutto il resto — verifica coerenza, aggiornamento registry, gate pre-tag — è verificato, calcolato o automatizzato.
