---
name: speckit-tasks
description: Generate an executable tasks.md from the current spec and plan, perform the cross-artifact consistency check, and produce the summary that the user confirms before implementation.
---

# Workflow

1. Run `.specify/scripts/powershell/setup-tasks.ps1 -Json` once and use its `FEATURE_DIR`, `TASKS_TEMPLATE`, and `AVAILABLE_DOCS`.
2. Read `spec.md`, `plan.md`, the tasks template, and `.specify/memory/constitution.md` once. Read optional `research.md`, `data-model.md`, `contracts/`, or `quickstart.md` only when present and relevant to an actual requirement.
3. Generate `tasks.md` by user story and dependency order. Do not emit generic setup, polish, documentation, or validation tasks unless the artifacts require them. Every task must be independently actionable and name its exact target path.

Use this format:

```text
- [ ] T001 [P?] [US?] Imperative action with exact path
```

- Assign sequential IDs. Add `[P]` only for different files with no incomplete dependency; add `[USn]` only to story tasks.
- Add test or reproducible-validation tasks for algorithm, resource, duration, shared-contract, persistence, security, and cross-module behavior. Do not add duplicate full-suite runs.
- Keep setup/foundation phases only when real shared prerequisites exist. Preserve story-level acceptance and the smallest executable order.

4. Perform one consistency check before reporting:
   - map each buildable FR, SC, user-story acceptance item, and plan decision to at least one task or explicit evidence;
   - reject tasks with no source requirement, conflicting terms/contracts, missing dependencies, duplicate validation, or paths outside the plan;
   - if the source is unambiguous, repair `tasks.md` once; otherwise report the blocker and stop without implementation.

# Completion

Report the tasks path, total and per-story counts, dependency/parallel summary, coverage gaps, and consistency result. Ask the user to confirm `tasks.md` and this result before `$speckit-implement`; do not create a separate analyze stage.
