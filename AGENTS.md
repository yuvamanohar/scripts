# Agent Instructions

This repository is a sample development pipeline for small local automation
scripts. Agents should use the docs and context files to avoid re-reading the
entire codebase on every task.

## Start Here

1. Read this file.
2. Read `context.md` at the repo root.
3. Read the nearest subproject `context.md` and `AGENTS.md` for the requested
   work area.
4. Inspect only the source, tests, and docs needed for the task.
5. Check `git status --short` before editing.

## Ignore By Default

Do not spend context on generated or environment files unless the task is about
them:

- `.git/`
- `.venv/`
- `venv/`
- `out/`
- `*.log`
- generated reports such as `diff_files.txt`, `failed_files.txt`,
  `duplicates.txt`, and `unprocessed_files.txt`

## Source Of Truth

- Source code and tests are authoritative.
- Context files are durable summaries, not specifications.
- If context and source disagree, trust source and update context when the task
  changes durable behavior.

## Development Workflow

Use the pipeline in `docs/development-pipeline.md`:

1. Intake requirements.
2. Write or update a PRD for non-trivial work.
3. Get approval before implementation when scope or behavior is not obvious.
4. Implement in the smallest sensible slice.
5. Add or update tests based on risk.
6. Run the relevant verification commands.
7. Update context files when future agents should know about the change.
8. Prepare the change for review or deployment.

## Coding Standards

- Prefer standard library Python unless a dependency has clear value.
- Keep command-line tools scriptable and predictable.
- Separate parsing/configuration, orchestration, filesystem work, and reporting
  when a script grows beyond one file.
- Avoid hidden destructive behavior. Require explicit flags for deletes,
  overwrites beyond documented sync behavior, or broad filesystem changes.
- Preserve existing CLI compatibility unless the requirement explicitly changes
  it.
- Use deterministic output ordering where practical.
- Keep error messages actionable and include relevant paths.

## Testing Expectations

- Run the nearest test command for any code change.
- For `sync_folders`, run:

```bash
python3 sync_folders/tests/run_tests.py
```

- For doc-only changes, tests are not required unless examples or commands were
  changed in a way that should be verified.

## Context Maintenance

Update context files when a change affects:

- architecture or module responsibilities
- public CLI behavior
- configuration or environment variables
- output files
- test commands
- known limitations or tradeoffs
- follow-up work that future agents should see immediately

Keep context files short. Link to fuller docs instead of duplicating long
process text.
