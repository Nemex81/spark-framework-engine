# Piano Tecnico - Harden multi-package SCF

Stato: completato

Scope principale:
- Root di riferimento: scf-pycode-crafter
- Repo coinvolti: scf-pycode-crafter, spark-framework-engine
- Obiettivo: rendere robusta la coesistenza di piu pacchetti SCF nello stesso workspace prima di espandere il catalogo plugin.

Decisioni di validazione gia fissate:
- Il piano generale e corretto: schema prima, poi diagnostica, poi enforcement, poi dipendenze.
- Il package manifest deve diventare auto-descrittivo.
- Le dipendenze restano semplici: lista di package_id, senza range di versione in questa iterazione.
- La conflict detection sui file va introdotta con policy iniziale error-only nel primo rilascio utile.
- Il path del changelog deve restare canonico e non tornare al file legacy.

Correzioni progettuali obbligatorie rispetto alla proposta iniziale:
- Usare un campo singolare per il changelog esplicito. Nome proposto: changelog_path.
- In scf-pycode-crafter il file canonico resta .github/changelogs/scf-pycode-crafter.md.
- Non reintrodurre .github/FRAMEWORK_CHANGELOG.md nel campo files del package manifest v2.
- Le policy warn e skip non vanno rese operative finche ownership e diagnostica non sono chiari e testati; nel primo tag la semantica effettiva resta error.

Non obiettivi di questa iterazione:
- Nessuna installazione automatica delle dipendenze.
- Nessuna merge strategy tra file omonimi di pacchetti diversi.
- Nessuna compatibilita retroattiva con range semantici nelle dipendenze.

## [x] Fase 1 - Bloccare schema e contratto dati

Obiettivo:
- Definire il package-manifest.json v2 come contratto stabile tra pacchetto e motore.

Interventi previsti:
- Aggiornare package-manifest.json di scf-pycode-crafter con i campi schema_version, display_name, description, author, min_engine_version, dependencies, conflicts, file_ownership_policy, changelog_path.
- Allineare il campo files al contenuto reale del repo, mantenendo il changelog canonico in .github/changelogs/scf-pycode-crafter.md.
- Definire formalmente i valori ammessi per file_ownership_policy, ma implementare subito solo error.
- Documentare nel piano e nel README plugin la convenzione del changelog per-package.

Criteri di accettazione:
- Esiste uno schema v2 coerente e leggibile da umano.
- Il manifest del plugin non contiene path legacy non canonici.
- dependencies e conflicts sono liste di stringhe package_id.
- min_engine_version e changelog_path sono presenti e non ambigui.

File attesi:
- scf-pycode-crafter/package-manifest.json
- scf-pycode-crafter/README.md

## [x] Fase 2 - Integrita manifest e diagnostica workspace

Obiettivo:
- Rendere verificabile lo stato reale dei file installati dal motore.

Interventi previsti:
- Aggiungere ManifestManager.verify_integrity() nel motore.
- Introdurre un report strutturato con almeno: missing, modified, ok, duplicate_owners, orphan_candidates.
- Aggiungere il tool MCP scf_verify_workspace.
- Definire se orphan_candidates significhi file presenti sotto .github non tracciati dal manifest oppure solo file attesi dal package manifest ma non presenti nel manifest runtime.

Criteri di accettazione:
- Il motore restituisce un report deterministico e testabile.
- Un file mancante o modificato viene rilevato senza falsi positivi sul caso nominale.
- Il tool ha docstring valida, naming coerente e contatori aggiornati.

File attesi:
- spark-framework-engine/spark-framework-engine.py
- spark-framework-engine/tests/test_manifest_integrity.py oppure estensione dei test esistenti
- spark-framework-engine/README.md
- eventuale documentazione motore correlata

## [x] Fase 3 - Conflict detection e ownership enforcement

Obiettivo:
- Impedire sovrascritture silenziose tra pacchetti diversi.

