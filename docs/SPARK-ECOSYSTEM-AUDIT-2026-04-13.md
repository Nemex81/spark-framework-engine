# SPARK Ecosystem Audit Report

Date: 2026-04-13
Scope: full ecosystem review of SPARK MCP engine, services, plugin packages, and update/onboarding flows.
Method: static code and config audit across repos in the active workspace.

## 1) Executive Summary

Current ecosystem status is good on core architecture and package lifecycle controls, with clear strengths:
- solid MCP engine boundaries (stdio only, structured tools/resources, runtime state).
- dependency-aware update planning and execution.
- user-modified file preservation for tracked files.
- onboarding bootstrap and setup flows are idempotent.

Main risk area is conflict handling for pre-existing user files in .github during package install/update:
- tracked files are protected by manifest sha.
- untracked but pre-existing user files can be overwritten silently by package install/update.

This is the key gap to close for safe adoption at scale for existing projects.

## 2) Ecosystem Inventory

### 2.1 Core MCP engine (spark-framework-engine)

Main server:
- spark-framework-engine.py

Declared runtime shape:
- Resources: 15
- Tools: 28

Key service areas:
- discovery and retrieval of agents/skills/instructions/prompts.
- workspace status and framework version.
- package registry read and package info.
- install, remove, check updates, plan updates, apply updates.
- runtime state read/update for orchestrator.
- workspace bootstrap for base SPARK assets.
- workspace/system verification.

### 2.2 Package registry (scf-registry)

Registry schema:
- schema_version 2.0

Current listed packages:
- scf-master-codecrafter 1.0.0
- scf-pycode-crafter 2.0.0

Both require engine >= 1.5.0.

### 2.3 Managed plugin packages

scf-master-codecrafter:
- base orchestration layer.
- agents, instructions, transversal skills.
- file_ownership_policy: error.

scf-pycode-crafter:
- python-specialized plugin.
- depends on scf-master-codecrafter.
- file_ownership_policy: error.

## 3) Coherence and Completeness Audit

### 3.1 Strong points (PASS)

- Tool count coherence is enforced by tests (source/comment/log must match).
- ENGINE_VERSION and top CHANGELOG entry are enforced by tests.
- Update planner resolves dependency order and blocks incompatible plans.
- Apply updates uses planner order and returns detailed applied/failed result.
- Verify workspace reports missing/modified/duplicate ownership and classifies untracked files.
- spark-init setup is idempotent and preserves changed user bootstrap files.
- scf_bootstrap_workspace preserves already existing files and skips overwrite.

### 3.2 Coherence findings (WARNING)

1) Documentation/agent flow mismatch in spark-guide
- Frontmatter tools no longer include scf_list_installed_packages.
- Agent body still references scf_list_installed_packages in informational flow.
- Impact: routing text can suggest a tool that the agent cannot call directly.

2) Bootstrap asset divergence between spark-init and scf_bootstrap_workspace
- scf_bootstrap_workspace includes spark-guide.agent.md in copied assets.
- spark-init bootstrap static list does not include spark-guide.agent.md.
- Impact: different initial asset set depending on entry path (CLI init vs MCP bootstrap).

3) Service naming consistency between prompts/docs
- ecosystem still references both scf_check_updates and scf_update_packages in different guidance contexts.
- Not wrong technically, but user-facing guidance can be simplified to one canonical check path plus one advanced planner path.

## 4) Effectiveness for New User Initialization

### 4.1 What currently works well

- setup.ps1/setup.sh plus spark-init provide practical zero-to-running path.
- spark-init updates both .code-workspace and .vscode/settings.json.
- bootstrap of base .github assets is deterministic and idempotent.
- corrupted JSON in .vscode/settings.json is handled defensively.

### 4.2 Observed gaps for existing projects

For pre-existing .github files, current behavior is split:
- spark-init bootstrap preserves existing files (safe by default).
- package install/update may overwrite existing untracked files if they match package paths.

This means first-time plugin install in a mature project can silently replace user-authored files that are not in manifest but share target path.

## 5) Effectiveness for Plugin Updates

### 5.1 Current robustness

- update planning detects dependencies and blocked states.
- engine version constraints and missing dependencies are surfaced explicitly.
- tracked user-modified files are preserved on install/update/remove.
- obsolete files are removed only when safe, preserved when modified.

