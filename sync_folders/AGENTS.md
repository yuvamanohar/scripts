# sync_folders Agent Instructions

Read this file with `sync_folders/context.md` before changing this utility.

## Scope

`sync_folders` copies files that are missing or changed from a source folder to
a target folder. It should remain safe for local backup-style workflows.

## Important Files

- `sync_folders.py` - executable facade and import compatibility entry point
- `sync_folders.sh` - compatibility wrapper with virtual environment bootstrap
- `sync_folders_lib/config.py` - configuration, environment, validation
- `sync_folders_lib/app.py` - high-level orchestration
- `sync_folders_lib/diff.py` - source traversal and file comparison
- `sync_folders_lib/rsync.py` - batching, rsync execution, retries
- `sync_folders_lib/report.py` - report output
- `tests/` - current test suite

## Behavior To Preserve

- The target directory is created when missing.
- Extra files in the target are not deleted.
- Missing or changed files are copied with `rsync`.
- File comparison uses size and whole-second modified time.
- Output defaults to `sync_folders/out`.
- Existing CLI and wrapper usage should keep working unless a PRD says
  otherwise.

## Verification

Run from the repo root:

```bash
python3 sync_folders/tests/run_tests.py
```

## Generated Files

Treat these as generated output unless the task explicitly targets them:

- `out/sync_folders.log`
- `out/diff_files.txt`
- `out/failed_files.txt`
- `sync_folders.out`

## Context Updates

Update `sync_folders/context.md` when changing CLI behavior, sync semantics,
configuration, output files, tests, or known limitations.
