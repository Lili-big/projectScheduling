---
name: speckit-implement
description: Execute a user-confirmed Spec Kit tasks.md, validate the core objective, repair relevant failures, tolerate evidenced non-core failures, and record completion evidence.
---

# Workflow

1. Run `.specify/scripts/powershell/check-prerequisites.ps1 -Json -RequireTasks -IncludeTasks` once. If `tasks.md` is missing, or the current conversation does not contain explicit confirmation of `tasks.md` and its consistency result, stop.
2. Read `tasks.md`, `.specify/memory/constitution.md`, and only the plan/spec sections or optional artifacts referenced by incomplete tasks. Do not mechanically reload every design file or inspect optional checklists unless a confirmed task names them as a gate.
3. Protect unrelated worktree changes. Execute incomplete tasks in dependency order; tasks touching the same file are sequential. Use parallel work only where `[P]` is still valid. Follow test-first order only when the task requires it.
4. Batch related edits. Mark a task `[x]` only after its stated output or evidence exists. Do not run generic setup checks, re-plan completed work, or report after every task.
5. After the related modification batch, run each validation command defined by the tasks for an initial attempt. A high-risk independent review may add one different risk-focused check; it must not repeat the same suite.
6. Classify every failure against the confirmed core objective, acceptance criteria, and safety or data-integrity boundaries before deciding what to do:
   - If the failure is caused by the implementation, test, fixture, or validation command and affects or obscures core acceptance, make the smallest in-scope correction and rerun only the affected validation. Do not repeat an unchanged command without new evidence.
   - If the failure is unrelated, pre-existing, environmental, or otherwise does not affect core acceptance, record the evidence and why it is non-blocking, then continue. Do not expand into a deep investigation that does not improve confidence in the core objective.
   - Stop only when the core objective still cannot be proven after focused correction, the next correction would change confirmed business semantics or expand scope or authority, or safety/data-integrity risk remains unresolved.
7. Do not start a separate analyze/converge pass or append speculative work. Record commands, exit results, changed paths, tolerated failures, and remaining risks.

# Completion

Completion requires all confirmed core tasks checked and their acceptance evidence present. Defined validation must pass unless a failure is explicitly classified with evidence as non-blocking to the core objective; tolerated failures and their residual risk remain visible in the completion report. Report actual changes, results, and uncovered risk, then stop.
