<!--
Sync Impact Report
Version change: 1.1.1 -> 1.2.0
Modified principles:
- IV. Reuse Existing Docs and Code -> IV. Reuse Existing Assets and Preserve Behavior
Added principles:
- VIII. Lifecycle Ownership and Work Packages
Added sections:
- None
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/spec-template.md updated for lifecycle source references
- ✅ .specify/templates/plan-template.md updated for lifecycle ownership checks
- ✅ .specify/templates/tasks-template.md updated for lifecycle/work-package tasks
- ✅ .specify/templates/checklist-template.md remains compatible
- ⚠ .specify/templates/constitution-template.md pending 045 implementation sync
- ⚠ .agents/skills/speckit-* path defaults pending 045 implementation sync
- ⚠ AGENTS.md, agent.md, README.md and current repository docs pending 045 implementation sync
Follow-up TODOs:
- Complete physical migration and path-tooling switch only after 045 tasks and analysis are approved.
-->

# Bridge Scheduling Spec Kit Constitution

## Core Principles

### I. Requirements First

Agents MUST NOT write implementation code when the requirement is unclear. Every feature
or change MUST first identify the business goal, target user, scope boundary, source
documents, affected modules, assumptions, and acceptance criteria.

Requirement review MUST remain separate from PRD writing and implementation. When the
user asks for review, use `$requirement-review` to decide whether to proceed, adjust,
validate first, defer, or reject before creating engineering artifacts.

### II. Explicit Algorithm Specifications

Algorithm-related requirements MUST define inputs, outputs, hard constraints, soft
constraints, objective function, prioritization rules, and acceptance examples before
planning implementation.

This applies to task duration, resource configuration, fixed-resource constraints,
minimum-resource recommendations, resource-cost optimization, milestones, continuity
metrics, CP-SAT objectives, and schedule-result interpretation.

### III. Explicit Frontend-Backend Contracts

Frontend-backend changes MUST define interface fields, page entry points, state display,
loading and empty states, error handling, compatibility expectations, and downstream
invalidation behavior.

Shared data shapes such as `ScenarioInput`, `ScheduleInput`, `ScheduleResult`, resource
pools, process templates, logic rules, milestones, and diagnostics MUST be kept aligned
across backend models, frontend types, API clients, Netlify demo code when applicable,
and tests.

### IV. Reuse Existing Assets and Preserve Behavior

All work MUST start from existing project documents, code, scripts, inputs, outputs,
tests, and work-package evidence. Agents MUST read the relevant lifecycle assets before
changing requirements, algorithms, scheduling behavior, resource configuration,
frontend interaction, backend contracts, or generated deliverables.

Implementation MUST reuse existing modules, domain helpers, services, components, API
patterns, tests, and documentation conventions before introducing new abstractions,
dependencies, or directory structures. Directory migration MUST preserve public behavior,
tracked content, approved binary hashes, and uncommitted user work unless a change is
explicitly included in an approved migration entry.

### V. Phased Delivery

Complex requirements MUST be split into phases. The first implementation phase MUST
deliver a testable MVP that proves the primary user value independently. Enhancements,
secondary stories, polish, and broader optimization MUST follow after the MVP is
validated.

Spec Kit tasks MUST preserve this sequencing by grouping work into setup, foundational
work, prioritized user stories, and polish or convergence phases.

### VI. Spec Kit Gate Before Implementation

Before implementation of complex or scheduling-related work, agents MUST complete:

```text
$speckit-specify -> $speckit-clarify -> $speckit-plan
  -> $speckit-tasks -> $speckit-analyze
```

Implementation MUST NOT begin until the user confirms the analyzed spec, plan, and tasks.
After implementation, `$speckit-converge` MUST assess whether code, spec, plan, and
tasks have converged.

Small documentation edits and narrow bug fixes may skip the full Spec Kit flow only when
they do not change business rules, algorithm behavior, shared contracts, or user-facing
workflow.

### VII. Completion Report and Verification

After every implementation, agents MUST report changed files, core logic, test method,
validation result, and remaining risk.

Algorithm changes MUST include a reproducible input sample, expected output or invariant,
and validation command or scenario. Frontend-backend changes MUST report affected fields,
status and error behavior, and any compatibility gaps.

