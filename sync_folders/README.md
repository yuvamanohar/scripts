# sync_folders

Sync missing or changed files from one folder to another.

`sync_folders.sh` compares every file in a source folder against the matching
path in a target folder. Files are considered different when the target copy is
missing, has a different size, or has a different modified time. Only those
missing or changed files are copied with `rsync`.

## Requirements

- Bash
- `find`
- `stat`
- `rsync`

Note: this script uses the macOS/BSD `stat` flags (`stat -f`). On Linux, the
`stat` commands would need to be adjusted.

## Usage

```bash
./sync_folders.sh <source_folder> <target_folder>
```


Example:

```bash
./sync_folders.sh /path/to/source /path/to/backup
```

Both arguments must be existing directories. The script does not create the
target folder for you.

## What It Does

1. Validates that exactly two folder paths were provided.
2. Confirms both folders exist.
3. Scans every regular file under the source folder.
4. Builds a list of files that are missing or changed in the target folder.
5. Writes a human-readable diff report.
6. Copies only the missing or changed files from source to target using `rsync`.
7. Records failed batches if any `rsync` operation fails.

## Output Files

The script writes these files in the directory where you run it:

- `sync_folders.log` - timestamped progress and `rsync` output
- `diff_files.txt` - list of missing and changed files
- `failed_files.txt` - created only when one or more sync batches fail

Temporary batch files are created with `mktemp` and cleaned up automatically
when the script exits.

## Sync Behavior

- Directory structure is preserved relative to the source folder.
- Existing target files are overwritten when their size or modified time differs.
- Extra files that exist only in the target folder are not deleted.
- File comparison uses size and modified time, not file checksums.
- Files are synced in batches of 2.

## Exit Codes

- `0` - sync completed successfully, or nothing needed to be synced
- `1` - invalid usage, missing directory, or one or more sync batches failed

