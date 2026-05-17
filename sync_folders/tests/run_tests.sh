#!/usr/bin/env bash

set -euo pipefail

TEST_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
PROJECT_DIR=$(cd "$TEST_DIR/.." && pwd)
SCRIPT="$PROJECT_DIR/sync_folders.sh"
TMP_ROOT=$(mktemp -d)
PASS_COUNT=0
FAIL_COUNT=0

cleanup_all() {
  rm -rf "$TMP_ROOT"
}
trap cleanup_all EXIT

coverage_percent() {
  local trace_file=$1
  local executable_file="$TMP_ROOT/executable_lines.txt"
  local covered_file="$TMP_ROOT/covered_lines.txt"
  local matched_file="$TMP_ROOT/matched_lines.txt"
  local executable_count
  local covered_count

  awk '
    /^[[:space:]]*[0-9]+[[:space:]]*$/ { next }
    /^[[:space:]]*[0-9]+[[:space:]]*#/ { next }
    /^[[:space:]]*[0-9]+[[:space:]]*$/ { next }
    /^[[:space:]]*[0-9]+[[:space:]]*(else|fi|done|\}|\{)[[:space:]]*$/ { next }
    /^[[:space:]]*[0-9]+[[:space:]]*[[:alnum:]_]+\(\)[[:space:]]*\{[[:space:]]*$/ { next }
    { print $1 }
  ' < <(nl -ba "$SCRIPT") | sort -n -u > "$executable_file"

  grep -E "^\\++$SCRIPT:" "$trace_file" |
    sed -E "s#^\\++$SCRIPT:([0-9]+):.*#\\1#" |
    sort -n -u > "$covered_file" || true

  comm -12 "$executable_file" "$covered_file" > "$matched_file"
  executable_count=$(wc -l < "$executable_file" | tr -d ' ')
  covered_count=$(wc -l < "$matched_file" | tr -d ' ')
  awk -v covered="$covered_count" -v executable="$executable_count" 'BEGIN { printf "%.2f", (covered / executable) * 100 }'
}

if [[ "${SYNC_FOLDERS_TEST_CHILD:-0}" != "1" ]]; then
  TRACE_FILE="$TMP_ROOT/coverage.trace"
  RESULT_FILE="$TMP_ROOT/results.out"

  if PS4='+${BASH_SOURCE}:${LINENO}: ' SYNC_FOLDERS_TEST_CHILD=1 bash -x "$0" > "$RESULT_FILE" 2> "$TRACE_FILE"; then
    CHILD_STATUS=0
  else
    CHILD_STATUS=$?
  fi

  cat "$RESULT_FILE"
  COVERAGE=$(coverage_percent "$TRACE_FILE")
  echo "coverage - sync_folders.sh: $COVERAGE%"

  if awk -v coverage="$COVERAGE" 'BEGIN { exit !(coverage >= 90) }'; then
    echo "ok - coverage is at least 90%"
  else
    echo "not ok - coverage is below 90%" >&2
    CHILD_STATUS=1
  fi

  exit "$CHILD_STATUS"
fi

# shellcheck source=../sync_folders.sh
source "$SCRIPT"

assert_eq() {
  local expected=$1
  local actual=$2
  local message=$3

  if [[ "$expected" != "$actual" ]]; then
    echo "not ok - $message: expected '$expected', got '$actual'" >&2
    return 1
  fi
}

assert_file_contains() {
  local file=$1
  local expected=$2
  local message=$3

  if ! grep -Fq -- "$expected" "$file"; then
    echo "not ok - $message: '$expected' not found in $file" >&2
    return 1
  fi
}

assert_file_missing() {
  local file=$1
  local message=$2

  if [[ -e "$file" ]]; then
    echo "not ok - $message: $file exists" >&2
    return 1
  fi
}

reset_env() {
  unset SYNC_OUTPUT_DIR SYNC_BATCH_SIZE RSYNC_BIN
  cleanup || true
}

new_workspace() {
  local name=$1
  WORK="$TMP_ROOT/$name"
  SOURCE_DIR="$WORK/source"
  TARGET_DIR="$WORK/target"
  OUTPUT_DIR="$WORK/output"

  mkdir -p "$SOURCE_DIR" "$TARGET_DIR" "$OUTPUT_DIR"
}

prepare_script_state() {
  export SYNC_OUTPUT_DIR="$OUTPUT_DIR"
  configure "$SOURCE_DIR" "$TARGET_DIR"
  make_temp_files
}

make_fake_rsync() {
  local exit_code=$1
  local bin="$WORK/fake_rsync"

  {
    echo '#!/usr/bin/env bash'
    echo 'echo "$@" >> "$FAKE_RSYNC_CALLS"'
    echo "exit $exit_code"
  } > "$bin"
  chmod +x "$bin"
  export RSYNC_BIN="$bin"
  export FAKE_RSYNC_CALLS="$WORK/rsync_calls.txt"
}

test_validate_args_rejects_bad_input() {
  reset_env
  new_workspace validate

  if validate_args "$SOURCE_DIR"; then
    echo "not ok - validate_args accepted one argument" >&2
    return 1
  fi

  if validate_args "$SOURCE_DIR/missing" "$TARGET_DIR"; then
    echo "not ok - validate_args accepted missing source" >&2
    return 1
  fi

  if validate_args "$SOURCE_DIR" "$TARGET_DIR/missing"; then
    echo "not ok - validate_args accepted missing target" >&2
    return 1
  fi

  validate_args "$SOURCE_DIR" "$TARGET_DIR"
}

test_configure_normalizes_paths_and_validates_options() {
  reset_env
  new_workspace configure

  export SYNC_OUTPUT_DIR="$OUTPUT_DIR/"
  export SYNC_BATCH_SIZE=3
  configure "$SOURCE_DIR/" "$TARGET_DIR/"

  assert_eq "$SOURCE_DIR" "$SOURCE" "source path was normalized"
  assert_eq "$TARGET_DIR" "$TARGET" "target path was normalized"
  assert_eq "$OUTPUT_DIR" "$OUTPUT_DIR" "output path was normalized"
  assert_eq 3 "$BATCH_SIZE" "batch size was configured"
  assert_eq "$OUTPUT_DIR/diff_files.txt" "$DIFF_REPORT" "diff report path was configured"

  export SYNC_BATCH_SIZE=0
  if configure "$SOURCE_DIR" "$TARGET_DIR"; then
    echo "not ok - configure accepted invalid batch size" >&2
    return 1
  fi

  export SYNC_BATCH_SIZE=1
  export SYNC_OUTPUT_DIR="$WORK/missing-output"
  if configure "$SOURCE_DIR" "$TARGET_DIR"; then
    echo "not ok - configure accepted missing output directory" >&2
    return 1
  fi
}

test_files_differ_detects_missing_equal_size_and_mtime() {
  reset_env
  new_workspace differ

  printf 'same\n' > "$SOURCE_DIR/file.txt"
  assert_eq 0 "$(files_differ "$SOURCE_DIR/file.txt" "$TARGET_DIR/file.txt"; echo $?)" "missing target differs"

  cp -p "$SOURCE_DIR/file.txt" "$TARGET_DIR/file.txt"
  assert_eq 1 "$(files_differ "$SOURCE_DIR/file.txt" "$TARGET_DIR/file.txt"; echo $?)" "identical files do not differ"

  printf 'different\n' > "$TARGET_DIR/file.txt"
  assert_eq 0 "$(files_differ "$SOURCE_DIR/file.txt" "$TARGET_DIR/file.txt"; echo $?)" "size difference differs"

  printf 'same\n' > "$TARGET_DIR/file.txt"
  touch -t 202401010101 "$SOURCE_DIR/file.txt"
  touch -t 202401010102 "$TARGET_DIR/file.txt"
  assert_eq 0 "$(files_differ "$SOURCE_DIR/file.txt" "$TARGET_DIR/file.txt"; echo $?)" "mtime difference differs"
}

test_file_stat_linux_fallbacks() {
  reset_env
  new_workspace linux_stat
  printf 'fallback\n' > "$SOURCE_DIR/file.txt"

  stat() {
    if [[ "$1" == "-f" ]]; then
      return 1
    fi

    if [[ "$1" == "-c" && "$2" == "%s" ]]; then
      command stat -f %z "$3"
      return
    fi

    if [[ "$1" == "-c" && "$2" == "%Y" ]]; then
      command stat -f %m "$3"
      return
    fi

    return 2
  }

  assert_eq "$(command stat -f %z "$SOURCE_DIR/file.txt")" "$(file_size "$SOURCE_DIR/file.txt")" "Linux size fallback"
  assert_eq "$(command stat -f %m "$SOURCE_DIR/file.txt")" "$(file_mtime "$SOURCE_DIR/file.txt")" "Linux mtime fallback"
}

test_compute_differences_and_report() {
  reset_env
  new_workspace compute
  mkdir -p "$SOURCE_DIR/nested" "$TARGET_DIR/nested"

  printf 'same\n' > "$SOURCE_DIR/unchanged.txt"
  cp -p "$SOURCE_DIR/unchanged.txt" "$TARGET_DIR/unchanged.txt"
  printf 'missing\n' > "$SOURCE_DIR/nested/missing.txt"
  printf 'source\n' > "$SOURCE_DIR/changed.txt"
  printf 'target-target\n' > "$TARGET_DIR/changed.txt"

  prepare_script_state
  compute_differences
  write_diff_report

  assert_eq 3 "$total_files" "total source file count"
  assert_eq 1 "$missing_count" "missing file count"
  assert_eq 1 "$changed_count" "changed file count"
  assert_file_contains "$DIFF_REPORT" "nested/missing.txt" "report includes missing file"
  assert_file_contains "$DIFF_REPORT" "changed.txt" "report includes changed file"

  has_sync_work
}

test_write_diff_report_prints_none_for_empty_lists() {
  reset_env
  new_workspace empty_report
  prepare_script_state
  compute_differences
  write_diff_report

  assert_file_contains "$DIFF_REPORT" "Missing files (0):" "empty report has missing header"
  assert_file_contains "$DIFF_REPORT" "Changed files (0):" "empty report has changed header"
  assert_file_contains "$DIFF_REPORT" "(none)" "empty report prints none"

  if has_sync_work; then
    echo "not ok - empty sync list reported work" >&2
    return 1
  fi
}

test_run_batch_success_and_zero_batch() {
  reset_env
  new_workspace batch_success
  prepare_script_state
  make_fake_rsync 0

  : > "$LOG_FILE"
  append_null "$BATCH_LIST" "one.txt"
  run_batch 1 1
  run_batch 2 0

  assert_eq "" "$(tr '\0' '\n' < "$BATCH_LIST")" "successful batch clears batch list"
  assert_file_contains "$LOG_FILE" "[Batch 1] Success" "successful batch is logged"
  assert_file_contains "$FAKE_RSYNC_CALLS" "--files-from=$BATCH_LIST" "rsync receives files-from"
}

test_run_batch_failure_records_failed_files() {
  reset_env
  new_workspace batch_failure
  prepare_script_state
  make_fake_rsync 23

  : > "$LOG_FILE"
  append_null "$BATCH_LIST" "bad.txt"
  run_batch 1 1

  assert_file_contains "$FAILED_LIST" "bad.txt" "failed file was recorded"
  assert_file_contains "$FAILED_LIST" "---" "failed batch separator was recorded"
  assert_eq 1 "$(count_failed_batches)" "failed batch count"
}

test_sync_files_batches_and_removes_failed_list_on_success() {
  reset_env
  new_workspace sync_success
  export SYNC_BATCH_SIZE=2
  prepare_script_state
  make_fake_rsync 0

  : > "$LOG_FILE"
  append_null "$SYNC_LIST" "one.txt"
  append_null "$SYNC_LIST" "two.txt"
  append_null "$SYNC_LIST" "three.txt"

  sync_files

  assert_file_contains "$LOG_FILE" "Batches attempted: 2" "sync created two batches"
  assert_file_contains "$FAKE_RSYNC_CALLS" "$SOURCE_DIR/" "rsync receives source path"
  assert_file_missing "$FAILED_LIST" "failed list removed after successful sync"
}

test_sync_files_returns_failure_when_batch_fails() {
  reset_env
  new_workspace sync_failure
  prepare_script_state
  make_fake_rsync 23

  : > "$LOG_FILE"
  append_null "$SYNC_LIST" "bad.txt"

  if sync_files; then
    echo "not ok - sync_files accepted failed batch" >&2
    return 1
  fi

  assert_file_contains "$LOG_FILE" "Failed batch file lists saved to:" "sync failure is logged"
  assert_file_contains "$FAILED_LIST" "bad.txt" "failed sync keeps failed list"
}

test_main_no_work_exits_successfully() {
  reset_env
  new_workspace main_no_work
  printf 'same\n' > "$SOURCE_DIR/same.txt"
  cp -p "$SOURCE_DIR/same.txt" "$TARGET_DIR/same.txt"
  export SYNC_OUTPUT_DIR="$OUTPUT_DIR"

  main "$SOURCE_DIR" "$TARGET_DIR"

  assert_file_contains "$OUTPUT_DIR/sync_folders.log" "No missing or changed files; nothing to sync." "main logs no work"
}

test_main_syncs_missing_file_integration() {
  reset_env
  new_workspace main_sync
  printf 'hello\n' > "$SOURCE_DIR/hello.txt"
  export SYNC_OUTPUT_DIR="$OUTPUT_DIR"
  export SYNC_BATCH_SIZE=1

  main "$SOURCE_DIR" "$TARGET_DIR"

  assert_file_contains "$TARGET_DIR/hello.txt" "hello" "main copied missing file"
  assert_file_contains "$OUTPUT_DIR/sync_folders.log" "Sync complete." "main logged completion"
}

test_count_failed_batches_handles_missing_file() {
  reset_env
  new_workspace missing_failed_list
  prepare_script_state
  rm -f "$FAILED_LIST"

  assert_eq 0 "$(count_failed_batches)" "missing failed file has zero failures"
}

run_test() {
  local name=$1

  if (set -e; "$name"); then
    echo "ok - $name"
    ((PASS_COUNT += 1))
  else
    echo "not ok - $name" >&2
    ((FAIL_COUNT += 1))
  fi
}

run_test test_validate_args_rejects_bad_input
run_test test_configure_normalizes_paths_and_validates_options
run_test test_files_differ_detects_missing_equal_size_and_mtime
run_test test_file_stat_linux_fallbacks
run_test test_compute_differences_and_report
run_test test_write_diff_report_prints_none_for_empty_lists
run_test test_run_batch_success_and_zero_batch
run_test test_run_batch_failure_records_failed_files
run_test test_sync_files_batches_and_removes_failed_list_on_success
run_test test_sync_files_returns_failure_when_batch_fails
run_test test_main_syncs_missing_file_integration
run_test test_main_no_work_exits_successfully
run_test test_count_failed_batches_handles_missing_file

echo "passed: $PASS_COUNT"
echo "failed: $FAIL_COUNT"

if ((FAIL_COUNT > 0)); then
  exit 1
fi
