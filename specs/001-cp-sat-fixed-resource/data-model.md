# Data Model: CP-SAT Fixed Resource Scheduling

## Scenario

Represents one scheduling run input.

**Key fields**

- Project structure and start date
- Process library and task overrides
- Lower-structure and upper-structure logic rules
- Resource pools and calendars
- Milestones
- Scheduling strategy and run budget

**Validation rules**

- Scenario must generate at least one schedulable task before fixed-resource scheduling can proceed.
- Scenario generation errors block scheduling and return diagnostics.
- Changes to resource quantities, maximum quantities, enabled state, process choices, productivity, logic rules, milestones, or control-relevant data invalidate previous schedules and comparisons.

## Task Graph

Represents the generated schedule input before solving.

**Key fields**

- Tasks with duration, structure, component, process, control level, and compatible resource types
- Precedence links with relationship type and lag
- Named resources expanded from resource pools
- Milestones and generation diagnostics

**Validation rules**

- Task duration must be at least one day.
- Precedence lag must be non-negative.
- Resource candidates must reflect current resource configuration.
- Unmatched or disabled resources must be visible through diagnostics.

## Resource Pool

Represents a project or scenario-level pool of limited resources.

**Key fields**

- Stable identifier, label, resource type
- Current quantity
- Maximum quantity
- Enabled state
- Resource mode
- Calendar reference
- Same-structure same-process binding flag
- Same-structure same-process parallel limit
- User-facing parallel-rule description

**Validation rules**

- Current quantity must be non-negative.
- Maximum quantity must be greater than or equal to current quantity.
- Disabled pools do not expand named resources.
- Same-structure same-process parallel limit, when present, must be a positive integer.
- Binding and parallel-limit behavior comes from configuration, not resource type alone.

## Mandatory Milestone

Represents a date target used to decide whether current resources are sufficient.

**Key fields**

- Stable identifier and name
- Mode and level
- Scope type and scope identifier
- Target event and target date
- Penalty settings for non-hard milestones

**Validation rules**

- Matched mandatory milestones participate in current-resource sufficiency evaluation.
- Unmatched milestones are marked not evaluated with diagnostics.
- All matched mandatory milestones must be considered; the first milestone alone is not sufficient.

## Schedule Result

Represents one schedule returned to the user.

**Key fields**

- Status
- Objective duration and plan start/finish
- Scheduled tasks
- Resource allocations
- Milestone results
- Validation diagnostics
- Statistics and result-source metadata
- Objective and business breakdown metadata

**States**

- Usable refined schedule
- Usable reference schedule
- Usable fallback schedule
- Delayed current-resource schedule
- Invalid or unresolved schedule with diagnostics

**Validation rules**

- A delayed current-resource schedule may be returned with an infeasible milestone judgment if it includes inspectable tasks, resources, and delay diagnostics.
- Fallback schedules must preserve the successful judgment they are falling back from and explain the refinement failure.
- Result source must be explicit.

## Minimum-Resource Candidate

Represents a verified resource-increase candidate returned alongside the current-resource result.

**Key fields**

- Recommended resource counts
- Current quantities
- Added quantities
- Maximum quantities
- Candidate schedule
- Candidate schedule source
- Candidate diagnostics

**Lifecycle**

1. Current resources delay one or more matched mandatory milestones.
2. The no-wait critical path is checked.
3. Maximum configured resources are checked.
4. Recommended quantities are found and verified.
5. Candidate refinement is run.
6. Refined candidate is returned, or verified feasible candidate is returned as a fallback.

**Validation rules**

- Recommended quantities must not exceed maximum quantities.
- Candidate must not be returned as verified unless a feasible schedule was produced.
- Candidate refinement fallback must be explicitly labeled.

## Control Target

Represents a task or task group treated as control-related during refinement.

**Sources**

- Explicit task control attribute
- Cast-in-place continuous-beam recognition

**Validation rules**

- Milestone evaluation scope alone does not create control targets.
- Control-target source must be explainable in diagnostics.

## Schedule Source

Represents where a displayed schedule came from.

**Required source categories**

- Current-resource reference
- Current-resource refined
- Current-resource refinement fallback
- Minimum-resource refined
- Minimum-resource refinement fallback

**Validation rules**

- Every displayed main or candidate schedule must have one source category.
- Source categories must support frontend labels and tests.

## Diagnostic Message

Represents a user-understandable explanation of a scheduling branch or failure.

**Required diagnostic topics**

- Scenario generation error
- Current-resource mandatory milestone delay
- Critical-path infeasible
- Maximum-resource upper bound infeasible
- Unresolved minimum-resource recommendation
- Refinement fallback
- Unmatched milestone
- Disabled or unavailable resource pool
