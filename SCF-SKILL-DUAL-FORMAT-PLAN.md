# Piano Tecnico Implementativo — Supporto Doppio Formato Skill in SCF

Data: 30 marzo 2026
Repo: spark-framework-engine
Versione piano: 2 (post-validazione e post-implementazione)
Ambito: discovery skill dual-format nel motore SCF con retrocompatibilita' completa

---

## 1) Esito convalida progetto aggiornato

Esito: PASS

Evidenze tecniche verificate:
- ENGINE_VERSION allineata a 1.1.0 in spark-framework-engine.py
- list_skills() aggiornato per discovery dual-format
- README allineato con Tools Disponibili (18)
- CHANGELOG.md presente con voce [1.1.0]
- test suite verde: 32 passed, 12 subtests passed

---

## 2) Obiettivo implementativo

Abilitare la scoperta delle skill in due formati contemporaneamente:
- Formato legacy piatto: .github/skills/*.skill.md
- Formato standard Agent Skills: .github/skills/<skill-name>/SKILL.md

Vincolo primario: zero breaking change per i repository che usano solo formato legacy.

---

## 3) Specifica tecnica implementata

### 3.1 Metodo target

File: spark-framework-engine.py
Classe: FrameworkInventory
Metodo: list_skills()

### 3.2 Algoritmo

Passo A - Discovery legacy:
- usa _list_by_pattern(skills_root, "*.skill.md", "skill")
- mantiene comportamento storico invariato

Passo B - Costruzione set deduplica logica:
- crea seen con chiavi normalizzate da flat
- normalizzazione: removesuffix(".skill")

Passo C - Discovery standard a sottocartelle:
- itera skills_root.iterdir() in ordine sorted
- seleziona solo directory contenenti SKILL.md
- crea FrameworkFile con name uguale al nome directory

Passo D - Deduplica con priorita' legacy:
- calcola key normalizzata per entry standard
- include entry standard solo se key non e' in seen
- su collisione foo.skill.md vs foo/SKILL.md prevale flat

Passo E - Ordinamento finale:
- ritorna combined ordinato alfabeticamente per name

### 3.3 Compatibilita' API

Nessun cambiamento a:
- firma dei tool
- URI resources
- shape di risposta dei tool
- comportamento di skills://{name} e scf_get_skill

---

## 4) Implementazione test

File test aggiunto: tests/test_framework_inventory_skills.py

Copertura minima implementata:
- scoperta simultanea flat + standard
- collisione nome con prevalenza flat
- skills directory assente -> lista vuota
- skills directory vuota -> lista vuota

Approccio test:
- unittest standard library
- fixture con TemporaryDirectory
- caricamento modulo engine via importlib + mock mcp

---

## 5) Requisiti non funzionali soddisfatti

- Retrocompatibilita' con repository legacy
- Determinismo risultato tramite ordinamento
- Nessuna dipendenza runtime aggiuntiva
- Nessun impatto su performance significativo (scan locale limitato a .github/skills)

---

## 6) Rischi residui e mitigazioni

Rischio 1: collisioni non intenzionali tra nomi legacy e standard.
Mitigazione: regola esplicita di priorita' legacy documentata e testata.

Rischio 2: naming ambiguo con suffisso .skill nelle directory standard.
Mitigazione: deduplica su chiave normalizzata (removesuffix(".skill")).

Rischio 3: divergenza futura tra implementazione e documentazione.
Mitigazione: aggiornamento README + CHANGELOG nella stessa release.

---

## 7) Artefatti di rilascio collegati

- spark-framework-engine.py: ENGINE_VERSION 1.1.0 e list_skills dual-format
- tests/test_framework_inventory_skills.py: nuova suite specifica
- README.md: Tools Disponibili (18) allineato
- CHANGELOG.md: voce [1.1.0]

---

## 8) Criteri di accettazione (Definition of Done)

- [x] supporto dual-format attivo in list_skills()
- [x] priorita' legacy su collisione nome
- [x] ordinamento alfabetico output
- [x] nessuna regressione su suite esistente
- [x] test dedicati aggiunti e verdi
- [x] ENGINE_VERSION allineata a 1.1.0
- [x] CHANGELOG aggiornato
- [x] README allineato

---

## 9) Procedura operativa replicabile (future patch)

1. Implementare eventuale estensione di discovery solo in FrameworkInventory.list_skills().
2. Mantenere sempre first-pass legacy e deduplica con priorita' flat.
3. Aggiornare test dedicati in tests/test_framework_inventory_skills.py.
4. Eseguire pytest -q e richiedere suite verde.
5. Allineare ENGINE_VERSION, CHANGELOG e README nella stessa change-set.

---

## 10) Stato finale

Modifica introdotta, verificata e rilasciata.
Il piano passa da "proposta" a "piano tecnico as-built" utilizzabile come riferimento implementativo per evoluzioni future.
