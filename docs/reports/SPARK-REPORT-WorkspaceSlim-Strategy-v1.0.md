# SPARK-REPORT — Strategia Workspace Slim: Rimozione Repo Esterni e Allineamento HTTPS
**Versione:** 1.0  
**Data:** 2026-05-11  
**Stato:** STRATEGIA VALIDATA — PRONTA PER ESECUZIONE  
**Autore:** spark-engine-maintainer  

---

## 1. Sintesi Analisi (Theory Validation)

### Teoria proposta dall'utente
> Il motore spark-framework-engine deve essere un universo autonomo che espone tool MCP
> per gestire plugin/pacchetti tramite canale HTTPS verso i repository GitHub.
> Le cartelle workspace dei pacchetti indipendenti (spark-base, scf-master-codecrafter,
> scf-pycode-crafter, scf-registry) sono ridondanti e devono essere rimosse.

### Verdetto: **TEORIA VALIDA ✅** — con 4 precisazioni tecniche

---

## 2. Evidenze dell'Analisi

### 2.1 Registry remoto — già configurato via HTTPS

In `spark/core/constants.py`:
```python
_REGISTRY_URL: str = (
    "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
)
```

In `spark-init.py`:
```python
REGISTRY_URL = "https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json"
```

**Conclusione:** Il motore NON legge il registry da file locale. Usa già HTTPS. ✅

### 2.2 Download pacchetti — già via raw.githubusercontent.com

In `spark/boot/install_helpers.py` e `spark/packages/lifecycle.py`:
```python
base_raw_url = pkg["repo_url"].replace(
    "https://github.com/", "https://raw.githubusercontent.com/"
)
```

In `spark/registry/client.py`:
```python
# solo URL raw.githubusercontent.com sono accettati
if not self._registry_url.startswith("https://raw.githubusercontent.com/"):
    raise ValueError(...)
```

**Conclusione:** Il motore scarica i file pacchetto da GitHub tramite HTTPS. ✅

### 2.3 Cartelle workspace esterne — ZERO dipendenze nel codice Python

Ricerca exhaustiva su tutti i sorgenti `.py` del motore: **nessun path reference**
a `../scf-registry`, `../spark-base`, `../scf-master-codecrafter`, `../scf-pycode-crafter`.

Le cartelle esterne sono presenti SOLO nel file `.code-workspace`:
```json
{
  "folders": [
    {"path": "."},
    {"path": "../scf-registry"},         // ← solo IDE convenience
    {"path": "../scf-master-codecrafter"},// ← solo IDE convenience
    {"path": "../scf-pycode-crafter"},    // ← solo IDE convenience
    {"path": "../spark-base"}             // ← solo IDE convenience
  ]
}
```

**Conclusione:** Rimozione sicura senza impatto sul motore. ✅

### 2.4 Store interna `packages/` — NON va rimossa (è la cache MCP funzionale)

La directory `spark-framework-engine/packages/` è la **store locale del motore MCP**,
popolata durante l'installazione pacchetti scaricando da GitHub. Serve per:
- Servire agenti, skill, prompt, instruction via tool MCP (`scf_get_agent`, ecc.)
- Risolvere risorse MCP senza accesso online a ogni richiesta

**NON è una copia manuale dei repo source. È la cache funzionale dell'engine.**  
Rimuoverla romperebbe l'engine. **NON va toccata.** ⛔

---

## 3. Gap Critico Rilevato: Versioni non allineate

Inventario attuale delle versioni (2026-05-11):

| Pacchetto | Repo source (workspace) | Store interna `packages/` | Registry remoto (`scf-registry`) |
|---|---|---|---|
| spark-base | 1.7.3 | 1.7.3 | 1.7.3 |
| scf-master-codecrafter | 2.6.1 | **2.7.0** | 2.6.1 ← STALE |
| scf-pycode-crafter | 2.2.2 | **2.3.0** | 2.2.2 ← STALE |
| spark-ops | N/A | **1.1.0** | **ASSENTE** ← GAP |
| pkg-smoke | N/A | 3.1.0 | N/A (test-only) |

**Problema:** Il registry remoto su GitHub (`Nemex81/scf-registry`) è stale e non
conosce spark-ops. Se un utente finale chiama `scf_install_package("spark-ops")`,
il motore non troverà l'entry nel registry.

---

## 4. Strategia di Modifica — 4 Fasi

### FASE 1 — Aggiornare il Registry Remoto `scf-registry`
**File:** `scf-registry/registry.json`  
**Azioni:**

1. Aggiornare `scf-master-codecrafter`: `latest_version` → `"2.7.0"`, `min_engine_version` → `"3.4.0"`
2. Aggiornare `scf-pycode-crafter`: `latest_version` → `"2.3.0"`, `min_engine_version` → `"3.4.0"`
3. Aggiungere entry `spark-ops`:
```json
{
  "id": "spark-ops",
  "display_name": "SPARK Ops Layer",
  "description": "Layer operativo E2E/framework-docs/release. Richiede spark-base >= 2.0.0.",
  "latest_version": "1.1.0",
  "version_source": "package-manifest",
  "status": "stable",
  "repo_url": "https://github.com/Nemex81/spark-ops",
  "min_engine_version": "3.4.0",
  "engine_managed_resources": true,
  "tags": ["ops", "e2e", "release", "docs", "spark-base"]
}
```
4. Aggiornare `updated_at` → `"2026-05-11T00:00:00Z"`
5. **Push su GitHub** (richiede conferma PUSH ad Agent-Git)

