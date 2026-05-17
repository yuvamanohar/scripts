#!/usr/bin/env bash
# Author: Yuva

set -euo pipefail

DEFAULT_BATCH_SIZE=2
SCRIPT_NAME=$(basename "$0")

usage() {
  echo "Usage: $SCRIPT_NAME <source_folder> <target_folder>" >&2
}

fail() {
  echo "$*" >&2
  return 1
}

normalize_path() {
  local path=$1
  printf '%s\n' "${path%/}"
}

validate_args() {
  if [[ $# -ne 2 ]]; then
    usage
    return 1
  fi

  if [[ ! -d "$1" ]]; then
    fail "Source folder does not exist or is not a directory: $1"
    return 1
  fi

  if [[ ! -d "$2" ]]; then
    fail "Target folder does not exist or is not a directory: $2"
    return 1
  fi
}

configure() {
  SOURCE=$(normalize_path "$1")
  TARGET=$(normalize_path "$2")
  OUTPUT_DIR=$(normalize_path "${SYNC_OUTPUT_DIR:-.}")
  BATCH_SIZE=${SYNC_BATCH_SIZE:-$DEFAULT_BATCH_SIZE}
  RSYNC_BIN=${RSYNC_BIN:-rsync}

  if [[ ! -d "$OUTPUT_DIR" ]]; then
    fail "Output directory does not exist or is not a directory: $OUTPUT_DIR"
    return 1
  fi

  if ! [[ "$BATCH_SIZE" =~ ^[1-9][0-9]*$ ]]; then
    fail "SYNC_BATCH_SIZE must be a positive integer: $BATCH_SIZE"
    return 1
  fi

  FAILED_LIST="$OUTPUT_DIR/failed_files.txt"
  LOG_FILE="$OUTPUT_DIR/sync_folders.log"
  DIFF_REPORT="$OUTPUT_DIR/diff_files.txt"
}

make_temp_files() {
  BATCH_LIST=$(mktemp)
  SYNC_LIST=$(mktemp)
  MISSING_LIST=$(mktemp)
  CHANGED_LIST=$(mktemp)
}

cleanup() {
  rm -f "${BATCH_LIST:-}" "${SYNC_LIST:-}" "${MISSING_LIST:-}" "${CHANGED_LIST:-}"
}

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

file_size() {
  if stat -f %z "$1" >/dev/null 2>&1; then
    stat -f %z "$1"
  else
    stat -c %s "$1"
  fi
}

file_mtime() {
  if stat -f %m "$1" >/dev/null 2>&1; then
    stat -f %m "$1"
  else
    stat -c %Y "$1"
  fi
}

files_differ() {
  local source_file=$1
  local target_file=$2
  local src_size
  local tgt_size
  local src_mtime
  local tgt_mtime

  if [[ ! -f "$target_file" ]]; then
    return 0
  fi

  src_size=$(file_size "$source_file")
  tgt_size=$(file_size "$target_file")
  src_mtime=$(file_mtime "$source_file")
  tgt_mtime=$(file_mtime "$target_file")

  [[ $src_size -ne $tgt_size || $src_mtime -ne $tgt_mtime ]]
}

append_null() {
  local file=$1
  local value=$2
  printf '%s\0' "$value" >> "$file"
}

reset_output_files() {
  : > "$SYNC_LIST"
  : > "$MISSING_LIST"
  : > "$CHANGED_LIST"
  : > "$DIFF_REPORT"
}

record_missing_file() {
  local rel_path=$1
  ((missing_count += 1))
  append_null "$SYNC_LIST" "$rel_path"
  append_null "$MISSING_LIST" "$rel_path"
}

record_changed_file() {
  local rel_path=$1
  ((changed_count += 1))
  append_null "$SYNC_LIST" "$rel_path"
  append_null "$CHANGED_LIST" "$rel_path"
}

compute_differences() {
  missing_count=0
  changed_count=0
  total_files=0
  reset_output_files

  while IFS= read -r -d '' file; do
    ((total_files += 1))
    rel_path=${file#"$SOURCE"/}

    if [[ ! -f "$TARGET/$rel_path" ]]; then
      record_missing_file "$rel_path"
      continue
    fi

    if files_differ "$file" "$TARGET/$rel_path"; then
      record_changed_file "$rel_path"
    fi
  done < <(find "$SOURCE" -type f -print0)
}

write_null_list_or_none() {
  local count=$1
  local list_file=$2

  if [[ $count -eq 0 ]]; then
    echo "(none)"
  else
    tr '\0' '\n' < "$list_file"
  fi
}

write_diff_report() {
  {
    echo "Missing files ($missing_count):"
    write_null_list_or_none "$missing_count" "$MISSING_LIST"
    echo
    echo "Changed files ($changed_count):"
    write_null_list_or_none "$changed_count" "$CHANGED_LIST"
  } > "$DIFF_REPORT"
}

print_diff_summary() {
  log "Total source files: $total_files"
  log "Missing files: $missing_count"
  log "Changed files: $changed_count"
  log "Diff file list written to: $DIFF_REPORT"
  cat "$DIFF_REPORT"
}

has_sync_work() {
  [[ -s "$SYNC_LIST" ]]
}

run_batch() {
  local batch_number=$1
  local batch_file_count=$2

  if [[ $batch_file_count -eq 0 ]]; then
    return 0
  fi

  log "[Batch $batch_number] Syncing $batch_file_count file(s)"

  if "$RSYNC_BIN" -av --partial --files-from="$BATCH_LIST" --from0 "$SOURCE/" "$TARGET/" >> "$LOG_FILE" 2>&1; then
    log "[Batch $batch_number] Success"
  else
    log "[Batch $batch_number] Failed; recording batch file list to $FAILED_LIST"
    tr '\0' '\n' < "$BATCH_LIST" >> "$FAILED_LIST"
    echo "---" >> "$FAILED_LIST"
  fi

  : > "$BATCH_LIST"
}

sync_files() {
  local batch_count=0
  local batch_file_count=0
  local failed_count
  local rel_path

  log "Syncing files from source to target..."
  : > "$FAILED_LIST"

  while IFS= read -r -d '' rel_path; do
    append_null "$BATCH_LIST" "$rel_path"
    ((batch_file_count += 1))

    if ((batch_file_count == BATCH_SIZE)); then
      ((batch_count += 1))
      run_batch "$batch_count" "$batch_file_count"
      batch_file_count=0
    fi
  done < "$SYNC_LIST"

  if ((batch_file_count > 0)); then
    ((batch_count += 1))
    run_batch "$batch_count" "$batch_file_count"
  fi

  failed_count=$(count_failed_batches)
  log "Batches attempted: $batch_count"
  log "Failed batches: $failed_count"

  if ((failed_count > 0)); then
    log "Failed batch file lists saved to: $FAILED_LIST"
    return 1
  fi

  rm -f "$FAILED_LIST"
  log "Sync complete."
}

count_failed_batches() {
  if [[ ! -f "$FAILED_LIST" ]]; then
    echo 0
    return
  fi

  grep -c '^---$' "$FAILED_LIST" || true
}

main() {
  validate_args "$@"
  configure "$1" "$2"
  make_temp_files
  trap cleanup EXIT

  : > "$LOG_FILE"
  log "Computing file differences (missing or changed) using size+mtime..."
  compute_differences
  write_diff_report
  print_diff_summary

  if ! has_sync_work; then
    log "No missing or changed files; nothing to sync."
    return 0
  fi

  sync_files
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  main "$@"
fi