Interventi previsti:
- Prima di scrivere ogni file in scf_install_package, interrogare il manifest runtime per capire se il path e gia posseduto da un altro package.
- Bloccare l'installazione se il proprietario esistente e diverso dal package in installazione.
- Esporre nel risultato del tool l'elenco dei conflitti rilevati con package proprietario e path.
- Preparare il punto di estensione per file_ownership_policy, ma mantenere enforcement effettivo su error.
- Valutare transazionalita minima: se durante l'installazione compare un conflitto o un fetch fallisce, il risultato non deve lasciare uno stato ambiguo non segnalato.

Criteri di accettazione:
- Nessun file puo essere sovrascritto silenziosamente da un altro pacchetto.
- Un conflitto produce errore esplicito e riproducibile.
- I test coprono conflitto package-vs-package e reinstallazione dello stesso package.

File attesi:
- spark-framework-engine/spark-framework-engine.py
- spark-framework-engine/tests/test_package_installation_policies.py oppure estensione dei test esistenti

## [x] Fase 4 - Compatibilita motore e dipendenze dichiarative

Obiettivo:
- Preparare il sistema a dipendenze e compatibilita senza introdurre automazione prematura.

Interventi previsti:
- In scf_install_package verificare min_engine_version contro ENGINE_VERSION.
- Leggere dependencies dal package manifest remoto e fallire con messaggio chiaro se manca un package richiesto.
- Leggere conflicts dal package manifest remoto e bloccare l'installazione se un package incompatibile e gia installato.
- Esporre i nuovi campi in scf_get_package_info.

Criteri di accettazione:
- Installazione bloccata in modo esplicito se il motore e troppo vecchio.
- Installazione bloccata in modo esplicito se manca una dipendenza dichiarata.
- Installazione bloccata in modo esplicito se e presente un package in conflicts.
- scf_get_package_info mostra i campi nuovi del manifest.

File attesi:
- spark-framework-engine/spark-framework-engine.py
- spark-framework-engine/tests/test_package_manifest_v2.py oppure estensione dei test esistenti
- spark-framework-engine/README.md

## [x] Fase 5 - Allineamento contenuti plugin e documentazione

Obiettivo:
- Rendere scf-pycode-crafter il primo package conforme al contratto v2.

Interventi previsti:
- Aggiornare README del plugin con convenzione changelog per-package.
- Documentare i nuovi campi del package manifest e la semantica pratica di dependencies, conflicts e file_ownership_policy.
- Verificare che il changelog path dichiarato nel manifest esista davvero.
- Se necessario, aggiornare documentazione motore o skill che spiegano installazione e diagnostica pacchetti.

Criteri di accettazione:
- Il plugin e auto-consistente: manifest, README e file reali coincidono.
- La convenzione changelog e documentata una volta sola e senza ambiguita.

File attesi:
- scf-pycode-crafter/package-manifest.json
- scf-pycode-crafter/README.md
- eventuali documenti motore impattati

## [x] Fase 6 - Validazione finale e readiness al rollout

Obiettivo:
- Chiudere il ciclo con verifica tecnica completa e stato pronto al merge.

Interventi previsti:
- Eseguire pytest, ruff e mypy sulle aree toccate.
- Verificare il contatore tool del motore se viene introdotto scf_verify_workspace.
- Verificare output MCP dei tool toccati almeno su casi nominali ed error path principali.
- Aggiornare questo file marcando completate le fasi concluse.

Criteri di accettazione:
- Test verdi.
- Lint verde sulle aree modificate.
- Type checking verde sul motore.
- Nessuna discrepanza tra contatori tool, documentazione e implementazione.

## Ordine di implementazione raccomandato

1. Fase 1
2. Fase 2
3. Fase 3
4. Fase 4
5. Fase 5
6. Fase 6

## Nota operativa

Aggiornamento stato fasi durante il lavoro:
- Sostituire [ ] con [x] nel titolo della fase appena completata.
- Se una fase viene avviata ma non chiusa, annotare sotto il titolo i blocchi rimasti invece di marcarla completa.