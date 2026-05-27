# PRD Process

A PRD is required when work changes user-facing behavior, adds a new workflow,
or affects safety-sensitive filesystem operations.

## When To Write A PRD

Write or update a PRD for:

- new commands or flags
- destructive behavior such as deleting files
- sync semantics
- UI workflows
- output/report format changes
- deployment or packaging changes

Skip a PRD for:

- typo fixes
- small internal refactors
- tests that preserve behavior
- context/doc updates that do not change product behavior

## PRD Sections

Use `docs/templates/prd.md`.

Required sections:

- Problem
- Goals
- Non-goals
- Users
- Current behavior
- Proposed behavior
- Functional requirements
- Acceptance criteria
- Risks
- Open questions

## Approval

Do not implement a PRD until one of these is true:

- The user explicitly approves it.
- The user already provided enough detail and asked for implementation.
- The change is small enough that a PRD is unnecessary.

If approval is needed, stop after the PRD and ask for approval.
