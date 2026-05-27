# sync_folders Context

Durable working context for `sync_folders`. Keep this short and update it when
source changes affect how future work should start.

## Overview

- Main command: `sync_folders.py`
- Compatibility wrapper: `sync_folders.sh`
- The top-level Python script is a thin CLI/import facade.
- Implementation lives in `sync_folders_lib/`.
- Local agent instructions: `sync_folders/AGENTS.md`

## Useful Entry Points

- `build_config(...)` in `sync_folders_lib/config.py`
- `sync_folders(config, stream=...)` in `sync_folders_lib/app.py`
- `compute_differences(source, target)` in `sync_folders_lib/diff.py`

## Current Behavior

- Compares source and target files by size and whole-second modified time.
- Syncs only missing or changed files with `rsync`.
- Preserves relative directory structure.
- Does not delete extra files in the target.
- Writes output files to `out` by default.

## User-Facing Config

- source folder
- target folder
- output directory
- batch size
- max retries
- retry batch sizes
- rsync binary

## Output Files

- `out/sync_folders.log`
- `out/diff_files.txt`
- `out/failed_files.txt` when failures remain unresolved

## Tests

- From repo root: `python3 sync_folders/tests/run_tests.py`

## Local Workflow

- Read `sync_folders/AGENTS.md` before changing this utility.
- Treat files under `sync_folders/out/` as generated output unless the task is
  specifically about reports or logs.

## UI Notes

- A desktop UI is a natural fit because this script operates on local folders.
- Practical options:
  - Tkinter: fastest, stdlib, basic look.
  - CustomTkinter: nicer local desktop app with small dependency.
  - PySide6/Qt: most polished, heavier dependency.
  - Streamlit: quick browser UI, more dev-tool feel.
  - FastAPI/Flask: flexible local web app, more moving parts.
- Likely first UI should expose:
  - source and target folder pickers
  - output directory picker
  - batch/retry controls
  - preview differences
  - run sync
  - live log output
  - paths to generated reports
- Current `sync_folders(config, stream=...)` can send log messages to a UI stream.
- True live `rsync` output, cancel support, and granular progress may need a small
  job/progress layer around `run_rsync()`.
