---
name: speckit-specify
description: Create or update a formal feature specification from the user's requirement. Use when a project change needs Spec Kit; this stage also resolves only implementation-blocking ambiguity.
---

# Workflow

1. Treat the triggering user text as the feature description. If it is empty, stop and request the description.
2. Derive one concise `SHORT_NAME`, then run the deterministic creator exactly once from the repository root:

   ```powershell
   .specify/scripts/powershell/create-new-feature.ps1 -Json -ShortName "<SHORT_NAME>" "<feature description>"
   ```

   Use the returned `SPEC_FILE`, `FEATURE_NUM`, and feature directory. Do not scan numbers, create directories, copy templates, or edit `.specify/feature.json` manually.
3. Load the resolved spec template and `.specify/memory/constitution.md` once.
4. Write the specification as business intent, not implementation design. Include only applicable user stories, testable requirements, measurable success criteria, scope, edge/error cases, assumptions, entities, and source references.
5. Use a reasonable documented default for non-critical gaps. If no safe default exists and the answer changes scope, security/privacy, data meaning, or acceptance, ask one concise question at a time, at most three in total, and update the affected requirement directly after each answer. Do not create a separate clarification artifact or stage.
6. Validate the completed spec once against the template and Constitution. Repair source-supported omissions once; if a blocking ambiguity or conflict remains, record it and stop before planning. Do not create a checklist unless the user explicitly invokes `$speckit-checklist`.

# Completion

Report the feature directory, `SPEC_FILE`, resolved assumptions or questions, remaining blockers, and readiness for `$speckit-plan`. Stop after the spec is complete and validated.
