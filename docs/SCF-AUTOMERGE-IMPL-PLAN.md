# SCF — Piano Implementativo: Auto-merge Condizionale per il Gateway

**Data redazione:** 2026-04-01
**Stato:** 📋 da implementare
**Versione documento:** 1.2 (rev. validazione prerequisiti)
**Repository target:** `spark-framework-engine`
**File da modificare:** `.github/workflows/registry-sync-gateway.yml`

---

## Contesto e obiettivo

Il workflow `registry-sync-gateway.yml` apre attualmente una PR su `scf-registry` ogni volta che riceve un evento `plugin-manifest-updated`. Il merge è sempre manuale.

L'obiettivo di questo piano è introdurre un sistema di **auto-merge condizionale** basato sul mittente dell'evento:

- **Mittente fidato (`Nemex81`):** la PR viene mergiata automaticamente entro pochi secondi — zero azioni manuali richieste.
- **Mittente esterno (contributore terzo):** la PR rimane aperta e attende la revisione e approvazione manuale del maintainer.

Il discriminante è `github.event.sender.login`, già disponibile nel contesto dell'evento `repository_dispatch`.

---

## Nota sulla revisione v1.1

La v1.0 prevedeva l'uso di `peter-evans/enable-pull-request-automerge@v3`. L'analisi di convalida ha rilevato che questa action richiede **branch protection rules con almeno un requisito attivo** sulla branch `base` della PR (documentazione ufficiale, sezione *Conditions*). Poiché `scf-registry` non ha CI né branch protection su `main`, l'azione fallirebbe a runtime.

La strategia correttiva adottata è il **merge diretto** tramite `gh pr merge --squash`, che non richiede branch protection e produce il merge immediato desiderato.

---

## Prerequisiti

Nessun prerequisito manuale richiesto su `scf-registry`.

**`REGISTRY_WRITE_TOKEN`** (usato sia per checkout che per `gh pr merge`): deve avere i seguenti scope sul repo `Nemex81/scf-registry`:
- `contents: write` — per scrivere il branch e mergiare il contenuto
- `pull_requests: write` — per eseguire `PUT /repos/.../pulls/{number}/merge` (chiamata interna di `gh pr merge`)

Per un **PAT classico** con scope `repo`, entrambi i requisiti sono coperti automaticamente. Per un **fine-grained PAT**, entrambi gli scope devono essere abilitati esplicitamente. La configurazione esistente soddisfa questo requisito se il token è di tipo `repo`-scope.

**`ENGINE_DISPATCH_TOKEN`** (in `notify-engine.yml` su `scf-pycode-crafter`): deve essere un PAT di proprietà di `Nemex81`. La condizione di auto-merge `sender.login == 'Nemex81'` si basa sul fatto che GitHub imposta `event.sender` all'utente proprietario del token usato per inviare il `repository_dispatch`. Se il token fosse di un altro utente o di una GitHub App, la condizione fallirebbe silenziosamente (il merge non avverrebbe, la PR resterebbe aperta).

---

## Modifica richiesta al workflow

### File da modificare

`.github/workflows/registry-sync-gateway.yml` in `spark-framework-engine`

### Stato attuale (ultimo step)

```yaml
- name: Create Pull Request on scf-registry
  uses: peter-evans/create-pull-request@v6
  with:
    token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
    path: scf-registry
    branch: sync/${{ env.PKG_ID }}-${{ env.VERSION }}
    title: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
    body: |
      Sync automatico generato dal motore `spark-framework-engine`.

      - **Pacchetto:** `${{ env.PKG_ID }}`
      - **Versione:** `${{ env.VERSION }}`
      - **Engine min:** `${{ env.ENGINE_MIN }}`
      - **Evento origine:** `plugin-manifest-updated`
      - **Repository sorgente:** `${{ github.event.sender.login }}`

      Aperto automaticamente da `registry-sync-gateway.yml`.
    commit-message: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
    delete-branch: true
```

### Stato target (due step)

**Step 1 — Aggiungere `id: cpr` allo step esistente** per esporre l'output con il numero della PR appena creata:

