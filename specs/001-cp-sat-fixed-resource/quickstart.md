# Quickstart: Validate CP-SAT Fixed Resource Scheduling

This guide describes the validation scenarios for the first-phase fixed-resource scheduling feature. It is a test and review guide, not an implementation script.

## Prerequisites

- Python dependencies installed for the backend.
- Frontend dependencies installed if validating result display and type integration.
- A scenario can be loaded or constructed with tasks, resources, milestones, and resource pools.

## Core Validation Commands

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm --prefix frontend run build
```

If `npm` is blocked by PowerShell execution policy, use `npm.cmd` through the local Node installation as documented in the project README.

## Scenario 1: Current Resources Satisfy Mandatory Milestones

**Given**

- A valid scenario with enabled limited resource pools.
- Current quantities are sufficient for all matched mandatory milestones.

**When**

- The user runs fixed-resource scheduling.

**Expected**

- Main result is usable.
- Mandatory milestones are met.
- Resource recommendation status says no additional resources are needed.
- Main schedule source is a refined current-resource result, or a clearly labeled current-resource refinement fallback if refinement cannot complete.
- Result includes resource allocations and milestone results.

## Scenario 2: Current Resources Delay Mandatory Milestones

**Given**

- A valid scenario where current quantities are insufficient.
- At least one matched mandatory milestone is delayed.

**When**

- The user runs fixed-resource scheduling.

**Expected**

- Current-resource reference schedule is preserved.
- Delayed mandatory milestone names, target dates, expected dates, and delay days are visible.
- Main result does not imply mandatory milestone success.
- Resource recommendation branch is evaluated unless the reference schedule itself is unusable.

## Scenario 3: Minimum-Resource Candidate Is Verified and Refined

**Given**

- Current resources delay mandatory milestones.
- The theoretical critical path can satisfy the target.
- Maximum configured quantities are sufficient.

**When**

- The system evaluates minimum-resource recommendations.

**Expected**

- Recommended quantities do not exceed maximum quantities.
- Added quantities are non-negative.
- Candidate schedule is verified feasible before being returned.
- Candidate refinement is attempted.
- Candidate result is labeled as minimum-resource refined when refinement succeeds, or minimum-resource refinement fallback when only the verified feasible schedule can be returned.

## Scenario 4: Resource Increase Cannot Solve Delay

**Given**

- Current resources delay mandatory milestones.
- The no-wait critical path already misses the target, or maximum configured quantities still cannot meet the target.

**When**

- The system evaluates resource recommendations.

**Expected**

- No verified candidate plan is returned.
- Diagnostics explain whether the failure is critical-path infeasibility or resource upper-bound infeasibility.
- Current-resource reference schedule remains visible for comparison and diagnosis.

## Scenario 5: Same-Structure Same-Process Rules

**Given**

- Tasks share the same structure and process.
- Their resource pool configures same-structure binding or a same-structure parallel limit.

**When**

- Current-resource or minimum-resource candidate schedules are produced.

**Expected**

- Binding rules are respected.
- Parallel limits are not exceeded.
- If rules are absent, the schedule does not invent hidden restrictions based only on resource type.

## Scenario 6: Frontend Result Interpretation

**Given**

- Results from current-resource sufficient, current-resource delayed, and minimum-resource candidate cases.

**When**

- The result view renders schedules and alternatives.

**Expected**

- The user can distinguish reference, refined, and fallback schedules.
- The user can see resource recommendation status and message.
- The user can compare current delayed plan and recommended candidate plan without manually inferring result source or delay.

## Scenario 7: Frontend Stale-Result Invalidation

**Given**

- A scenario has generated tasks, a fixed-resource solve result, and optionally a scenario comparison result.

**When**

- The user changes any resource pool quantity, maximum quantity, same-structure rule, process productivity, logic rule, milestone target, task process override, or structure control attribute.

**Expected**

- Previously generated task graph, solve result, and comparison result are no longer displayed as current for the changed scenario.
- Opening the task view regenerates tasks for the new scenario fingerprint.
- Running fixed-resource scheduling again produces a result tied to the updated scenario fingerprint.

## Completion Evidence

Before implementation is considered complete, collect:

- Passing backend tests for all core scenarios above.
- Passing frontend build.
- A short note listing any demo/mirror behavior that aligns with or intentionally degrades from the authoritative backend contract.
