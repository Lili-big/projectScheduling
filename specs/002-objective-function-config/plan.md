# Implementation Plan: Objective Function Configuration

**Branch**: `[002-objective-function-config]` | **Date**: 2026-07-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-objective-function-config/spec.md`

## Summary

Add pre-solve objective-function controls to the full historical simulation page and pass the selected objective terms into CP-SAT refinement. The implementation extends the existing schedule strategy contract, validates and normalizes objective terms on the backend, applies effective weights in `solve_control_priority_schedule()`, and exposes result metadata for audit while leaving the MVP page and resource-cost optimization behavior unchanged.

## Technical Context

**Language/Version**: Python 3.11-compatible backend, TypeScript/React frontend

**Primary Dependencies**: FastAPI, Pydantic, OR-Tools CP-SAT, pytest, React, Vite

**Storage**: Existing request scenario state only; no local persistence change

**Testing**: `pytest backend/tests -q`, `npm --prefix frontend run build`, browser validation on `127.0.0.1:8000`

**Target Platform**: Local FastAPI scheduling service with React frontend; Netlify demo contract compatibility

**Project Type**: Web app with backend scheduling service and frontend simulation UI

**Performance Goals**: Preserve existing bounded solver behavior; objective configuration should not add extra solve stages

**Constraints**: No README update, no commit, no deploy, no hard-constraint editing, no MVP page changes, no new dependencies

**Scale/Scope**: Current bridge scheduling demo scenarios and the 10 existing refinement soft objective terms

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- Requirement review completed or explicitly not required for a narrow change. **PASS**: user supplied and confirmed the implementation plan.
- Source docs and Demo/code facts are cited in `spec.md`. **PASS**.
- Scheduling, resource, duration, CP-SAT, and frontend/backend contract impacts are explicit. **PASS**.
- Inputs, outputs, constraints, edge cases, and acceptance criteria are testable. **PASS**.
- No Demo-only limitation is promoted into product intent without explicit approval. **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/002-objective-function-config/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── objective-function-config-contract.md
├── checklists/
│   └── requirements.md
├── analysis.md
└── tasks.md
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── models.py
│   └── solver.py
└── tests/
    └── test_scheduler.py

frontend/
└── src/
    ├── app/App.tsx
    ├── styles.css
    └── types/scheduler.ts

netlify/
└── demo-functions/api.mts
```

**Structure Decision**: Reuse the existing schedule strategy, solver, test, full simulation page, and Netlify demo files. No new runtime module or dependency is required.

## Phase 0: Research

Research completed in [research.md](research.md). Decisions cover strategy extension, soft-objective-only scope, default compatibility, result metadata, and Netlify demo compatibility.

## Phase 1: Design & Contracts

- Data model: [data-model.md](data-model.md)
- Interface contract: [contracts/objective-function-config-contract.md](contracts/objective-function-config-contract.md)
- Validation guide: [quickstart.md](quickstart.md)

## Constitution Check - Post-Design

- Existing docs and solver/page code are reused. **PASS**
- Objective inputs, outputs, hard/soft boundary, validation, and result metadata are explicit. **PASS**
- Frontend-backend contract effects and stale-result invalidation are explicit. **PASS**
- No new persistence, dependency, README update, deployment, or git action is required. **PASS**

## Complexity Tracking

No constitution violations identified.
