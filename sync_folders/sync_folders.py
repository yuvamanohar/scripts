#!/usr/bin/env python3
"""Sync missing or changed files from one folder to another."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence, TextIO

DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BATCH_SIZES = (3, 2, 1)


@dataclass(frozen=True)
class SyncConfig:
    source: Path
    target: Path
    output_dir: Path
    batch_size: int
    max_retries: int
    retry_batch_sizes: tuple[int, ...]
    rsync_bin: str

    @property
    def log_file(self) -> Path:
        return self.output_dir / "sync_folders.log"

    @property
    def diff_report(self) -> Path:
        return self.output_dir / "diff_files.txt"

    @property
    def failed_list(self) -> Path:
        return self.output_dir / "failed_files.txt"


@dataclass(frozen=True)
class DifferenceResult:
    total_files: int
    missing: tuple[Path, ...]
    changed: tuple[Path, ...]

    @property
    def sync_paths(self) -> tuple[Path, ...]:
        return self.missing + self.changed


class SyncError(RuntimeError):
    """Raised when sync validation or execution fails."""


class Logger:
    def __init__(self, log_file: Path, stream: TextIO = sys.stdout) -> None:
        self.log_file = log_file
        self.stream = stream

    def reset(self) -> None:
        self.log_file.write_text("")

    def log(self, message: str) -> None:
        line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {message}"
        print(line, file=self.stream)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(f"{line}\n")


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value}") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value}")
    return parsed


def positive_int_tuple(value: str) -> tuple[int, ...]:
    try:
        values = tuple(positive_int(part.strip()) for part in value.split(",") if part.strip())
    except argparse.ArgumentTypeError:
        raise

    if not values:
        raise argparse.ArgumentTypeError(f"must contain at least one positive integer: {value}")
    return values


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def validate_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SyncError(f"{label} does not exist or is not a directory: {path}")


def ensure_target_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise SyncError(f"Target folder exists but is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def build_config(
    source: str | Path,
    target: str | Path,
    *,
    output_dir: str | Path | None = None,
    batch_size: int | None = None,
    max_retries: int | None = None,
    retry_batch_sizes: Sequence[int] | None = None,
    rsync_bin: str | None = None,
    env: os._Environ[str] | dict[str, str] = os.environ,
) -> SyncConfig:
    source_path = normalize_path(source)
    target_path = normalize_path(target)
    output_path = normalize_path(output_dir or env.get("SYNC_OUTPUT_DIR", "."))
    configured_batch_size = batch_size
    if configured_batch_size is None:
        configured_batch_size = positive_int(env.get("SYNC_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))
    configured_max_retries = max_retries
    if configured_max_retries is None:
        configured_max_retries = positive_int(env.get("SYNC_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
    configured_retry_batch_sizes = tuple(retry_batch_sizes or ())
    if not configured_retry_batch_sizes:
        configured_retry_batch_sizes = positive_int_tuple(
            env.get(
                "SYNC_RETRY_BATCH_SIZES",
                ",".join(str(size) for size in DEFAULT_RETRY_BATCH_SIZES),
            )
        )

    config = SyncConfig(
        source=source_path,
        target=target_path,
        output_dir=output_path,
        batch_size=configured_batch_size,
        max_retries=configured_max_retries,
        retry_batch_sizes=configured_retry_batch_sizes,
        rsync_bin=rsync_bin or env.get("RSYNC_BIN", "rsync"),
    )

    validate_directory(config.source, "Source folder")
    ensure_target_directory(config.target)
    validate_directory(config.output_dir, "Output directory")
    if config.batch_size < 1:
        raise SyncError(f"SYNC_BATCH_SIZE must be a positive integer: {config.batch_size}")
    if config.max_retries < 1:
        raise SyncError(f"SYNC_MAX_RETRIES must be a positive integer: {config.max_retries}")
    if any(size < 1 for size in config.retry_batch_sizes):
        raise SyncError(f"SYNC_RETRY_BATCH_SIZES must contain positive integers: {config.retry_batch_sizes}")
    return config


def iter_source_files(source: Path) -> Iterable[Path]:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            yield path


def files_differ(source_file: Path, target_file: Path) -> bool:
    if not target_file.is_file():
        return True

    source_stat = source_file.stat()
    target_stat = target_file.stat()
    return (
        source_stat.st_size != target_stat.st_size
        or int(source_stat.st_mtime) != int(target_stat.st_mtime)
    )


def compute_differences(source: Path, target: Path) -> DifferenceResult:
    missing: list[Path] = []
    changed: list[Path] = []
    total_files = 0

    for source_file in iter_source_files(source):
        total_files += 1
        rel_path = source_file.relative_to(source)
        target_file = target / rel_path

        if not target_file.is_file():
            missing.append(rel_path)
        elif files_differ(source_file, target_file):
            changed.append(rel_path)

    return DifferenceResult(
        total_files=total_files,
        missing=tuple(missing),
        changed=tuple(changed),
    )


def format_path_list(paths: Sequence[Path]) -> str:
    if not paths:
        return "(none)"
    return "\n".join(path.as_posix() for path in paths)


def write_diff_report(report: DifferenceResult, diff_report: Path) -> None:
    contents = (
        f"Missing files ({len(report.missing)}):\n"
        f"{format_path_list(report.missing)}\n\n"
        f"Changed files ({len(report.changed)}):\n"
        f"{format_path_list(report.changed)}\n"
    )
    diff_report.write_text(contents, encoding="utf-8")


def print_diff_summary(
    report: DifferenceResult,
    config: SyncConfig,
    logger: Logger,
    stream: TextIO = sys.stdout,
) -> None:
    logger.log(f"Total source files: {report.total_files}")
    logger.log(f"Missing files: {len(report.missing)}")
    logger.log(f"Changed files: {len(report.changed)}")
    logger.log(f"Diff file list written to: {config.diff_report}")
    print(config.diff_report.read_text(encoding="utf-8"), end="", file=stream)


def batched(paths: Sequence[Path], batch_size: int) -> Iterable[tuple[Path, ...]]:
    for index in range(0, len(paths), batch_size):
        yield tuple(paths[index : index + batch_size])


def write_batch_file(paths: Sequence[Path], batch_file: Path) -> None:
    payload = b"".join(path.as_posix().encode("utf-8") + b"\0" for path in paths)
    batch_file.write_bytes(payload)


def unique_paths(paths: Sequence[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    unique: list[Path] = []

    for path in paths:
        normalized = Path(path.as_posix())
        key = normalized.as_posix()
        if key not in seen:
            seen.add(key)
            unique.append(normalized)

    return tuple(unique)


def append_failed_paths(failed_list: Path, paths: Sequence[Path]) -> None:
    with failed_list.open("a", encoding="utf-8") as handle:
        for path in paths:
            handle.write(f"{path.as_posix()}\n")


def read_failed_paths(failed_list: Path) -> tuple[Path, ...]:
    if not failed_list.exists():
        return ()

    paths = [
        Path(line)
        for line in failed_list.read_text(encoding="utf-8").splitlines()
        if line and line != "---"
    ]
    return unique_paths(paths)


def write_failed_paths(failed_list: Path, paths: Sequence[Path]) -> None:
    unresolved = unique_paths(paths)
    if not unresolved:
        failed_list.unlink(missing_ok=True)
        return

    contents = "".join(f"{path.as_posix()}\n" for path in unresolved)
    failed_list.write_text(contents, encoding="utf-8")


def paths_still_unresolved(config: SyncConfig, paths: Sequence[Path]) -> tuple[Path, ...]:
    unresolved: list[Path] = []

    for path in unique_paths(paths):
        try:
            if files_differ(config.source / path, config.target / path):
                unresolved.append(path)
        except OSError:
            unresolved.append(path)

    return tuple(unresolved)


def refresh_failed_paths(config: SyncConfig, paths: Sequence[Path]) -> tuple[Path, ...]:
    unresolved = paths_still_unresolved(config, paths)
    write_failed_paths(config.failed_list, unresolved)
    return unresolved


def rsync_command(config: SyncConfig, batch_file: Path) -> list[str]:
    return [
        config.rsync_bin,
        "-av",
        "--partial",
        f"--files-from={batch_file}",
        "--from0",
        f"{config.source}/",
        f"{config.target}/",
    ]


def run_rsync(config: SyncConfig, paths: Sequence[Path], logger: Logger) -> int:
    if not paths:
        return 0

    with tempfile.NamedTemporaryFile() as batch_handle:
        batch_file = Path(batch_handle.name)
        write_batch_file(paths, batch_file)
        command = rsync_command(config, batch_file)

        with config.log_file.open("a", encoding="utf-8") as log_handle:
            try:
                result = subprocess.run(
                    command,
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
            except OSError as exc:
                logger.log(f"rsync failed to start: {exc}")
                return 1

    return result.returncode


def run_batch(
    config: SyncConfig,
    batch_number: int,
    paths: Sequence[Path],
    logger: Logger,
) -> bool:
    if not paths:
        return True

    logger.log(f"[Batch {batch_number}] Syncing {len(paths)} file(s)")
    returncode = run_rsync(config, paths, logger)

    if returncode == 0:
        logger.log(f"[Batch {batch_number}] Success")
        return True

    logger.log(
        f"[Batch {batch_number}] Failed with rsync exit code {returncode}; "
        f"queued {len(paths)} file(s) for retry in {config.failed_list}"
    )
    append_failed_paths(config.failed_list, paths)
    return False


def retry_batch_size(config: SyncConfig, attempt: int) -> int:
    index = min(attempt - 1, len(config.retry_batch_sizes) - 1)
    return config.retry_batch_sizes[index]


def retry_failed_files(config: SyncConfig, logger: Logger) -> tuple[Path, ...]:
    candidates = read_failed_paths(config.failed_list)
    if not candidates:
        config.failed_list.unlink(missing_ok=True)
        return ()

    for attempt in range(1, config.max_retries + 1):
        unresolved = refresh_failed_paths(config, candidates)
        if not unresolved:
            logger.log("Retry verification: all failed file candidates are already synced.")
            return ()

        batch_size = retry_batch_size(config, attempt)
        logger.log(
            f"Retry attempt {attempt}/{config.max_retries}: "
            f"syncing {len(unresolved)} unresolved file(s) in batch(es) of {batch_size}"
        )
        returncodes = [
            run_rsync(config, retry_paths, logger)
            for retry_paths in batched(unresolved, batch_size)
        ]

        candidates = refresh_failed_paths(config, unresolved)
        if not candidates:
            logger.log(f"Retry attempt {attempt}/{config.max_retries}: success")
            return ()

        failed_retry_batches = sum(1 for returncode in returncodes if returncode != 0)
        logger.log(
            f"Retry attempt {attempt}/{config.max_retries}: "
            f"{failed_retry_batches} retry batch(es) failed; "
            f"{len(candidates)} file(s) still unresolved"
        )
        if attempt < config.max_retries:
            time.sleep(min(attempt, 3))

    return read_failed_paths(config.failed_list)


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

    return sync_files(config, report.sync_paths, logger)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
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
        help="directory for log/report files; defaults to SYNC_OUTPUT_DIR or current directory",
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


if __name__ == "__main__":
    raise SystemExit(main())
