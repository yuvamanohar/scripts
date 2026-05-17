#!/usr/bin/env python3
"""Sync missing or changed files from one folder to another."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence, TextIO

DEFAULT_BATCH_SIZE = 2


@dataclass(frozen=True)
class SyncConfig:
    source: Path
    target: Path
    output_dir: Path
    batch_size: int
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


def normalize_path(path: str | Path) -> Path:
    return Path(path).expanduser()


def validate_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise SyncError(f"{label} does not exist or is not a directory: {path}")


def build_config(
    source: str | Path,
    target: str | Path,
    *,
    output_dir: str | Path | None = None,
    batch_size: int | None = None,
    rsync_bin: str | None = None,
    env: os._Environ[str] | dict[str, str] = os.environ,
) -> SyncConfig:
    source_path = normalize_path(source)
    target_path = normalize_path(target)
    output_path = normalize_path(output_dir or env.get("SYNC_OUTPUT_DIR", "."))
    configured_batch_size = batch_size
    if configured_batch_size is None:
        configured_batch_size = positive_int(env.get("SYNC_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))

    config = SyncConfig(
        source=source_path,
        target=target_path,
        output_dir=output_path,
        batch_size=configured_batch_size,
        rsync_bin=rsync_bin or env.get("RSYNC_BIN", "rsync"),
    )

    validate_directory(config.source, "Source folder")
    validate_directory(config.target, "Target folder")
    validate_directory(config.output_dir, "Output directory")
    if config.batch_size < 1:
        raise SyncError(f"SYNC_BATCH_SIZE must be a positive integer: {config.batch_size}")
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
        or source_stat.st_mtime_ns != target_stat.st_mtime_ns
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


def append_failed_batch(failed_list: Path, paths: Sequence[Path]) -> None:
    with failed_list.open("a", encoding="utf-8") as handle:
        for path in paths:
            handle.write(f"{path.as_posix()}\n")
        handle.write("---\n")


def count_failed_batches(failed_list: Path) -> int:
    if not failed_list.exists():
        return 0
    return sum(1 for line in failed_list.read_text(encoding="utf-8").splitlines() if line == "---")


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


def run_batch(
    config: SyncConfig,
    batch_number: int,
    paths: Sequence[Path],
    logger: Logger,
) -> bool:
    if not paths:
        return True

    logger.log(f"[Batch {batch_number}] Syncing {len(paths)} file(s)")

    with tempfile.NamedTemporaryFile() as batch_handle:
        batch_file = Path(batch_handle.name)
        write_batch_file(paths, batch_file)
        command = rsync_command(config, batch_file)

        with config.log_file.open("a", encoding="utf-8") as log_handle:
            result = subprocess.run(
                command,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                check=False,
            )

    if result.returncode == 0:
        logger.log(f"[Batch {batch_number}] Success")
        return True

    logger.log(f"[Batch {batch_number}] Failed; recording batch file list to {config.failed_list}")
    append_failed_batch(config.failed_list, paths)
    return False


def sync_files(config: SyncConfig, paths: Sequence[Path], logger: Logger) -> int:
    logger.log("Syncing files from source to target...")
    config.failed_list.write_text("", encoding="utf-8")
    batch_count = 0

    for batch_count, batch_paths in enumerate(batched(paths, config.batch_size), start=1):
        run_batch(config, batch_count, batch_paths, logger)

    failed_count = count_failed_batches(config.failed_list)
    logger.log(f"Batches attempted: {batch_count}")
    logger.log(f"Failed batches: {failed_count}")

    if failed_count > 0:
        logger.log(f"Failed batch file lists saved to: {config.failed_list}")
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
        help="files per rsync batch; defaults to SYNC_BATCH_SIZE or 2",
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
            rsync_bin=args.rsync_bin,
        )
    except (SyncError, argparse.ArgumentTypeError) as exc:
        print(exc, file=sys.stderr)
        return 1

    return sync_folders(config)


if __name__ == "__main__":
    raise SystemExit(main())