> ⚠️ **NOTA:** Il repo `spark-ops` deve esistere su GitHub prima di questo step,
> oppure il `repo_url` deve puntare a un repository pubblico valido.

### FASE 2 — Aggiornare i Repository Source (opzionale ma consigliato)
**Repo:** spark-base, scf-master-codecrafter, scf-pycode-crafter  
**Azioni:** Portare le versioni dei repo source al pari con la store interna:
- scf-master-codecrafter: bump a 2.7.0
- scf-pycode-crafter: bump a 2.3.0

> ℹ️ Questa fase è opzionale se i repo source vengono abbandonati come cartelle
> di sviluppo attivo. I file "veri" sono nella store interna del motore.

### FASE 3 — Aggiornare `.code-workspace` (rimozione cartelle esterne)
**File:** `spark-framework-engine.code-workspace`  
**Azione:** Rimuovere le 4 entry esterne:

```json
// DA RIMUOVERE:
{"path": "../scf-registry"},
{"path": "../scf-master-codecrafter"},
{"path": "../scf-pycode-crafter"},
{"path": "../spark-base"}
```

**Risultato finale:**
```json
{
  "folders": [{"path": "."}],
  "settings": {"powershell.cwd": "spark-framework-engine"},
  "mcp": { /* invariato */ }
}
```

> ✅ **Sicuro:** nessuna dipendenza runtime nelle cartelle da rimuovere.
> ⚠️ **Reversibile:** le cartelle fisiche restano su disco — solo il workspace VS Code smette di includerle.

### FASE 4 — Documentare gli URL HTTPS come canonical reference
**File suggeriti:**
- `docs/api.md`: aggiungere sezione "Registry e Package URL"
- `README.md`: aggiornare sezione architettura con il modello HTTPS-first

**URL canonici da documentare:**

| Risorsa | URL HTTPS |
|---|---|
| Registry principale | `https://raw.githubusercontent.com/Nemex81/scf-registry/main/registry.json` |
| spark-base repo | `https://github.com/Nemex81/spark-base` |
| scf-master-codecrafter repo | `https://github.com/Nemex81/scf-master-codecrafter` |
| scf-pycode-crafter repo | `https://github.com/Nemex81/scf-pycode-crafter` |
| spark-ops repo | `https://github.com/Nemex81/spark-ops` *(da creare o verificare)* |

---

## 5. Precondizioni e Rischi

### Precondizione critica: `spark-ops` su GitHub
Il pacchetto `spark-ops` è presente nella store interna (`packages/spark-ops`) ma
non ha un repository GitHub pubblico verificato. Prima della FASE 1 occorre:
1. Verificare se `https://github.com/Nemex81/spark-ops` esiste
2. Se non esiste: creare il repo oppure NON aggiungere spark-ops al registry remoto
   (il motore continua a servire spark-ops dalla store interna via MCP, ma non sarà
   installabile tramite `scf_install_package`)

### Rischio basso: Cache del registry nel workspace utente
Se un workspace utente ha una cache locale `.github/.scf-registry-cache.json` con
versioni obsolete, continuerà a vederle fino alla prossima fetch online. Non è un
problema del motore ma di cache lato utente — si risolve con `scf_check_updates()`.

### Rischio nullo: Funzionamento MCP
La rimozione delle cartelle workspace dal `.code-workspace` non impatta in nessun
modo il funzionamento del server MCP. Il server legge solo la propria directory.

---

## 6. Ordine di Esecuzione Consigliato

```
FASE 1 → FASE 3 → FASE 4 → FASE 2 (opzionale)
```

La FASE 3 (rimozione workspace) è sicura da eseguire **subito**, in autonomia.
La FASE 1 (registry) richiede una verifica sull'esistenza del repo spark-ops prima del push.

---

## 7. Comandi Proposti

```bash
# FASE 3: rimozione cartelle workspace (solo modifica .code-workspace — già fatto dal motore)
# Modificare spark-framework-engine.code-workspace manualmente o con Agent-Code

# FASE 1: push registry aggiornato
git add scf-registry/registry.json
git commit -m "chore(registry): sync versions + add spark-ops entry (v2026-05-11)"
# → delegare ad Agent-Git con conferma PUSH
```

---

## 8. Architettura Post-Modifica

```
spark-framework-engine/          ← unico folder nel workspace VS Code
├── spark-framework-engine.py    ← server MCP
├── packages/                    ← store MCP locale (cache funzionale, NON toccare)
│   ├── spark-base/
│   ├── spark-ops/
│   ├── scf-master-codecrafter/
│   └── scf-pycode-crafter/
├── spark/                       ← sorgenti del motore
└── ...

Registry remoto (GitHub):        ← fonte di verità per installazioni utente
  https://github.com/Nemex81/scf-registry/blob/main/registry.json

Repo pacchetti (GitHub):         ← fonte di verità per file pacchetto
  https://github.com/Nemex81/spark-base
  https://github.com/Nemex81/scf-master-codecrafter
  https://github.com/Nemex81/scf-pycode-crafter
  https://github.com/Nemex81/spark-ops  (da verificare)
```

---

*Report generato da spark-engine-maintainer — 2026-05-11*
