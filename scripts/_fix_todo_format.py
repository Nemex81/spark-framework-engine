"""Fix formatting of docs/todo.md — adds blank lines before/after headings."""
from __future__ import annotations
import pathlib
import re
import sys

TODO_PATH = pathlib.Path(__file__).parent.parent / "docs" / "todo.md"

raw = TODO_PATH.read_text(encoding="utf-8")

lines = raw.splitlines()
out: list[str] = []

for i, line in enumerate(lines):
    is_heading = line.startswith("# ") or line.startswith("## ") or line.startswith("### ")
    is_hr = line.strip() == "---"

    # Blank line BEFORE heading/hr (except first line)
    if (is_heading or is_hr) and i > 0:
        if out and out[-1] != "":
            out.append("")

    out.append(line)

    # Blank line AFTER heading (not after ---; next line handles it)
    if is_heading:
        # Peek next line: if already blank, skip
        if i + 1 < len(lines) and lines[i + 1] != "":
            out.append("")

# Remove trailing blank lines at EOF, add single trailing newline
while out and out[-1] == "":
    out.pop()

result = "\n".join(out) + "\n"
TODO_PATH.write_text(result, encoding="utf-8", newline="\n" if sys.platform != "win32" else None)

# Re-read for verification
final_lines = TODO_PATH.read_text(encoding="utf-8").splitlines()
print(f"Righe totali: {len(final_lines)}")

checks = [
    ("# SPARK Framework Engine", "Heading principale"),
    ("Refactoring-Estrazione Fase 2 COMPLETATA", "Stato piano"),
    ("## Sessione 2026-05-05", "Sezione sessione"),
    ("Refactoring Fase 1 — Estrazione", "RFase1"),
    ("Refactoring Fase 2 — Estrazione", "RFase2"),
    ("P6 — Fase 3 — Promozione", "P6 entry"),
    ("IN ATTESA DI CONFERMA DA LUCA", "P6 stato"),
    ("P5 — ~~Payload non uniforme", "P5 entry"),
    ("- **Stato:** RISOLTO.", "P5 stato risolto"),
    ("P4 — ~~Logica duplicata", "P4 entry"),
    ("NO-OP.", "P4 no-op"),
    ("## Storico sessioni precedenti", "Storico"),
]
all_ok = True
for txt, label in checks:
    found = any(txt in l for l in final_lines)
    status = "OK" if found else "MANCANTE"
    if not found:
        all_ok = False
    print(f"  [{status}] {label}")

# Check blank lines before ## / ### headings
h_issues: list[str] = []
for i, l in enumerate(final_lines):
    if l.startswith("## ") or l.startswith("### "):
        prev = final_lines[i - 1] if i > 0 else ""
        if prev.strip() != "":
            h_issues.append(f"L{i+1}: {l[:50]} (prev={repr(prev[:30])})")

if h_issues:
    print(f"Heading senza blank line prima ({len(h_issues)}):")
    for h in h_issues:
        print(f"  FIX: {h}")
    all_ok = False
else:
    print("Blank lines prima degli heading: OK")

print("RESULT:", "PASS" if all_ok else "FAIL")
