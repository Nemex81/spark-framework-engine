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
- Impact: this is not only a routing-text mismatch. The agent can fail on an informational path because it references a tool that is not in its allowed tool list.

2) Bootstrap asset divergence between spark-init and scf_bootstrap_workspace
- scf_bootstrap_workspace includes spark-guide.agent.md in copied assets.
- spark-init bootstrap static list does not include spark-guide.agent.md.
- spark-init does include spark-engine-maintainer.agent.md, while scf_bootstrap_workspace does not.
- Impact: different initial asset set depending on entry path (CLI init vs MCP bootstrap), with different user-facing guide/admin capabilities.

3) Service naming consistency between prompts/docs
- ecosystem still references both scf_check_updates and scf_update_packages in different guidance contexts.
- Not wrong technically, but user-facing guidance can be simplified to one canonical check path plus one advanced planner path.

4) Non-canonical consumer manifest state exists in the wild
- The engine canonical format is `.github/.scf-manifest.json` with `schema_version: "1.0"` and `entries[]`.
- A real consumer workspace in this audit contains `schema_version: "2.0"`, `entries[]`, and extra diagnostic keys such as `generated_at` and `untracked_files[]`.
- Current ManifestManager.load() tolerates this state because it only reads `entries[]`, but ManifestManager.save() will rewrite the file back to the canonical payload and discard extra keys.
- Impact: hardening logic must not rely on persisted non-canonical manifest metadata. Any conflict classification must be derived from live filesystem state plus canonical tracked entries.

5) Multi-package apply flow is not atomic
- scf_apply_updates applies packages sequentially and returns partial success/failure results.
- If one package is written successfully and a later target fails, earlier writes remain applied.
- Impact: conflict gating for updates must happen before the first write of the batch, otherwise the hardening work can still leave partially applied update states.

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

### 5.3 Additional regression risks validated in code

- `scf_update_package` delegates to `scf_apply_updates`, which in turn delegates to `scf_install_package`.
- Any new conflict policy added only to `scf_install_package` is incomplete unless the same behavior and structured result contract are propagated through `scf_apply_updates` and `scf_update_package`.
- A tool-level mode named `ask` is misleading in MCP terms: tools do not run an interactive question loop. The "ask the user" step belongs to prompts/agents. The engine should instead return a structured conflict report and stop safely.

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

Validation notes:
- The classification must run before any file write and before obsolete-file cleanup.
- The classification must use canonical tracked entries plus current disk state, not non-canonical consumer metadata such as `untracked_files[]`.

B) Introduce dry-run preview tool
New tool proposal:
- scf_plan_install(package_id)
Returns:
- write_plan
- preserve_plan
- conflict_plan
- ownership issues
- dependency issues

Maintenance notes:
- Adding this tool requires coordinated updates to tool counts in code, logs, README, and coherence tests.
- The preview tool should become the only source for install-time conflict review in prompts.

C) Add explicit conflict policy to apply path
Extend installer execution with parameter:
- conflict_mode: abort | replace | merge | custom
- Default should be abort at engine level.

Validation notes:
- `ask` is a prompt/agent UX state, not a tool execution mode.
- The same conflict behavior and structured report must be propagated through scf_install_package, scf_apply_updates, and scf_update_package.
- For multi-package updates, unresolved conflicts must abort the whole batch before the first write.

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
- blocked_files list
- requires_user_resolution boolean

Validation notes:
- The contract must preserve existing caller expectations (`installed`, `preserved`, `removed_obsolete_files`, `preserved_obsolete_files`).
- Update callers must receive the same structured conflict information, not a reduced error string.

## 7.3 UX flow for spark-assistant

Install/update requested:
1. run plan tool.
2. if no conflict: proceed with explicit confirmation.
3. if conflict: present conflict table and ask per mode (replace/merge/custom/abort).
4. if merge selected: show pre-apply diff summary and ask final confirmation.
5. apply and report exact file outcomes.

Validation notes:
- Install flow depends on scf_plan_install.
- Update flow can continue to use scf_update_packages as dependency planner, but must run conflict preflight for every target before the first write.
- If merge/custom are not implemented yet, the first safe engine milestone may support only `abort` and `replace`, while prompts keep the UX wording aligned with supported modes.

## 7.4 Suggested prompt updates

- scf-install.prompt.md: require conflict review branch before install call.
- scf-update.prompt.md: same conflict branch for each package in order.
- scf-status.prompt.md: include pending conflict risk indicator if detected by planner.

Validation notes:
- Prompt changes depend on the existence of structured conflict reports from the engine.
- scf-install.prompt.md specifically depends on scf_plan_install being available.
- The spark-guide tool-list mismatch should be fixed before relying on guide-driven routing during rollout.

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
- scf_update_package propagates conflict behavior and structured reports consistently.
- scf_apply_updates aborts before first write when any target has unresolved conflicts.
- adding scf_plan_install keeps tool-count coherence across code, logs, README and tests.

## 8) Priority Roadmap

Phase 0 (immediate, very low risk):
- fix spark-guide tool list mismatch.
- fix scf-registry README manifest wording (`entries[]`, not `installed_packages[]`).
- document bootstrap asymmetry precisely: spark-init vs scf_bootstrap_workspace.

Phase 1 (high priority, medium risk):
- implement preflight conflict classification.
- block install/update on untracked-existing without explicit engine mode.
- expose structured conflict report.
- propagate the new behavior through scf_install_package, scf_apply_updates and scf_update_package.
- ensure update batches preflight all targets before the first write.

Phase 2 (medium priority):
- add scf_plan_install and wire prompt flows to it.
- add markdown merge adapter for SPARK-config files if needed after the abort/replace milestone.
- add merge-specific tests.

Phase 3 (medium/high priority):
- align spark-init and scf_bootstrap_workspace copied asset set.
- clean remaining guidance mismatches in agent text.
- decide whether bootstrap parity should also include spark-engine-maintainer.agent.md or explicitly keep it CLI-only.

## 9) Final Assessment

Coherence:
- Good overall, but with validated gaps in guide tool gating, bootstrap parity, and consumer-manifest normalization.

Completeness:
- Strong for basic lifecycle, not complete for enterprise-safe conflict negotiation or batch-safe conflict handling.

Effectiveness:
- High for greenfield projects.
- Medium for brownfield projects with pre-existing .github assets, due to untracked overwrite risk and non-canonical manifest states already present in at least one consumer workspace.

Recommended immediate action:
- apply Phase 0 first, then implement Phase 1 before broadening plugin adoption in existing repositories.

## 10) Revision Notes — validated corrective strategy

Validated on 2026-04-13 against the current codebase and related repositories.

Outcome:
- The original direction of Phase 1 is correct, but the plan is not safe to implement exactly as written.

Required corrections before implementation:
- Treat `ask` as a prompt-layer concept, not a tool-level execution mode.
- Propagate conflict behavior through scf_install_package, scf_apply_updates, and scf_update_package as one coordinated change.
- Preflight all update targets before the first write to avoid partial batch application on conflict.
- Add tool-count and coherence-test maintenance to the scf_plan_install work item.
- Do not rely on non-canonical consumer manifest metadata for conflict handling.
- Fix the spark-guide tool-list mismatch before rollout so routing and status guidance remain trustworthy.

Implementation recommendation:
- Proceed only with the revised roadmap in sections 7 and 8.
- After Phase 0 and before code changes, obtain explicit confirmation on whether the first safe execution milestone should support only `abort` and `replace`, deferring `merge` and `custom` to a later phase.
