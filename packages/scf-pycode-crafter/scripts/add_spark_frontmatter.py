"""
Step 1 — Add spark: true + version: 1.2.1 to all SCF package components.
Run once from the repository root.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parent.parent
NEW_VERSION = "1.2.1"
SKIP_FILES = {"model-policy.instructions.md"}


def derive_component_name(path: Path) -> str:
    n = path.name
    if n == "SKILL.md":
        return path.parent.name  # folder name = component name
    for sfx in (".skill.md", ".instructions.md", ".prompt.md"):
        if n.endswith(sfx):
            return n[: -len(sfx)]
    return n[:-3]  # strip .md


def update_frontmatter(path: Path) -> str:
    """Add spark: true, update version, add name if missing. Returns status string."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"ERROR ({exc})"

    if not content.startswith("---\n"):
        return "SKIP (no frontmatter)"

    end = content.find("\n---", 4)
    if end == -1:
        return "SKIP (no closing ---)"

    fm_text = content[4:end]          # frontmatter body (without surrounding ---)
    body = content[end:]              # \n---\n... (rest of file)

    lines = fm_text.split("\n")

    has_name = any(ln.startswith("name:") for ln in lines)
    has_spark = any(ln.startswith("spark:") for ln in lines)

    new_lines: list[str] = []
    for ln in lines:
        if ln.startswith("version:"):
            new_lines.append(f"version: {NEW_VERSION}")
        elif ln.startswith("spark:"):
            has_spark = True
            new_lines.append("spark: true")
        else:
            new_lines.append(ln)

    if not has_name:
        name = derive_component_name(path)
        insert_pos = min(1, len(new_lines))
        new_lines.insert(insert_pos, f"name: {name}")

    if not has_spark:
        # Insert before trailing empty lines
        pos = len(new_lines)
        while pos > 0 and new_lines[pos - 1] == "":
            pos -= 1
        new_lines.insert(pos, "spark: true")

    new_fm = "\n".join(new_lines)
    new_content = f"---\n{new_fm}{body}"

    if new_content == content:
        return "UNCHANGED"

    path.write_text(new_content, encoding="utf-8")
    return "UPDATED"


def collect_files() -> list[Path]:
    targets: list[Path] = []
    # Agents
    for p in sorted((ROOT / ".github" / "agents").glob("*.md")):
        targets.append(p)
    # Flat skill files
    for p in sorted((ROOT / ".github" / "skills").glob("*.skill.md")):
        targets.append(p)
    # Folder SKILL.md
    for p in sorted((ROOT / ".github" / "skills").rglob("SKILL.md")):
        targets.append(p)
    # Instructions (skip model-policy)
    for p in sorted((ROOT / ".github" / "instructions").glob("*.instructions.md")):
        if p.name not in SKIP_FILES:
            targets.append(p)
    return targets


if __name__ == "__main__":
    files = collect_files()
    updated = 0
    unchanged = 0
    skipped = 0
    for fp in files:
        status = update_frontmatter(fp)
        rel = fp.relative_to(ROOT)
        print(f"  [{status:12}] {rel}")
        if status == "UPDATED":
            updated += 1
        elif status == "UNCHANGED":
            unchanged += 1
        else:
            skipped += 1
    print(f"\nDone — {updated} updated, {unchanged} unchanged, {skipped} skipped (of {len(files)} total)")
