#!/usr/bin/env python3
import re
import yaml
from pathlib import Path

# Validazione spark-assistant.agent.md
content = Path('.github/agents/spark-assistant.agent.md').read_text(encoding='utf-8')

required = [
    '## Flusso D',
    '## Flusso E',
    'scf_get_instruction(name="workflow-standard")',
    'scf_get_instruction(name="git-policy")',
    'scf_get_instruction(name="framework-guard")',
    'scf_list_instructions()',
    'scf_verify_system()',
    'scf_get_runtime_state()',
]

for r in required:
    if r not in content:
        print(f'ERRORE — MANCANTE: {r}')
        exit(1)

fm = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
if not fm:
    print('ERRORE — Frontmatter mancante')
    exit(1)

data = yaml.safe_load(fm.group(1))
tools_count = len(data.get('tools', []))
if tools_count < 23:
    print(f'ERRORE — tools ridotti: {tools_count} < 23')
    exit(1)

print('OK — flussi D+E presenti, frontmatter intatto')
print(f'tools count: {tools_count}')

# Validazione project-profile.md
profile = Path('.github/project-profile.md').read_text(encoding='utf-8')
if 'framework_edit_mode: false' not in profile:
    print('ERRORE — FLAG NON RIPRISTINATO')
    exit(1)

print('OK — framework_edit_mode ripristinato a false')
