from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, TextIO

from .config import SyncConfig
from .diff import compute_differences
from .logging import Logger
from .report import print_diff_summary, write_diff_report
from .rsync import batched, read_failed_paths, retry_failed_files, run_batch


def sync_files(config: SyncConfig, paths: Sequence[Path], logger: Logger) -> int:
    logger.log("Syncing files from source to target...")
    config.failed_list.write_text("", encoding="utf-8")
    batch_count = 0
    failed_batch_count = 0

    for batch_count, batch_paths in enumerate(batched(paths, config.batch_size), start=1):
        if not run_batch(config, batch_count, batch_paths, logger):
            failed_batch_count += 1

    failed_paths = read_failed_paths(config.failed_list)
    logger.log(f"Batches attempted: {batch_count}")
    logger.log(f"Failed batches: {failed_batch_count}")

    if failed_paths:
        logger.log(f"Retrying failed file candidates from: {config.failed_list}")
        failed_paths = retry_failed_files(config, logger)

    if failed_paths:
        logger.log(f"Unresolved failed file list saved to: {config.failed_list}")
        return 1

    config.failed_list.unlink(missing_ok=True)
    logger.log("Sync complete.")
    return 0


def sync_folders(config: SyncConfig, stream: TextIO = sys.stdout) -> int:
    logger = Logger(config.log_file, stream)
    logger.reset()
    logger.log("Computing file differences (missing or changed) using size+mtime...")

    report = compute_differences(config.source, config.target)
    write_diff_report(report, config.diff_report)
    print_diff_summary(report, config, logger, stream)

    if not report.sync_paths:
        logger.log("No missing or changed files; nothing to sync.")
        return 0

    if config.dry_run:
        sync_count = len(report.sync_paths)
        file_label = "file" if sync_count == 1 else "files"
        logger.log(f"Dry run enabled; {sync_count} {file_label} would be synced.")
        return 0

    return sync_files(config, report.sync_paths, logger)