### VIII. Lifecycle Ownership and Work Packages

Every business asset MUST have one primary lifecycle stage and, when it belongs to an
independent workflow, one primary work package. A work package MUST connect its purpose,
inputs, scripts or entry commands, generated results, tracking policy, retention class,
and owner. Cross-stage reuse MUST use references rather than duplicated source files.

Before creating or moving assets, agents MUST classify the task by lifecycle stage,
work package, asset type, retention class, and primary owner. Generic root-level
collections such as undifferentiated `docs/`, `tools/`, `outputs/`, or `logs/` MUST NOT
become new long-term ownership boundaries. Framework discovery entry points and required
platform configuration MAY remain at the root only when their compatibility reason is
documented and their business content has a lifecycle owner.

Local assets MUST distinguish persistent state, user input, formal output, diagnostic
logs, rebuildable output, caches, and temporary files. Cleanup MUST default to dry-run;
persistent state, user input, and formal output MUST NOT be automatic deletion candidates.

## Project Constraints

- The detailed project handbook is `agent.md`; `AGENTS.md` governs runtime workflow
  routing; this constitution governs Spec Kit and implementation gates.
- Requirement review uses `$requirement-review`; formal PRD output uses
  `skills/write-dev-prd/SKILL.md`; spec ambiguity reduction uses `$speckit-clarify`.
- During the 045 transition, existing features continue under
  `specs/<number>-<feature-name>/`. After the approved migration activates the lifecycle
  layout, new features live under
  `03-requirements/specs/<number>-<feature-name>/`; historical feature content and numbering
  MUST remain unchanged.
- Product, algorithm, research, validation, Demo, and delivery assets live under their
  primary lifecycle stage and work package. Temporary analysis MUST NOT be scattered in
  the repository root or promoted to a formal output without an explicit retention class.
- `.agents/` and `.specify/` MAY remain root discovery entry points. Their project-specific
  content and generated feature assets MUST still declare a lifecycle owner.
- All Spec Kit process artifacts and user-facing stage reports MUST be written in
  Simplified Chinese. This includes `spec.md`, `plan.md`, `research.md`,
  `data-model.md`, `quickstart.md`, `tasks.md`, checklist files, analyze reports,
  converge reports, and clarification questions. Code identifiers, file paths, API
  names, field names, commands, branch names, task IDs, requirement IDs, and necessary
  English acronyms MAY remain unchanged for traceability and tooling compatibility.
- Chinese business documents MUST remain UTF-8.
- Secret-bearing files such as `.local.env` MUST NOT be copied into docs, specs, code,
  or examples with real values.

## Development Workflow

1. Classify the request as requirement review, Demo implementation, PRD/document output,
   or Spec Kit development.
2. Declare the lifecycle stage, work package, asset type, retention class, and primary
   owner before creating or moving project assets.
3. Read relevant project documents before implementation planning; for algorithm work,
   read both docs and code paths.
4. Resolve high-impact ambiguity before generating implementation tasks.
5. For complex features, run the full Spec Kit gate sequence and treat this constitution
   as non-negotiable during analyze and converge.
6. Implement only after user confirmation, then verify with the narrowest reliable tests
   or runnable scenario.
7. Do not modify `README.md`, commit, push, or deploy unless the user explicitly asks.

## Governance

This constitution supersedes ad-hoc workflow habits when using Spec Kit in this
repository. `AGENTS.md` provides runtime routing rules; `agent.md` provides detailed
project knowledge. If the three conflict, this constitution controls Spec Kit governance,
`AGENTS.md` controls routing, and `agent.md` supplies factual context.

Amendments require an explicit user request or an approved workflow-design task. Changes
MUST update the version using semantic versioning:

- MAJOR for removing or redefining a core principle.
- MINOR for adding or materially expanding workflow principles.
- PATCH for clarifications that do not change required behavior.

Any change to this constitution MUST re-check `AGENTS.md` and the Spec Kit templates for
alignment. `$speckit-analyze` and `$speckit-converge` MUST treat violations of MUST-level
principles as blocking issues.

**Version**: 1.2.0 | **Ratified**: 2026-07-01 | **Last Amended**: 2026-07-16
