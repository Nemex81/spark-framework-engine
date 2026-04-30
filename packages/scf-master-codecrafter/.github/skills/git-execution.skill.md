---
spark: true
name: git-execution
description: Matrice sintetica dei comandi git consentiti, vietati e delegati ad Agent-Git.
---

# git-execution

## Consentiti read-only

- `git status`
- `git diff`
- `git log`
- `git show`

## Consentiti solo via Agent-Git

- `git commit`
- `git push`
- `git merge`
- `git tag`

## Vietati in autonomia

- `git reset --hard`
- `git rebase`
- force push su branch condivisi