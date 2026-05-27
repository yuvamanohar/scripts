# find_duplicates Context

Durable working context for `find_duplicates`. Keep this short and update it
when source changes affect how future work should start.

## Overview

- Main command: `find_duplicates.py`
- Current shape: single-file Python CLI.
- Purpose: find duplicate files under a folder and optionally delete duplicates
  according to an explicit keep policy.

## Current Behavior

- Groups files by size before hashing.
- Uses `sha256` by default; `md5` is optional.
- Supports parallel hashing with `--jobs`.
- Confirms matching hashes with byte-for-byte comparison.
- Supports `--min-size` and `--max-depth`.
- Writes duplicate groups to `duplicates.txt` by default.
- Writes files that could not be processed to `unprocessed_files.txt` when
  needed.
- Optional deletion requires `--delete` with one of: `first`, `newest`,
  `oldest`, `shortest`.

## Useful Entry Points

- `parse_args()` - CLI options.
- `gather_files(args)` - traversal and size grouping.
- `hash_file(path, algo_name)` - file hashing.
- `cmp_files(path_a, path_b)` - byte comparison.
- `choose_keep(paths, policy)` - deletion keep policy.
- `main()` - orchestration and output writing.

## Tests

- No dedicated automated test suite exists yet.
- For future changes, prefer adding tests around temporary directories and
  generated report files.

## Known Tradeoffs

- The implementation is still a single file; if behavior grows, split CLI,
  scanning, hashing, reporting, and deletion into separate modules.
- Deletion is real and irreversible from the script's perspective. Keep it
  explicit and test with temporary directories.
