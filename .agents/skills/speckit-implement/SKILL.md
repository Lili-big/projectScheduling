---
name: speckit-implement
description: Execute a user-confirmed Spec Kit tasks.md, run the task-defined minimum validation once, record completion evidence, and stop.
---

# Workflow

1. Run `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks` once. If `tasks.md` is missing, or the current conversation does not contain explicit confirmation of `tasks.md` and its consistency result, stop.
2. Read `tasks.md`, `.specify/memory/constitution.md`, and only the plan/spec sections or optional artifacts referenced by incomplete tasks. Do not mechanically reload every design file or inspect optional checklists unless a confirmed task names them as a gate.
3. Protect unrelated worktree changes. Execute incomplete tasks in dependency order; tasks touching the same file are sequential. Use parallel work only where `[P]` is still valid. Follow test-first order only when the task requires it.
4. Batch related edits. Mark a task `[x]` only after its stated output or evidence exists. Do not run generic setup checks, re-plan completed work, or report after every task.
5. After the related modification batch, run the validation commands defined by the tasks once. A high-risk independent review may add one different risk-focused check; it must not repeat the same suite.
6. If a task, acceptance item, or validation fails, leave the affected task incomplete, record the concrete evidence, and stop. Do not start a separate analyze/converge pass or append speculative work. If all tasks and validations pass, record commands, exit results, changed paths, and remaining risks.

# Completion

Completion requires all confirmed tasks checked, their acceptance evidence present, and the defined validation passing. Report actual changes, results, and uncovered risk, then stop.
