# Research: CP-SAT Fixed Resource Scheduling

## Decision 1: Backend Scheduling Path Is Authoritative

**Decision**: Treat the Python backend scheduling path as the authoritative behavior for fixed-resource scheduling, minimum-resource recommendations, refinement, fallback labels, and diagnostics. Any demo or mirror implementation must align with the same user-visible contract or clearly degrade.

**Rationale**: The current project handbook identifies the FastAPI + OR-Tools path as the engineering and validation source. The Netlify/demo surface is a presentation or mirror layer and should not redefine algorithm behavior.

**Alternatives considered**:

- Make all surfaces fully equivalent in the first phase: rejected because it risks expanding scope beyond the algorithm and result contract.
- Ignore mirror/demo behavior: rejected because users may see contradictory labels or incomplete candidate results.

## Decision 2: Preserve Delayed Current-Resource Schedules

**Decision**: When current resources delay mandatory milestones, keep and return the current-resource reference schedule with delay diagnostics instead of returning only an infeasible status.

**Rationale**: The user explicitly wants to know approximately how much the current resource plan deviates. This also gives a meaningful baseline for comparing any minimum-resource candidate.

**Alternatives considered**:

- Hide the schedule when mandatory milestones are delayed: rejected because it removes the user's primary diagnostic evidence.
- Force a refined current-resource schedule despite mandatory delay: rejected for the first phase because the current-resource branch is already known not to satisfy mandatory milestones.

## Decision 3: Minimum-Resource Candidates Must Be Refined After Verification

**Decision**: After minimum-resource quantities are verified feasible, rerun the refinement flow for the candidate plan. If candidate refinement fails or times out, return the verified feasible schedule as a fallback and label the source.

**Rationale**: Current-resource sufficient plans and minimum-resource candidate plans need comparable user-facing quality. A raw feasible candidate is useful for validation but may be less suitable for resource-lane review.

**Alternatives considered**:

- Return only recommended resource counts: rejected because it cannot support plan comparison.
- Return only the raw feasible candidate: rejected by user correction; the candidate also needs refinement.
- Require refinement success before returning any candidate: rejected because it would hide a verified feasible resource option when refinement is the only failing step.

## Decision 4: Same-Structure Same-Process Rules Remain Explicit Configuration

**Decision**: Enforce configured same-structure same-process binding and parallel-limit rules, and do not invent these rules solely from resource type.

**Rationale**: Resource configuration is the business source of these constraints. The documents explicitly require avoiding hard-coded resource-type behavior when configuration fields are absent.

**Alternatives considered**:

- Hard-code drilling and template rules by resource type: rejected because it would bypass the resource configuration page and create hidden behavior.
- Defer these rules to a later phase: rejected because the user confirmed they must be retained in the first phase.

## Decision 5: Control Targets Are Limited in Phase One

**Decision**: In the first phase, control targets come only from explicit task control attributes and cast-in-place continuous-beam recognition.

**Rationale**: This avoids turning milestone evaluation ranges into broad control-target sets and keeps refinement explainable without a new control-target setup UI.

**Alternatives considered**:

- Treat all tasks in a milestone scope as control targets: rejected because source documents explicitly warn against this.
- Add a control-target configuration page: rejected as out of scope for the first phase.

## Decision 6: Result Source Labels Are Part of the Contract

**Decision**: Normalize user-visible result source labels for current-resource reference, current-resource refinement, current-resource fallback, minimum-resource refinement, and minimum-resource fallback.

**Rationale**: Users must know whether a displayed plan is a reference, a refined plan, or a fallback. Testing also needs stable states to assert.

**Alternatives considered**:

- Infer source from status only: rejected because status does not distinguish fallback/refinement paths.
- Use only free-text diagnostics: rejected because frontend display and tests need consistent categories.