```yaml
- name: Create Pull Request on scf-registry
  id: cpr
  uses: peter-evans/create-pull-request@v6
  with:
    token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
    path: scf-registry
    branch: sync/${{ env.PKG_ID }}-${{ env.VERSION }}
    title: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
    body: |
      Sync automatico generato dal motore `spark-framework-engine`.

      - **Pacchetto:** `${{ env.PKG_ID }}`
      - **Versione:** `${{ env.VERSION }}`
      - **Engine min:** `${{ env.ENGINE_MIN }}`
      - **Evento origine:** `plugin-manifest-updated`
      - **Repository sorgente:** `${{ github.event.sender.login }}`

      Aperto automaticamente da `registry-sync-gateway.yml`.
    commit-message: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
    delete-branch: true
```

**Step 2 — Aggiungere nuovo step per auto-merge condizionale** immediatamente dopo il precedente:

```yaml
- name: Auto-merge se mittente fidato
  if: ${{ github.event.sender.login == 'Nemex81' && steps.cpr.outputs.pull-request-number != '' }}
  run: gh pr merge ${{ steps.cpr.outputs.pull-request-number }} --squash --repo Nemex81/scf-registry
  env:
    GH_TOKEN: ${{ secrets.REGISTRY_WRITE_TOKEN }}
```

---

## Workflow completo risultante

Di seguito il contenuto integrale del file dopo la modifica, pronto per essere committato:

```yaml
name: Registry Sync Gateway

on:
  repository_dispatch:
    types:
      - plugin-manifest-updated

jobs:
  sync-registry:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout scf-registry
        uses: actions/checkout@v4
        with:
          repository: Nemex81/scf-registry
          token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
          path: scf-registry

      - name: Validate payload
        run: |
          PKG_ID="${{ github.event.client_payload.pkg_id }}"
          VERSION="${{ github.event.client_payload.version }}"
          ENGINE_MIN="${{ github.event.client_payload.engine_min }}"
          if [ -z "$PKG_ID" ] || [ -z "$VERSION" ] || [ -z "$ENGINE_MIN" ]; then
            echo "::error::Payload validation failed: pkg_id='$PKG_ID' version='$VERSION' engine_min='$ENGINE_MIN'"
            exit 1
          fi
          echo "PKG_ID=$PKG_ID" >> "$GITHUB_ENV"
          echo "VERSION=$VERSION" >> "$GITHUB_ENV"
          echo "ENGINE_MIN=$ENGINE_MIN" >> "$GITHUB_ENV"

      - name: Update registry.json
        run: |
          python3 - <<'EOF'
          import json
          import os
          from datetime import datetime, timezone

          pkg_id = os.environ["PKG_ID"]
          version = os.environ["VERSION"]
          engine_min = os.environ["ENGINE_MIN"]

          registry_path = "scf-registry/registry.json"
          with open(registry_path, "r", encoding="utf-8") as f:
              data = json.load(f)

          packages = data.get("packages", [])
          found = False
          for pkg in packages:
              if pkg.get("id") == pkg_id:
                  pkg["latest_version"] = version
                  pkg["engine_min_version"] = engine_min
                  found = True
                  break

          if not found:
              raise ValueError(f"Package '{pkg_id}' not found in registry.json")

          data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

          with open(registry_path, "w", encoding="utf-8") as f:
              json.dump(data, f, indent=2, ensure_ascii=False)
              f.write("\n")

          print(f"Updated {pkg_id} to version {version} (engine_min={engine_min})")
          EOF

      - name: Create Pull Request on scf-registry
        id: cpr
        uses: peter-evans/create-pull-request@v6
        with:
          token: ${{ secrets.REGISTRY_WRITE_TOKEN }}
          path: scf-registry
          branch: sync/${{ env.PKG_ID }}-${{ env.VERSION }}
          title: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
          body: |
            Sync automatico generato dal motore `spark-framework-engine`.

            - **Pacchetto:** `${{ env.PKG_ID }}`
            - **Versione:** `${{ env.VERSION }}`
            - **Engine min:** `${{ env.ENGINE_MIN }}`
            - **Evento origine:** `plugin-manifest-updated`
            - **Repository sorgente:** `${{ github.event.sender.login }}`

            Aperto automaticamente da `registry-sync-gateway.yml`.
          commit-message: "sync: ${{ env.PKG_ID }} ${{ env.VERSION }}"
          delete-branch: true

      - name: Auto-merge se mittente fidato
        if: ${{ github.event.sender.login == 'Nemex81' && steps.cpr.outputs.pull-request-number != '' }}
        run: gh pr merge ${{ steps.cpr.outputs.pull-request-number }} --squash --repo Nemex81/scf-registry
        env:
          GH_TOKEN: ${{ secrets.REGISTRY_WRITE_TOKEN }}
```

