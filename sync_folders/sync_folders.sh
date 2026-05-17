#!/usr/bin/env bash
# Author: Yuva

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <source_folder> <target_folder>" >&2
  exit 1
fi

SOURCE=$1
TARGET=$2

if [[ ! -d "$SOURCE" ]]; then
  echo "Source folder does not exist or is not a directory: $SOURCE" >&2
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  echo "Target folder does not exist or is not a directory: $TARGET" >&2
  exit 1
fi

SOURCE="${SOURCE%/}"
TARGET="${TARGET%/}"
FAILED_LIST="failed_files.txt"
LOG_FILE="sync_folders.log"
DIFF_REPORT="diff_files.txt"
BATCH_SIZE=2
BATCH_LIST=$(mktemp)
SYNC_LIST=$(mktemp)
MISSING_LIST=$(mktemp)
CHANGED_LIST=$(mktemp)

cleanup() {
  rm -f "$BATCH_LIST" "$SYNC_LIST" "$MISSING_LIST" "$CHANGED_LIST"
}

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

run_batch() {
  local batch_number=$1
  local batch_file_count=$2

  if [[ $batch_file_count -eq 0 ]]; then
    return
  fi

  log "[Batch $batch_number] Syncing $batch_file_count file(s)"

  if rsync -av --partial --files-from="$BATCH_LIST" --from0 "$SOURCE/" "$TARGET/" >> "$LOG_FILE" 2>&1; then
    log "[Batch $batch_number] Success"
  else
    log "[Batch $batch_number] Failed; recording batch file list to $FAILED_LIST"
    tr '\0' '\n' < "$BATCH_LIST" >> "$FAILED_LIST"
    echo "---" >> "$FAILED_LIST"
  fi

  : > "$BATCH_LIST"
}

trap cleanup EXIT

> "$LOG_FILE"
log "Computing file differences (missing or changed) using size+mtime..."
missing_count=0
changed_count=0
total_files=0
: > "$SYNC_LIST"
: > "$MISSING_LIST"
: > "$CHANGED_LIST"
: > "$DIFF_REPORT"

while IFS= read -r -d '' file; do
  ((total_files+=1))
  rel_path=${file#"$SOURCE"/}

  if [[ ! -f "$TARGET/$rel_path" ]]; then
    ((missing_count+=1))
    printf '%s\0' "$rel_path" >> "$SYNC_LIST"
    printf '%s\0' "$rel_path" >> "$MISSING_LIST"
    continue
  fi

  src_size=$(stat -f %z "$file")
  tgt_size=$(stat -f %z "$TARGET/$rel_path")
  src_mtime=$(stat -f %m "$file")
  tgt_mtime=$(stat -f %m "$TARGET/$rel_path")

  if [[ $src_size -ne $tgt_size || $src_mtime -ne $tgt_mtime ]]; then
    ((changed_count+=1))
    printf '%s\0' "$rel_path" >> "$SYNC_LIST"
    printf '%s\0' "$rel_path" >> "$CHANGED_LIST"
  fi
done < <(find "$SOURCE" -type f -print0)

log "Total source files: $total_files"
log "Missing files: $missing_count"
log "Changed files: $changed_count"

{
  echo "Missing files ($missing_count):"
  if [[ $missing_count -eq 0 ]]; then
    echo "(none)"
  else
    tr '\0' '\n' < "$MISSING_LIST"
  fi
  echo
  echo "Changed files ($changed_count):"
  if [[ $changed_count -eq 0 ]]; then
    echo "(none)"
  else
    tr '\0' '\n' < "$CHANGED_LIST"
  fi
} > "$DIFF_REPORT"

log "Diff file list written to: $DIFF_REPORT"
cat "$DIFF_REPORT"

if [[ ! -s "$SYNC_LIST" ]]; then
  log "No missing or changed files; nothing to sync."
  exit 0
fi

log "Syncing files from source to target..."
> "$FAILED_LIST"
failed_count=0
processed_count=0
batch_count=0
batch_file_count=0

while IFS= read -r -d '' rel_path; do
  ((processed_count+=1))
  printf '%s\0' "$rel_path" >> "$BATCH_LIST"
  ((batch_file_count+=1))

  if (( batch_file_count == BATCH_SIZE )); then
    ((batch_count+=1))
    run_batch "$batch_count" "$batch_file_count"
    batch_file_count=0
  fi
done < "$SYNC_LIST"

if (( batch_file_count > 0 )); then
  ((batch_count+=1))
  run_batch "$batch_count" "$batch_file_count"
fi

failed_count=$(grep -c '^---$' "$FAILED_LIST" || true)
log "Batches attempted: $batch_count"
log "Failed batches: $failed_count"

if (( failed_count > 0 )); then
  log "Failed batch file lists saved to: $FAILED_LIST"
  exit 1
fi

rm -f "$FAILED_LIST"
log "Sync complete."
