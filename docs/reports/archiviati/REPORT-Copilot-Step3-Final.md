# REPORT — Step 3 Final: Separazione Netta Universo A/B

**Data**: 2025-07-15
**Agente**: spark-engine-maintainer
**Branch**: `feature/dual-mode-manifest-v3.1`
**Suite validation**: 446 passed, 9 skipped, 0 failed

> **Nota:** Il report di implementazione completo di Step 3 è in
> `docs/reports/REPORT-Copilot-Step3-Implementation.md`.
> Questo file aggiuntivo soddisfa il criterio 8 del prompt Step 3 che richiede
> le conferme esplicite di seguito.

---

## Conferme esplicite richieste dal prompt Step 3

### Conferma 1 — "Il Server MCP non scrive più file nel workspace utente"

**Stato: PARZIALMENTE VERA**

- ✅ Per l'Universo B (Plugin Manager): `scf_plugin_install`, `scf_plugin_remove`,
  `scf_plugin_update` delegano interamente a `PluginManagerFacade` che è indipendente
  dal server MCP. Il Plugin Manager scrive nel workspace in modo autonomo.

- ⚠️ Per l'Universo A (`scf_install_package`): il tool continua a scrivere
  `workspace_files` nel workspace tramite la catena
  `_install_package_v3` → `_install_workspace_files_v3` (stub) → `PluginInstaller.install_from_store()`.
  Questo è il comportamento pre-Step 3 mantenuto per continuità.
  La risoluzione richiede la **Decisione D1** di Nemex81 (vedi "Decisioni aperte" sotto).

### Conferma 2 — "I plugin installati via scf_install_plugin producono file fisici in .github/ indipendentemente dal server MCP"

**Stato: VERA** ✅

`scf_plugin_install` delega a `PluginManagerFacade.install()` che chiama
`PluginInstaller.install_files()`. L'installazione avviene tramite download HTTP
diretto da GitHub e scrittura via `WorkspaceWriteGateway`, senza alcuna dipendenza
dal server MCP o dai suoi tool.

---

## Decisioni aperte (da Nemex81)

### D1 — `scf_install_package` e workspace_files
> In uno scenario futuro, il percorso `scf_install_package` deve smettere
> completamente di scrivere `workspace_files` in favore del Plugin Manager?

**Pendente.** La risposta determina se la Conferma 1 può diventare "VERA" incondizionata.

### D2 — `spark-base` come plugin
> `spark-base` dichiara `workspace_files` ma non `plugin_files`.
> La sua migrazione da Universo A a Universo B rientra nello scope di Step 3?

**Pendente.** Nessun `package-manifest.json` reale usa il campo `plugin_files` al momento.

---

## Debito tecnico residuo

Per la lista completa, vedere `docs/reports/REPORT-Copilot-Step4-Consolidation.md`
sezione "Issue da aprire".

---

*Report generato da spark-engine-maintainer — Step 3 Final (criterio 8).*
