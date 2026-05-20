# sync_folders

Sync missing or changed files from one folder to another.

`sync_folders.py` compares every file in a source folder against the matching
path in a target folder. Files are considered different when the target copy is
missing, has a different size, or has a different modified time. Only those
missing or changed files are copied with `rsync`.

## Requirements

- Python 3.10+
- `rsync`

`sync_folders.sh` is kept as a small compatibility wrapper around the Python
implementation.

## Usage

```bash
./sync_folders.py <source_folder> <target_folder>
```

The wrapper still works:

```bash
./sync_folders.sh <source_folder> <target_folder>
```

Example:

```bash
./sync_folders.py /path/to/source /path/to/backup
```

The source folder must already exist. If the target folder does not exist, the
script creates it.

Optional environment variables:

- `SYNC_BATCH_SIZE` - positive integer for files per `rsync` batch; defaults to `5`
- `SYNC_MAX_RETRIES` - positive integer for failed-file retry attempts; defaults to `3`
- `SYNC_RETRY_BATCH_SIZES` - comma-separated positive integers for retry
  batch sizes by attempt; defaults to `3,2,1`
- `SYNC_OUTPUT_DIR` - directory for log/report files; defaults to the current directory
- `RSYNC_BIN` - alternate `rsync` executable, useful for tests

Equivalent CLI flags are available:

- `--batch-size`
- `--max-retries`
- `--retry-batch-sizes`
- `--output-dir`
- `--rsync-bin`

## What It Does

1. Validates that exactly two folder paths were provided.
2. Confirms both folders exist.
3. Scans every regular file under the source folder.
4. Builds a list of files that are missing or changed in the target folder.
5. Writes a human-readable diff report.
6. Copies only the missing or changed files from source to target using `rsync`.
7. Records files from failed batches as retry candidates if any `rsync`
   operation fails.
8. Re-checks failed-file candidates after each retry and keeps
   `failed_files.txt` as a live list of only files that still need recovery.

## Output Files

The script writes these files in the directory where you run it:

- `sync_folders.log` - timestamped progress and `rsync` output
- `diff_files.txt` - list of missing and changed files
- `failed_files.txt` - created only when one or more files remain unresolved
  after a failed batch or retry attempt

Temporary batch files are created with Python's `tempfile` module and cleaned
up automatically after each batch.

## Sync Behavior

- Directory structure is preserved relative to the source folder.
- Existing target files are overwritten when their size or whole-second modified
  time differs.
- Extra files that exist only in the target folder are not deleted.
- File comparison uses size and whole-second modified time, not file checksums.
- Files are synced in batches. The default batch size is 5.
- Files from failed batches are retried up to 3 times by default. Before each
  retry, the script re-checks those files and removes any that already synced.
- Retry attempts use smaller batches by default: `3`, then `2`, then `1`. If
  more retries are configured than retry batch sizes, the final retry batch
  size is reused.

## Tests

Run the test suite from the repo root:

```bash
python3 sync_folders/tests/run_tests.py
```

The compatibility wrapper also works:

```bash
./sync_folders/tests/run_tests.sh
```

The test runner uses only the Python standard library and reports line coverage
for `sync_folders.py`. It fails when coverage is below 90%.

## Exit Codes

- `0` - sync completed successfully, or nothing needed to be synced
- `1` - invalid usage, missing directory, or one or more sync batches failed
