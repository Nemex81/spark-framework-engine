---
spark: true
scf-file-role: doc
scf-protected: false
scf-version: 1.0.0
scf-owner: spark-framework-engine
title: Piano Tecnico Fase 2 — Boot deterministico
generated_by: scf-refactoring-plan-generate-validate-v2
---

# Piano Tecnico Fase 2 — Boot deterministico

## 1. Obiettivo

Riscrivere `spark/boot/sequence.py` come sequenza lineare e ordinata di inizializzazioni; consolidare in `spark/boot/validation.py` le verifiche post-costruzione. Eliminare ogni fallback silenzioso.

## 2. Criterio di completamento

- Lettura lineare di `spark/boot/sequence.py` permette di capire l'ordine esatto di costruzione e quale componente può causare quale errore.
- Ogni eccezione catturata in `_build_app` ora termina con messaggio diagnostico esplicito su `stderr` e `SystemExit` non zero.
- `spark/boot/validation.py` espone funzioni `validate_<componente>()` che restituiscono `(ok: bool, reason: str)`.
- Output `scf_verify_workspace` resta identico alla baseline Fase 1.

## 3. File coinvolti

- `spark/boot/sequence.py` — riscrittura completa di `_build_app`.
- `spark/boot/validation.py` — nuove funzioni di validazione estratte dai blocchi `try/except` permissivi attuali.
- `spark/core/constants.py` — aggiunta eventuale di costanti `BOOT_ERROR_*`.

## 4. Operazioni specifiche

1. Identificare nel `_build_app` originale (riga 8348) tutti i `try/except` che oggi loggano warning e proseguono (es. il caricamento di `engine-manifest.json` e la `populate_mcp_registry` fallibile).
2. Per ognuno, decidere: errore fatale → `SystemExit` con messaggio; errore degradato → ramo esplicito con flag visibile in `scf_verify_workspace`.
3. Estrarre ogni validazione in `validate_workspace_context()`, `validate_inventory()`, `validate_registry()`, `validate_engine_manifest()`.
4. Riordinare la sequenza in modo che ogni step abbia un solo prerequisito esplicito.
5. Rimuovere i fallback silenziosi.

## 5. Dipendenze dalla fase precedente

- Fase 1 chiusa: nessun marker `FASE1-RIASSEGNA` aperto.
- Suite test stabile.

## 6. Rischi specifici

- **Cambio di comportamento in caso di errore.** Trasformare un warning in fatal può rompere installazioni esistenti. Mitigazione: feature flag `SPARK_STRICT_BOOT=1` per abilitare il nuovo comportamento, default off in Fase 2; default on in Fase 3.
- **Test che dipendono da boot permissivo.** Mitigazione: marker `pytest.mark.legacy_boot` per i test che richiedono il vecchio comportamento.

---

## DRIFT — Note di allineamento post-Fase 0/1 (2026-05-01)

Aggiornamenti alla struttura reale rispetto a quanto scritto sopra al momento
della stesura del piano:

- **Sezione 4.1 riferimento riga monolite:** `_build_app` è descritta come
  “alla riga 8348” del file monolite. Quella riga non esiste più. La funzione
  ora vive in `spark/boot/sequence.py`.
- **`spark/boot/validation.py`:** il file non esiste ancora. Era pianificato
  come placeholder in Fase 0 Step 08 ma non è stato creato. Sarà il primo
  artefatto da creare in Fase 2 (nuova, non estratta dal monolite).
- **`spark/workspace/policy.py`:** il piano di Fase 3 e questo piano citano
  `update_policy.py`; il file si chiama `policy.py`. Step 1.1 di Fase 1 prevede
  la rinomina. Se non ancora eseguita all’apertura di Fase 2, aggiornare gli
  import di conseguenza.
- **Metodo istanza residuo:** `SparkFrameworkEngine._install_package_v3_into_store`
  rimane in `spark/boot/engine.py` ma non è più chiamato (fix Step 1.4 Fase 1).
  Candidato a rimozione come prima pulizia di Fase 2.