### 5.2 Critical risk scenario

Scenario:
- user already has .github/copilot-instructions.md created manually.
- package install includes same file path.
- file is untracked by manifest (first install or legacy state).

Current outcome:
- manifest.is_user_modified(rel) returns None (not True), so install path is treated as writable.
- destination file can be overwritten without explicit confirmation.

## 6) Required Target Behavior for Conflicts (Requested)

For any package file targeting an existing user file not safely tracked:

System must stop before write and require explicit resolution mode:
1. full replace
2. guided merge
3. user-provided custom resolution

Before decision, system must show a concise but useful two-version summary:
- source package version snippet/metadata.
- current workspace version snippet/metadata.
- change impact classification (frontmatter/tool list/instruction body/other).

## 7) Implementation Strategy

## 7.1 Design principles

- no silent overwrite on untracked-existing paths.
- explicit user choice for every unresolved conflict.
- deterministic and auditable conflict resolution output.
- preserve current tracked-file protections and dependency planner.

## 7.2 Proposed engine enhancements

A) Add collision preflight classification in install/update
For each target package file classify as:
- create_new (path absent)
- update_tracked_clean (tracked and unchanged)
- preserve_tracked_modified (tracked and changed)
- conflict_untracked_existing (exists but not tracked owner)
- conflict_cross_owner (owned by other package)

B) Introduce dry-run preview tool
New tool proposal:
- scf_plan_install(package_id)
Returns:
- write_plan
- preserve_plan
- conflict_plan
- ownership issues
- dependency issues

C) Add explicit conflict policy to apply path
Extend installer execution with parameter:
- conflict_mode: ask | replace | merge | abort
Default must be ask.

D) Add merge adapter for markdown framework files
For known SPARK files (agents/prompts/instructions/copilot-instructions):
- parse frontmatter and body separately.
- merge frontmatter keys by deterministic policy.
- preserve mandatory spark keys.
- append conflict notes for ambiguous sections.

E) Add conflict report contract
Each install/update result should include:
- conflicts_detected
- resolution_mode per file
- merged_files list
- replaced_files list
- preserved_files list

## 7.3 UX flow for spark-assistant

Install/update requested:
1. run plan tool.
2. if no conflict: proceed with explicit confirmation.
3. if conflict: present conflict table and ask per mode (replace/merge/custom/abort).
4. if merge selected: show pre-apply diff summary and ask final confirmation.
5. apply and report exact file outcomes.

## 7.4 Suggested prompt updates

- scf-install.prompt.md: require conflict review branch before install call.
- scf-update.prompt.md: same conflict branch for each package in order.
- scf-status.prompt.md: include pending conflict risk indicator if detected by planner.

## 7.5 Suggested test plan

Unit tests:
- untracked existing file triggers conflict_untracked_existing.
- replace mode overwrites only approved files.
- merge mode produces deterministic merged output.
- custom mode returns pending state without writing until user payload provided.

Integration tests:
- first install into project with pre-existing .github/copilot-instructions.md.
- update with mixed tracked modified + untracked existing conflicts.
- multi-package apply_updates with dependency order and conflict gating.

Regression tests:
- existing safe paths (tracked modified preservation, blocked dependencies) unchanged.

## 8) Priority Roadmap

Phase 1 (high priority, low risk):
- implement preflight conflict classification.
- block install/update on untracked-existing without explicit mode.
- expose structured conflict report.

Phase 2 (medium priority):
- add markdown merge adapter for SPARK-config files.
- add merge-specific tests.

Phase 3 (medium/high priority):
- add dedicated plan tool and unify user-facing prompt flow.
- align spark-init and scf_bootstrap_workspace copied asset set.
- clean remaining guidance mismatches in agent text.

## 9) Final Assessment

Coherence:
- Good overall, with localized mismatches in guidance and bootstrap parity.

Completeness:
- Strong for basic lifecycle, not complete for enterprise-safe conflict negotiation.

Effectiveness:
- High for greenfield projects.
- Medium for brownfield projects with pre-existing .github assets, due to untracked overwrite risk.

Recommended immediate action:
- implement Phase 1 before broadening plugin adoption in existing repositories.
