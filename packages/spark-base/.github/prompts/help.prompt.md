---
type: prompt
name: help
description: Spiega ruolo, responsabilita e workflow di un agente del framework.
scf_protected: false
scf_file_role: "prompt"
scf_merge_priority: 10
scf_merge_strategy: "replace"
scf_version: "1.2.0"
spark: true
scf_owner: "spark-base"
---

Spiega come funziona l'agente ${input:Nome agente (es: code-Agent-Code, code-Agent-Design...)}.

Se il file `.github/agents/${input:Nome agente (es: code-Agent-Code, code-Agent-Design...)}.md`
esiste nel workspace corrente, leggilo e produci una spiegazione strutturata.

Se il file non esiste nel pacchetto base ma esiste in un pacchetto plugin installato,
usa la definizione disponibile nel workspace installato e chiarisci che si tratta di
un agente fornito da un pacchetto aggiuntivo, ad esempio `scf-master-codecrafter`.

Se il file non esiste in nessun pacchetto installato, interrompi e segnala che l'agente
non è disponibile nel workspace corrente.

Produci sempre una spiegazione strutturata:

1. Scopo principale (1 riga)
2. Quando usarlo (trigger tipici)
3. Cosa produce in output
4. Gate di completamento
5. Comando per attivarlo direttamente
