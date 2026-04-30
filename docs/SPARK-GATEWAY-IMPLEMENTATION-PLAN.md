# SPARK Gateway Pattern — Implementation Plan

## Sommario esecutivo
Obiettivo: garantire accesso stabile e minimale agli agenti SPARK via Copilot, separando risorse gateway (Layer 0) da tutto il resto (Layer 1/2 via MCP).

## Architettura risultante
- Layer 0: solo file gateway in .github/
- Layer 1: tutte le risorse via MCP
- Layer 2: pacchetti modulari, nessun impatto su Layer 0

## Interventi

### Intervento 1 — Aggiornamento scf_bootstrap_workspace
- File target: spark-framework-engine.py
- Tipo: MODIFICA
- Punto di inserimento: def scf_bootstrap_workspace
- Dipende da: nessuno
- Descrizione: Garantire che vengano copiati solo i file gateway Layer 0 (spark-assistant.agent.md, spark-guide.agent.md, spark-assistant-guide.instructions.md, scf-*.prompt.md) e che la sentinella sia sempre aggiornata.
- Snippet: logica già presente, solo refactor per chiarezza e commenti.
- Rischio regressione: BASSO
- Motivo rischio: logica già idempotente, nessun impatto su altri flussi.

### Intervento 2 — Aggiornamento documentazione e template
- File target: docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md, CLAUDE.md, copilot-instructions.md (template)
- Tipo: CREAZIONE
- Punto di inserimento: nuovi file
- Dipende da: Intervento 1
- Descrizione: Documentare la strategia, fornire template minimi per Layer 0.
- Snippet: vedi sezione "Struttura file da creare".
- Rischio regressione: BASSO
- Motivo rischio: solo aggiunta documentazione e template.

## Struttura file da creare
- docs/SPARK-GATEWAY-IMPLEMENTATION-PLAN.md (questo file)
- CLAUDE.md (template orientamento Claude)
- copilot-instructions.md (template Layer 0, solo orientamento e URI MCP)

## Diagramma testuale Gateway Pattern
```
[.github/agents/spark-assistant.agent.md] --(loader)--> [MCP: scf_get_agent()]
[.github/agents/spark-guide.agent.md] --(onboarding)--> [MCP: scf_list_available_agents()]
[workspace user] --(richiesta)--> [Layer 0] --(pull)--> [Layer 1 MCP] --(proxy)--> [Layer 2 pacchetti]
```

## Criteri di accettazione
- Layer 0 contiene solo i file gateway
- scf_bootstrap_workspace non sovrascrive file utente
- Tutte le risorse extra sono accessibili via MCP
- Documentazione aggiornata

## Rischi residui
- Engine non avviato → risorse MCP non accessibili (limite fisico)
- Workspace con override manuali non tracciati → warning già gestito
