"""Phase 0 helper: sostituisce blocchi di testo nel sorgente hub.

Legge un JSON con la lista di operazioni `{start, end, replacement}`.
Ogni op trova il primo `start`, poi cerca `end` dopo `start`, e sostituisce
il range `[start..end)` (start incluso, end escluso) con `replacement`.

Le operazioni vengono applicate dal fondo verso l'inizio per non spostare
gli offset delle operazioni successive.
"""
from pathlib import Path
import json
import sys

source = Path(sys.argv[1])
ops_file = Path(sys.argv[2])
ops = json.loads(ops_file.read_text(encoding="utf-8"))

text = source.read_text(encoding="utf-8")
located = []
for op in ops:
    s = text.index(op["start"])
    e = text.index(op["end"], s + len(op["start"]))
    located.append((s, e, op["replacement"], op["start"][:60]))
located.sort(key=lambda x: x[0], reverse=True)
for s, e, repl, label in located:
    print(f"replacing {e - s} chars after marker {label!r} with {len(repl)} chars")
    text = text[:s] + repl + text[e:]

source.write_text(text, encoding="utf-8")
print(f"new_size={len(text)}")
