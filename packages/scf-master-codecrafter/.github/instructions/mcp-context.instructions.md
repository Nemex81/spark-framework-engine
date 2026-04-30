---
scf_protected: false
scf_file_role: "instruction"
name: mcp-context
applyTo: "**"
scf_merge_strategy: "replace"
scf_version: "2.1.0"
package: scf-master-codecrafter
scf_merge_priority: 20
scf_owner: "scf-master-codecrafter"
spark: true
version: 1.0.0
---

# Instruction: MCP Context

Questa instruction si applica a tutto il workspace quando si opera in un contesto server MCP (FastMCP / mcp SDK).

## Regole fondamentali

- Il transport e stdio: **mai scrivere su stdout** al di fuori del canale JSON-RPC gestito dall'SDK
- Logging esclusivamente su `sys.stderr` o file — mai `print()` a stdout
- Il server e avviato con `mcp.run()`: non aggiungere entry point alternativi non coordinati
- Le variabili d'ambiente (`WORKSPACE_FOLDER`, ecc.) vanno lette all'avvio, non in lazy mode

## Tool MCP

- Ogni tool pubblico deve avere il decorator `@mcp.tool()` — nessun `async def scf_*` senza decorator
- La docstring del tool e la descrizione esposta al client: deve essere chiara, concisa, in inglese
- Il contatore dei tool registrati nel log (`Tools registered: N total`) deve essere aggiornato ad ogni aggiunta o rimozione
- I tool non devono avere effetti collaterali silenti: errori e stati anomali vanno restituiti come stringa di errore nel return, non sollevati come eccezioni non gestite

## Risorse MCP

- Le risorse esposte devono avere URI stabili e descrittivi
- Non esporre dati sensibili o path assoluti di sistema nelle risorse

## Compatibilita engine

- Verificare sempre `min_engine_version` nel manifest prima di usare feature introdotte in versioni recenti
- Se la versione engine non soddisfa il minimo, il pacchetto deve fallire con messaggio esplicito

## Debugging

- In caso di mancata risposta del server: verificare prima che stdout non sia contaminato
- Usare `mcp dev` o inspector per validare tool e risorse prima del deploy
