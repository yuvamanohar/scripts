# Development Pipeline

This repo demonstrates a complete but lightweight development pipeline for
small automation projects.

## Pipeline Stages

1. Requirement intake
2. Clarification and scope control
3. PRD drafting
4. PRD approval
5. Implementation planning
6. Code changes
7. Tests and verification
8. Review readiness
9. Deployment readiness
10. Context update

## Stage Gates

Use explicit gates when a change is larger than a bug fix or small refactor:

- Intake approved: the problem, user, and desired outcome are clear.
- PRD approved: behavior, constraints, and non-goals are agreed.
- Plan approved: implementation slices and verification are clear.
- Review ready: tests pass and user-facing behavior is documented.
- Deployment ready: rollback, usage, and operational notes are prepared.

## Default Agent Flow

For each task:

1. Read `AGENTS.md`, root `context.md`, and the nearest subproject context.
2. Classify the task as docs-only, bug fix, feature, refactor, or release prep.
3. Use `docs/requirement-intake.md` for unclear requirements.
4. Use `docs/prd-process.md` for new user-facing behavior.
5. Use `docs/implementation-process.md` for coding work.
6. Use `docs/testing-process.md` before declaring the work complete.
7. Use `docs/deployment-readiness.md` before release or production use.

## Task Size Guidance

- Tiny: direct change, focused verification, update context only if durable
  behavior changes.
- Small: brief implementation plan, tests for affected behavior, update context.
- Medium: PRD, plan, implementation slices, tests, review checklist.
- Large: split into separate approved PRDs or milestones.

## Done Definition

A task is done when:

- The requested behavior or document exists.
- The relevant verification has been run or clearly marked not run.
- Generated files are not accidentally included as source changes.
- Durable context is updated when future agents need it.
- The final response states what changed and how it was verified.
