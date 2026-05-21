from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Sequence

from .config import SyncConfig
from .diff import files_differ
from .logging import Logger


def batched(paths: Sequence[Path], batch_size: int) -> list[tuple[Path, ...]]:
    return [
        tuple(paths[index : index + batch_size])
        for index in range(0, len(paths), batch_size)
    ]


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
