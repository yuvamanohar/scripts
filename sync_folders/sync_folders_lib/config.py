from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BATCH_SIZES = (3, 2, 1)
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "out"
DEFAULT_EXCLUDE_PATTERNS = (
    ".DS_Store",
    "._*",
    ".Trash/",
    ".Trashes/",
    ".Spotlight-V100/",
    ".fseventsd/",
    "TemporaryItems/",
    "Thumbs.db",
    "desktop.ini",
    "$RECYCLE.BIN/",
)


@dataclass(frozen=True)
class SyncConfig:
    source: Path
    target: Path
    output_dir: Path
    batch_size: int
    max_retries: int
    retry_batch_sizes: tuple[int, ...]
    rsync_bin: str
    dry_run: bool = False
    default_excludes: bool = True
    exclude_patterns: tuple[str, ...] = ()

    @property
    def log_file(self) -> Path:
        return self.output_dir / "sync_folders.log"

    @property
    def diff_report(self) -> Path:
        return self.output_dir / "diff_files.txt"

    @property
    def failed_list(self) -> Path:
        return self.output_dir / "failed_files.txt"

    @property
    def effective_exclude_patterns(self) -> tuple[str, ...]:
        if self.default_excludes:
            return DEFAULT_EXCLUDE_PATTERNS + self.exclude_patterns
        return self.exclude_patterns


class SyncError(RuntimeError):
    """Raised when sync validation or execution fails."""


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value}") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {value}")
    return parsed


def positive_int_tuple(value: str) -> tuple[int, ...]:
    values = tuple(positive_int(part.strip()) for part in value.split(",") if part.strip())

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


def ensure_output_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise SyncError(f"Output directory exists but is not a directory: {path}")
    path.mkdir(parents=True, exist_ok=True)


def read_exclude_patterns(path: str | Path) -> tuple[str, ...]:
    exclude_file = normalize_path(path)
    if not exclude_file.is_file():
        raise SyncError(f"Exclude file does not exist or is not a file: {exclude_file}")

    patterns = []
    for line in exclude_file.read_text(encoding="utf-8").splitlines():
        pattern = line.strip()
        if pattern and not pattern.startswith("#"):
            patterns.append(pattern)
    return tuple(patterns)


def build_config(
    source: str | Path,
    target: str | Path,
    *,
    output_dir: str | Path | None = None,
    batch_size: int | None = None,
    max_retries: int | None = None,
    retry_batch_sizes: Sequence[int] | None = None,
    rsync_bin: str | None = None,
    dry_run: bool = False,
    default_excludes: bool = True,
    exclude_patterns: Sequence[str] | None = None,
    exclude_files: Sequence[str | Path] | None = None,
    env: os._Environ[str] | dict[str, str] = os.environ,
) -> SyncConfig:
    source_path = normalize_path(source)
    target_path = normalize_path(target)
    output_path = normalize_path(output_dir or env.get("SYNC_OUTPUT_DIR", DEFAULT_OUTPUT_DIR))
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
    configured_exclude_patterns = tuple(exclude_patterns or ())
    for exclude_file in exclude_files or ():
        configured_exclude_patterns += read_exclude_patterns(exclude_file)

    config = SyncConfig(
        source=source_path,
        target=target_path,
        output_dir=output_path,
        batch_size=configured_batch_size,
        max_retries=configured_max_retries,
        retry_batch_sizes=configured_retry_batch_sizes,
        rsync_bin=rsync_bin or env.get("RSYNC_BIN", "rsync"),
        dry_run=dry_run,
        default_excludes=default_excludes,
        exclude_patterns=configured_exclude_patterns,
    )

    validate_directory(config.source, "Source folder")
    if config.dry_run:
        if config.target.exists() and not config.target.is_dir():
            raise SyncError(f"Target folder exists but is not a directory: {config.target}")
    else:
        ensure_target_directory(config.target)
    ensure_output_directory(config.output_dir)
    if config.batch_size < 1:
        raise SyncError(f"SYNC_BATCH_SIZE must be a positive integer: {config.batch_size}")
    if config.max_retries < 1:
        raise SyncError(f"SYNC_MAX_RETRIES must be a positive integer: {config.max_retries}")
    if any(size < 1 for size in config.retry_batch_sizes):
        raise SyncError(f"SYNC_RETRY_BATCH_SIZES must contain positive integers: {config.retry_batch_sizes}")
    return config
