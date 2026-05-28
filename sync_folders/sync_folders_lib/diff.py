from __future__ import annotations

from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class DifferenceResult:
    total_files: int
    missing: tuple[Path, ...]
    changed: tuple[Path, ...]

    @property
    def sync_paths(self) -> tuple[Path, ...]:
        return self.missing + self.changed


def clean_exclude_pattern(pattern: str) -> str:
    cleaned = pattern.strip().replace("\\", "/").lstrip("/")
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned


def path_matches_pattern(rel_path: Path, pattern: str) -> bool:
    normalized = clean_exclude_pattern(pattern)
    if not normalized:
        return False

    rel_posix = rel_path.as_posix()
    is_directory_pattern = normalized.endswith("/")
    normalized = normalized.rstrip("/")
    parts = rel_path.parts

    if "/" in normalized:
        return (
            fnmatch.fnmatchcase(rel_posix, normalized)
            or rel_posix.startswith(f"{normalized}/")
        )

    if is_directory_pattern:
        return any(part == normalized for part in parts)
    return any(fnmatch.fnmatchcase(part, normalized) for part in parts)


def is_excluded_path(rel_path: Path, exclude_patterns: Sequence[str]) -> bool:
    return any(path_matches_pattern(rel_path, pattern) for pattern in exclude_patterns)


def iter_source_files(
    source: Path,
    exclude_patterns: Sequence[str] = (),
) -> Iterable[Path]:
    for root, dir_names, file_names in os.walk(source):
        root_path = Path(root)
        rel_root = root_path.relative_to(source)

        dir_names[:] = sorted(
            dirname
            for dirname in dir_names
            if not is_excluded_path(rel_root / dirname, exclude_patterns)
        )

        for file_name in sorted(file_names):
            file_path = root_path / file_name
            rel_path = file_path.relative_to(source)
            if file_path.is_file() and not is_excluded_path(rel_path, exclude_patterns):
                yield file_path


def files_differ(source_file: Path, target_file: Path) -> bool:
    if not target_file.is_file():
        return True

    source_stat = source_file.stat()
    target_stat = target_file.stat()
    return (
        source_stat.st_size != target_stat.st_size
        or int(source_stat.st_mtime) != int(target_stat.st_mtime)
    )


def compute_differences(
    source: Path,
    target: Path,
    exclude_patterns: Sequence[str] = (),
) -> DifferenceResult:
    missing: list[Path] = []
    changed: list[Path] = []
    total_files = 0

    for source_file in iter_source_files(source, exclude_patterns):
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
