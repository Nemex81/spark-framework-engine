# Fase 4 — Decorator FastMCP dinamici + alias retrocompatibili
# Dipende da: Fase 3
# Effort stimato: S
# File target:
#   - spark-framework-engine/spark-framework-engine.py
#   - spark-framework-engine/tests/test_resource_aliases.py (nuovo)

## Prerequisiti

- [ ] Fase 3 completata
- [ ] Tutti i tool override funzionanti

## Task

- [ ] 4.1 Refactor handler `agents://{name}`
      File: `spark-framework-engine.py`
      Riga partenza: 2440.
      Logica: delega a `registry.resolve(f"agents://{name}")`,
      lettura del file ritornato. Mantiene errore "not found" se
      URI non registrato.

- [ ] 4.2 Refactor handler `skills://{name}` e `instructions://{name}`
      File: `spark-framework-engine.py`
      Righe partenza: 2451 (skills), 2463 (instructions).
      Stessa logica del 4.1.

- [ ] 4.3 Implementare alias `engine-skills://{name}`
      File: `spark-framework-engine.py`
      Riga partenza: 2478.
      Logica: redirect a `skills://{name}` con flag
      `_log_alias_warning_once` (set di URI già loggati).
      Logging:
      `[SPARK-ENGINE][WARN] URI deprecato engine-skills://{name}
       → usare skills://{name}. Alias rimosso in v4.0.`

- [ ] 4.4 Implementare alias `engine-instructions://{name}`
      File: `spark-framework-engine.py`
      Riga partenza: 2495.
      Stessa logica del 4.3.

- [ ] 4.5 Refactor handler `prompts://{name}` per usare registry
      File: `spark-framework-engine.py`
      Riga partenza: 2510.

- [ ] 4.6 Test alias retrocompatibili
      File: `tests/test_resource_aliases.py`
      Casi: `engine-skills://name` ritorna stesso contenuto di
      `skills://name`, warning loggato una sola volta per URI,
      lista risorse engine via `agents://list` include
      spark-welcome.

## Test di accettazione

- [ ] Handler unificati funzionano per agenti engine e pacchetto.
- [ ] Override prevale su engine via il nuovo handler.
- [ ] Alias `engine-skills://` ritorna contenuto identico a
      `skills://`.
- [ ] Warning su stderr loggato una volta per ogni URI alias
      richiesto.

## Note tecniche

- Il set `_logged_alias_uris` deve essere instance-level su
  `SparkFrameworkEngine` per persistere durante la sessione MCP.
- Non aggiungere lock: il logging duplicato è preferibile a un
  bottleneck di concurrency (impatto trascurabile).
- L'alias funziona solo per `engine-skills://` e
  `engine-instructions://`. Non estendere ad altri URI.