---

## Riepilogo delle modifiche

| Elemento | Prima | Dopo |
|---|---|---|
| Step `Create PR` | nessun `id` | aggiunto `id: cpr` |
| Auto-merge | assente | nuovo step condizionale |
| Condizione | n/a | `sender.login == 'Nemex81'` |
| Merge method | n/a | squash |
| Strumento usato | n/a | `gh pr merge` (GitHub CLI) |
| Branch PR | rimane | rimane (delete-branch: true) |

---

## Comportamento atteso post-implementazione

**Caso A — Tu (Nemex81) pusci su scf-pycode-crafter:**
1. `notify-engine.yml` invia `repository_dispatch` con `sender.login = Nemex81`
2. Il gateway apre la PR su `scf-registry`
3. Lo step `Auto-merge` si attiva (`if` è vero)
4. GitHub merge automaticamente la PR entro pochi secondi
5. `registry.json` aggiornato — zero azioni manuali

**Caso B — Contributore esterno pusha sul suo repo plugin:**
1. `notify-engine.yml` invia `repository_dispatch` con `sender.login = contributor_username`
2. Il gateway apre la PR su `scf-registry`
3. Lo step `Auto-merge` viene saltato (`if` è falso)
4. La PR rimane aperta, Nemex81 riceve notifica GitHub
5. Revisione e merge manuali da parte del maintainer

---

## Criteri di accettazione

- [ ] Il file `registry-sync-gateway.yml` contiene `id: cpr` sullo step `Create Pull Request`
- [ ] Il file contiene lo step `Auto-merge se mittente fidato` con la condizione corretta
- [ ] Lo step usa `gh pr merge` con flag `--squash --repo Nemex81/scf-registry`
- [ ] Il token è passato tramite `env.GH_TOKEN` (non come input action)
- [ ] Il workflow non introduce nuovi secret (usa `REGISTRY_WRITE_TOKEN` già esistente)
- [ ] Test manuale: push innocuo su `scf-pycode-crafter` → PR aperta e mergiata automaticamente
- [ ] Test manuale documentato nel commit message o in un commento al piano

---

## Note per il maintainer

Lo step di auto-merge usa `gh pr merge` (GitHub CLI), già preinstallato nei runner `ubuntu-latest`. Non introduce dipendenze esterne aggiuntive rispetto a `create-pull-request`. Il `REGISTRY_WRITE_TOKEN` già configurato fornisce i permessi necessari tramite variabile d'ambiente `GH_TOKEN` (richiede scope `contents: write` + `pull_requests: write`, o `repo` scope per PAT classici).

### Come funziona la condizione `sender.login == 'Nemex81'`

Il workflow `notify-engine.yml` su `scf-pycode-crafter` invia il `repository_dispatch` tramite una chiamata API autenticata con `ENGINE_DISPATCH_TOKEN`. GitHub imposta `github.event.sender.login` all'utente proprietario di quel token. Se `ENGINE_DISPATCH_TOKEN` appartiene a `Nemex81`, la condizione risulta vera e il merge è automatico. Se il dispatch proviene da un repo di un contributore esterno con il proprio token, `sender.login` sarà il nome del contributore e la condizione sarà falsa — la PR resta aperta per revisione manuale.

Il flag `--repo Nemex81/scf-registry` è obbligatorio perché il workflow gira su `spark-framework-engine` ma la PR target è su `scf-registry` — senza specificarlo il CLI cercherebbe la PR nel repo sbagliato.

### Perché non `enable-pull-request-automerge`

L'action `peter-evans/enable-pull-request-automerge@v3` richiede che la branch `base` della PR abbia **branch protection rules con almeno un requisito attivo** (doc ufficiale, sezione *Conditions*). `scf-registry` non ha CI né branch protection su `main`, quindi l'azione fallirebbe. `gh pr merge --squash` è la soluzione più semplice e affidabile per questo scenario.

*Documento generato il 2026-04-01 — v1.2 (rev. validazione prerequisiti)*
