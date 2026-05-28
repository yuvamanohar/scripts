from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence, TextIO

from .config import SyncConfig
from .diff import DifferenceResult
from .logging import Logger


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
    logger.log(f"Compared source files: {report.total_files}")
    logger.log(f"Missing files: {len(report.missing)}")
    logger.log(f"Changed files: {len(report.changed)}")
    logger.log(f"Diff file list written to: {config.diff_report}")
    print(config.diff_report.read_text(encoding="utf-8"), end="", file=stream)
