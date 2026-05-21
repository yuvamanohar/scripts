from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DifferenceResult:
    total_files: int
    missing: tuple[Path, ...]
    changed: tuple[Path, ...]

    @property
    def sync_paths(self) -> tuple[Path, ...]:
        return self.missing + self.changed


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
