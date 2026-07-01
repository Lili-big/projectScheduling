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
- If current resources produce a usable reference schedule, evaluate all matched mandatory milestones.
- If all matched mandatory milestones are satisfied, return a refined current-resource schedule when refinement succeeds.
- If all matched mandatory milestones are satisfied but refinement fails, return the current-resource reference schedule as a clearly labeled fallback.
- If at least one matched mandatory milestone is delayed, return the current-resource reference schedule with delayed milestone diagnostics and resource recommendation status.

## Minimum-Resource Candidate

**Trigger**

- Only when the current-resource reference schedule delays at least one matched mandatory milestone.

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

- `current_resources_capacity_shortest`: current-resource reference schedule.
- `current_resources_control_priority_balanced`: refined current-resource schedule.
- `current_resources_capacity_shortest_fallback`: current-resource refinement fallback.
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
