from __future__ import annotations

import argparse
import sys
from typing import Sequence

from .app import sync_folders
from .config import SyncError, build_config, positive_int, positive_int_tuple


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync missing or changed files from one folder to another.")
    parser.add_argument("source_folder")
    parser.add_argument("target_folder")
    parser.add_argument(
        "--batch-size",
        type=positive_int,
        default=None,
        help="files per rsync batch; defaults to SYNC_BATCH_SIZE or 5",
    )
    parser.add_argument(
        "--max-retries",
        type=positive_int,
        default=None,
        help="retry attempts for failed files; defaults to SYNC_MAX_RETRIES or 3",
    )
    parser.add_argument(
        "--retry-batch-sizes",
        type=positive_int_tuple,
        default=None,
        help="comma-separated retry batch sizes; defaults to SYNC_RETRY_BATCH_SIZES or 3,2,1",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="directory for log/report files; defaults to SYNC_OUTPUT_DIR or sync_folders/out",
    )
    parser.add_argument(
        "--rsync-bin",
        default=None,
        help="rsync executable; defaults to RSYNC_BIN or rsync",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        config = build_config(
            args.source_folder,
            args.target_folder,
            output_dir=args.output_dir,
            batch_size=args.batch_size,
            max_retries=args.max_retries,
            retry_batch_sizes=args.retry_batch_sizes,
            rsync_bin=args.rsync_bin,
        )
    except (SyncError, argparse.ArgumentTypeError) as exc:
        print(exc, file=sys.stderr)
        return 1

    return sync_folders(config)
