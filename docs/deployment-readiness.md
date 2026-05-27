# Deployment Readiness

Use this checklist before presenting a script as ready for regular use.

## Checklist

- README usage is current.
- Required runtime tools are documented.
- CLI flags and environment variables are documented.
- Output files are documented.
- Failure modes and exit codes are documented.
- Tests pass.
- Generated output files are excluded from commits unless intentionally tracked.
- Rollback or recovery steps are clear for risky filesystem operations.

## Local Script Release

For this repo, deployment usually means the script is ready to run locally.
Before release:

1. Run the relevant tests.
2. Run a small manual smoke test when filesystem behavior changed.
3. Check `git diff` for accidental generated files.
4. Update subproject context.
5. Update README if usage changed.

## Safety Notes

Scripts that copy, overwrite, or delete files should clearly document:

- what paths they touch
- whether target-only files are preserved or deleted
- whether changes are reversible
- where logs or reports are written
- how to run a dry run if available
