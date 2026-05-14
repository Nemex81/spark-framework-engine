> **STATO: COMPLETATO** — Archiviato il 2026-05-14 (ENGINE_VERSION 3.6.0).
> Documento di sola lettura. Non modificare.

***

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
della stesura del piano. **Tutti risolti in Fase 2 (2026-05-01).**

- **Sezione 4.1 riferimento riga monolite:** `_build_app` era descritta come
  "alla riga 8348" del file monolite. La funzione ora vive in `spark/boot/sequence.py`.
  `[RISOLTO]`
- **`spark/boot/validation.py`:** creato in Step 2.1 — funzione `validate_engine_manifest()`
  con feature flag `SPARK_STRICT_BOOT`. `[RISOLTO]`
- **`spark/workspace/policy.py`:** rinominato `update_policy.py` in Fase 1 Step 1.1.
  `[RISOLTO]`
- **Metodo istanza residuo:** `SparkFrameworkEngine._install_package_v3_into_store`
  rimosso in Step 2.0. `[RISOLTO]`

## Chiusura Fase 2 (2026-05-01)

| Step | Descrizione | File | Stato |
|------|-------------|------|-------|
| 2.0 | Rimozione metodo istanza residuo `_install_package_v3_into_store` | `spark/boot/engine.py` | COMPLETATO |
| 2.1 | Creazione `spark/boot/validation.py` con `validate_engine_manifest()` | `spark/boot/validation.py` | COMPLETATO |
| 2.2 | Sostituzione try/except inline con `validate_engine_manifest()` | `spark/boot/sequence.py` | COMPLETATO |

**Invariante finale:** 0 failed / 282 passed / 8 skipped confermata post-ogni-step.
