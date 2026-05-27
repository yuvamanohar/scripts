# Requirement Intake

Use this process before writing a PRD or implementing non-trivial work.

## Intake Goals

Capture enough information to avoid building the wrong thing:

- problem statement
- target user
- current workflow
- desired workflow
- inputs and outputs
- constraints
- risks
- acceptance criteria

## Intake Questions

Ask only questions that change implementation decisions. Prefer discovering
answers from the repo before asking the user.

Key questions:

- What problem should this solve?
- Who uses it and how often?
- What inputs are expected?
- What output or behavior proves success?
- What should not change?
- What errors or edge cases matter most?
- Is this a one-off script, reusable tool, or release-ready feature?

## Intake Output

Write the result using `docs/templates/requirement-intake.md`.

For small tasks, a short section in the implementation plan is enough. For
larger tasks, save the intake document near the relevant subproject or under
`docs/requirements/` if that folder exists.
