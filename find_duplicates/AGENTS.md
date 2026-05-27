# find_duplicates Agent Instructions

Read this file with `find_duplicates/context.md` before changing this utility.

## Scope

`find_duplicates` scans a folder, groups candidate duplicates by size and hash,
confirms matches with byte comparison, and can optionally delete duplicates
using an explicit keep policy.

## Important Files

- `find_duplicates.py` - current single-file CLI implementation
- `duplicates.txt` - generated duplicate report
- `find_duplicates.log` - generated log/output artifact

## Behavior To Preserve

- Default hash is `sha256`.
- Candidate files are grouped by size before hashing.
- Hash matches are confirmed with byte-for-byte comparison.
- Deletion only happens when `--delete` is supplied.
- Unprocessed files are reported separately.
- Errors processing individual files should not stop the whole scan when they
  can be recorded and skipped.

## Testing

There is currently no dedicated test suite. For behavior changes, prefer adding
tests before expanding the tool. At minimum, use a temporary directory smoke
test and report the command used.

## Generated Files

Treat these as generated output unless the task explicitly targets them:

- `duplicates.txt`
- `unprocessed_files.txt`
- `find_duplicates.log`

## Context Updates

Update `find_duplicates/context.md` when changing CLI behavior, duplicate
detection semantics, deletion policy, output files, tests, or known limitations.
