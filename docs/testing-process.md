# Testing Process

Testing should match the risk and scope of the change.

## Test Levels

- Docs-only: no tests required unless commands or examples changed.
- Small code change: run the nearest focused test.
- CLI behavior change: add or update CLI-level tests.
- Filesystem behavior change: use temporary directories and assert files,
  reports, and exit codes.
- Destructive behavior: test dry-run or explicit confirmation paths before
  testing deletion.

## Current Commands

For `sync_folders`:

```bash
python3 sync_folders/tests/run_tests.py
```

For `find_duplicates`, there is currently no dedicated test suite. Prefer
adding tests before expanding behavior.

## Verification Notes

Record in the final response:

- commands run
- pass/fail result
- tests not run and why

Do not hide verification gaps.
