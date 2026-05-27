# Implementation Process

Use this process after requirements are clear.

## Before Editing

1. Check `git status --short`.
2. Read the nearest `context.md` and `AGENTS.md`.
3. Read only the source and tests needed for the task.
4. Identify generated files and avoid treating them as source.
5. State the planned edits before changing files.

## Implementation Plan

Use `docs/templates/implementation-plan.md` for medium or larger changes.

The plan should include:

- files expected to change
- behavior being added or changed
- tests to add or update
- verification commands
- context files to update

## Coding Guidelines

- Keep changes scoped to the requested behavior.
- Prefer small pure functions around filesystem logic.
- Keep CLI parsing separate from business logic when practical.
- Make outputs deterministic for tests.
- Do not introduce dependencies without a clear reason.
- Preserve backward compatibility unless the requirement says otherwise.

## After Editing

1. Run focused tests.
2. Inspect `git diff`.
3. Update relevant context files.
4. Summarize changed files and verification.
