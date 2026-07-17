# Implementation Plan: CP-SAT Fixed Resource Scheduling

**Branch**: `[001-cp-sat-fixed-resource]` | **Date**: 2026-07-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-cp-sat-fixed-resource/spec.md`

## Summary

Deliver the first-phase CP-SAT fixed-resource scheduling loop as a complete, comparable user workflow: current resources produce a reference schedule and mandatory-milestone judgment; sufficient current resources rerun named-resource refinement; insufficient current resources preserve the delayed reference schedule and, when possible, return a verified minimum-resource candidate that is refined again before display. The plan reuses the existing scenario, solver, resource, milestone, diagnostics, and frontend result structures while tightening result-source labels, fallback handling, same-structure same-process rules, and validation coverage.

## Technical Context

**Language/Version**: Python 3.11-compatible backend, TypeScript/React frontend, TypeScript Netlify demo/mirror where applicable

**Primary Dependencies**: FastAPI, Pydantic, OR-Tools CP-SAT, pytest, React, Vite, existing frontend API/domain helpers

**Storage**: Existing in-memory/request scenario flow plus current local scenario configuration files; no new database schema in this phase

**Testing**: `pytest backend/tests -q` for scheduling behavior; `npm --prefix frontend run build` for frontend contract/type integration; targeted scenario tests for resource recommendation and refinement fallback

**Target Platform**: Local FastAPI scheduling service with React frontend; deployed demo or mirror code must align with the same user-visible contract or explicitly degrade

**Project Type**: Web application with backend scheduling service, frontend scheduling UI, and optional Netlify demo/mirror surface

**Performance Goals**: Preserve current bounded solve behavior for demo-scale bridge scenarios; return explicit timeout or fallback diagnostics instead of blocking without explanation

**Constraints**: No implementation before user confirms `tasks.md` and `$speckit-analyze`; no new dependencies unless unavoidable; no README, commit, push, or deploy unless explicitly requested; do not promote demo-only limitations into product rules

**Scale/Scope**: First-phase bridge construction scheduling scenarios using existing project structure, process library, logic rules, resource pools, milestones, current-resource quantities, maximum resource quantities, and refinement diagnostics

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Requirement review completed or explicitly not required for a narrow change. **PASS**: requirement discovery completed and user confirmed the five major decisions before Spec Kit.
- Source docs and Demo/code facts are cited in `spec.md`. **PASS**: spec lists AGENTS, handbook, README, four requested docs, companion fixed-resource document, and current scheduling boundary.
- Scheduling, resource, duration, CP-SAT, and frontend/backend contract impacts are explicit. **PASS**: spec covers fixed-resource, minimum-resource, refinement, same-structure rules, and result display.
- Inputs, outputs, constraints, edge cases, and acceptance criteria are testable. **PASS**: spec includes task graph, resource pool, milestone, schedule source, diagnostics, and scenario-based acceptance.
- No Demo-only limitation is promoted into product intent without explicit approval. **PASS**: spec calls out mirror/demo alignment or clear degradation and avoids making demo shortcuts product rules.

## Project Structure

### Documentation (this feature)

```text
specs/001-cp-sat-fixed-resource/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── fixed-resource-scheduling-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── main.py                 # scheduling endpoints
│   ├── models.py               # shared scheduling/result models
│   ├── scenario.py             # scenario generation and branch orchestration
│   ├── solver.py               # CP-SAT scheduling, refinement, recommendations
│   └── scenario_data.py        # default scenario/resource templates
└── tests/
    └── test_scheduler.py       # scheduling and resource behavior tests

frontend/
├── src/
│   ├── app/App.tsx             # solve actions and result display
│   ├── api/schedulerApi.ts     # scheduling API calls
│   ├── types/scheduler.ts      # frontend result contracts
│   ├── domain/resources.ts     # resource configuration helpers
│   └── features/resources/     # resource configuration page

netlify/
└── functions/ or demo-functions/
    └── api.mts                 # demo/mirror surface when applicable

docs/
└── CP-SAT and resource requirement documents used as source context
```

**Structure Decision**: Keep the feature in the existing backend/frontend scheduling structure. The backend remains the authoritative implementation for CP-SAT behavior; frontend work consumes and displays normalized result metadata; Netlify or demo code is checked for contract drift and either aligned or clearly degraded.

## Phase 0: Research

Research completed in [research.md](research.md). Decisions cover the authoritative scheduling path, insufficient-current-resource behavior, minimum-resource candidate refinement, same-structure same-process rules, control-target scope, and result-source vocabulary.

## Phase 1: Design & Contracts

- Data model: [data-model.md](data-model.md)
- Interface contract: [contracts/fixed-resource-scheduling-contract.md](contracts/fixed-resource-scheduling-contract.md)
- Validation guide: [quickstart.md](quickstart.md)

## Constitution Check - Post-Design

- Requirement and source grounding remain traceable through `spec.md`, `research.md`, and this plan. **PASS**
- Algorithm inputs, outputs, hard constraints, soft constraints, objective/fallback behavior, and acceptance examples are captured across `spec.md`, `data-model.md`, and `quickstart.md`. **PASS**
- Frontend-backend contract effects are explicit in `contracts/fixed-resource-scheduling-contract.md`. **PASS**
- The work is phased and taskable without implementation beginning before user confirmation. **PASS**
- No new dependency, storage layer, README update, commit, push, or deploy is required by this plan. **PASS**

## Complexity Tracking

No constitution violations identified.
