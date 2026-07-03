<!--
Sync Impact Report
Version change: 1.1.0 -> 1.1.1
Modified principles:
- None
Added principles:
- None
Added sections:
- None
Removed sections:
- None
Templates requiring updates:
- ✅ .specify/templates/spec-template.md updated for Simplified Chinese output
- ✅ .specify/templates/plan-template.md updated for Simplified Chinese output
- ✅ .specify/templates/tasks-template.md updated for Simplified Chinese output
- ✅ .specify/templates/checklist-template.md updated for Simplified Chinese output
- ✅ .specify/templates/constitution-template.md updated for Simplified Chinese output
- ✅ .agents/skills/speckit-* updated with repository language policy
Follow-up TODOs: None
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

### IV. Reuse Existing Docs and Code

All work MUST start from existing project documents and code structure. Agents MUST read
the relevant `docs/` materials before changing requirements, algorithms, scheduling
behavior, resource configuration, frontend interaction, or backend contracts.

Implementation MUST reuse existing modules, domain helpers, services, components, API
patterns, tests, and documentation conventions before introducing new abstractions,
dependencies, or directory structures.

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

## Project Constraints

- The detailed project handbook is `agent.md`; `AGENTS.md` governs runtime workflow
  routing; this constitution governs Spec Kit and implementation gates.
- Requirement review uses `$requirement-review`; formal PRD output uses
  `skills/write-dev-prd/SKILL.md`; spec ambiguity reduction uses `$speckit-clarify`.
- New feature specs live under `specs/<number>-<feature-name>/`.
- Product and algorithm documents live under `docs/`; temporary analysis MUST NOT be
  scattered in the repository root.
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
2. Read relevant project documents before implementation planning; for algorithm work,
   read both docs and code paths.
3. Resolve high-impact ambiguity before generating implementation tasks.
4. For complex features, run the full Spec Kit gate sequence and treat this constitution
   as non-negotiable during analyze and converge.
5. Implement only after user confirmation, then verify with the narrowest reliable tests
   or runnable scenario.
6. Do not modify `README.md`, commit, push, or deploy unless the user explicitly asks.

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

**Version**: 1.1.1 | **Ratified**: 2026-07-01 | **Last Amended**: 2026-07-01
