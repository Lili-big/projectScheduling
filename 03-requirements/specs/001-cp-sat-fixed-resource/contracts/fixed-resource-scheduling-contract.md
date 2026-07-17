# Contract: Fixed Resource Scheduling Result

This contract documents the user-visible scheduling behavior that backend, frontend, and any demo or mirror surface must preserve.

## Fixed-Resource Run

**Input**

- A complete scenario containing project structure, process choices, productivity, logic rules, resources, milestones, and strategy settings.

**Output**

- Generated task graph and diagnostics.
- Main schedule result.
- Main milestone results.
- Scenario metrics.
- Optional alternative results for verified minimum-resource candidates.

**Required main-result behavior**

- If scenario generation has blocking errors, return no misleading schedule and include diagnostics.
- Run the current-resource target schedule directly with the current objective model.
- If current resources satisfy the business target, return the current-resource target schedule as `current_resources_control_priority_balanced`.
- If current resources produce an inspectable schedule but the business target is not met, return that schedule as `current_resources_target_failed` with delayed milestone diagnostics and resource recommendation status.
- If the solver cannot confirm target feasibility within run limits, return `target_unconfirmed` with diagnostics.
- If construction hard rules or resource coverage are physically infeasible, return `physical_infeasible` without implying that resource recommendation solved the case.

## Minimum-Resource Candidate

**Trigger**

- Only when the current-resource target schedule is inspectable but fails the business target.

**Required behavior**

- Do not recommend more resources if the theoretical critical path already misses the target.
- Do not recommend more resources if maximum configured quantities still cannot meet the target.
- Recommended quantities must be verified by a feasible schedule.
- Verified candidates must rerun refinement before display.
- If verified candidate refinement fails, return the verified feasible schedule as a labeled fallback.

**Required candidate fields**

- Candidate role identifying it as a minimum-resource candidate.
- Recommended resource counts with current, recommended, added, and maximum quantities.
- Candidate schedule source.
- Milestone results.
- Diagnostics explaining candidate refinement success or fallback.

## Schedule Source Categories

The result contract must distinguish these categories in result metadata and frontend display:

- `current_resources_control_priority_balanced`: refined current-resource schedule.
- `current_resources_target_failed`: current-resource schedule is inspectable but does not meet the business target.
- `target_unconfirmed`: current-resource target status is not confirmed within run limits.
- `physical_infeasible`: construction hard rules or resource coverage are infeasible.
- `minimum_resources_control_priority_balanced`: refined minimum-resource candidate.
- `minimum_resources_refinement_fallback`: minimum-resource refinement fallback after feasibility verification.

Equivalent internal names are acceptable only if they are normalized to these user-visible categories before display and tests.

## Recommendation Status Categories

The result contract must distinguish:

- Current resources already satisfy mandatory milestones; no recommendation needed.
- Recommended resources verified.
- Critical path cannot meet target; resource increase cannot solve.
- Maximum resource upper bound cannot meet target.
- Recommendation unresolved within run limits.
- Recommendation was not evaluated because the current-resource reference schedule was not usable.

## Frontend Display Contract

The result view must show:

- Whether current resources satisfy mandatory milestones.
- Current-resource expected dates and delay days when delayed.
- Main schedule source.
- Candidate schedule source when alternatives exist.
- Recommended resource counts when a candidate exists.
- Fallback reason when refinement fails.
- Diagnostics for unmatched milestones, resource unavailability, and unresolved recommendations.

The result view must not imply that:

- A delayed current-resource schedule is a successful mandatory-milestone plan.
- A minimum-resource candidate is globally optimal.
- A fallback schedule is a refined result.
- A resource recommendation is verified if it lacks a feasible schedule.
