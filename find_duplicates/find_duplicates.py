#!/usr/bin/env python3
# Author: Yuva

"""
Find duplicate files under a folder.

Features:
- Groups by size then content hash (sha256 by default, md5 optional).
- Optional parallel hashing (--jobs).
- Confirms equality with byte-for-byte compare after hash match.
- Logs duplicates to duplicates.txt and problematic files to unprocessed_files.txt.
- Optional deletion: keep one file per duplicate set based on policy.
"""

import argparse
import concurrent.futures
import hashlib
import os
import sys
from typing import Dict, List, Tuple

CHUNK_SIZE = 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find duplicate files in a folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("root", help="Root folder to scan")
    parser.add_argument(
        "--hash",
        choices=["sha256", "md5"],
        default="sha256",
        help="Hash algorithm for candidate duplicates",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=1,
        help="Skip files smaller than this many bytes",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=None,
        help="Maximum directory depth to scan (0 = only root)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=os.cpu_count() or 4,
        help="Number of parallel workers for hashing",
    )
    parser.add_argument(
        "--delete",
        choices=["first", "newest", "oldest", "shortest"],
        help="Delete duplicates, keeping only one per group using this policy",
    )
    parser.add_argument(
        "--duplicates-file",
        default="duplicates.txt",
        help="Output file listing duplicate groups",
    )
    parser.add_argument(
        "--unprocessed-file",
        default="unprocessed_files.txt",
        help="Output file listing files that could not be processed",
    )
    return parser.parse_args()


def within_depth(root: str, path: str, max_depth: int) -> bool:
    if max_depth is None:
        return True
    rel = os.path.relpath(path, root)
    if rel == ".":
        depth = 0
    else:
        depth = rel.count(os.sep)
    return depth <= max_depth


def gather_files(args: argparse.Namespace):
    size_groups: Dict[int, List[str]] = {}
    unprocessed: List[Tuple[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(args.root):
        if not within_depth(args.root, dirpath, args.max_depth):
            dirnames[:] = []  # prune deeper traversal
            continue
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                st = os.stat(path, follow_symlinks=False)
            except Exception as exc:  # noqa: BLE001
                unprocessed.append((path, f"stat failed: {exc}"))
                continue
            if not os.path.isfile(path):
                continue
            if st.st_size < args.min_size:
                continue
            size_groups.setdefault(st.st_size, []).append(path)
    return size_groups, unprocessed


def hash_file(path: str, algo_name: str) -> Tuple[str, str]:
    h = hashlib.new(algo_name)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return path, h.hexdigest()


def cmp_files(path_a: str, path_b: str) -> bool:
    with open(path_a, "rb") as fa, open(path_b, "rb") as fb:
        while True:
            ba = fa.read(CHUNK_SIZE)
            bb = fb.read(CHUNK_SIZE)
            if ba != bb:
                return False
            if not ba:
                return True


def choose_keep(paths: List[str], policy: str) -> str:
    if policy == "newest":
        return max(paths, key=lambda p: os.stat(p, follow_symlinks=False).st_mtime)
    if policy == "oldest":
        return min(paths, key=lambda p: os.stat(p, follow_symlinks=False).st_mtime)
    if policy == "shortest":
        return min(paths, key=lambda p: (len(p), p))
    return sorted(paths)[0]  # default: first (lexicographic)


def main() -> int:
    args = parse_args()
    root = os.path.abspath(args.root)

    if not os.path.isdir(root):
        print(f"Root folder does not exist or is not a directory: {args.root}", file=sys.stderr)
        return 1

    size_groups, unprocessed = gather_files(args)

    hash_tasks: List[str] = []
    for size, paths in size_groups.items():
        if len(paths) > 1:
            hash_tasks.extend(paths)

    hash_results: Dict[str, str] = {}
    if hash_tasks:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
            future_to_path = {pool.submit(hash_file, p, args.hash): p for p in hash_tasks}
            for future in concurrent.futures.as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    path, digest = future.result()
                    hash_results[path] = digest
                except Exception as exc:  # noqa: BLE001
                    unprocessed.append((path, f"hash failed: {exc}"))

    # Group by hash where size had collisions
    hash_groups: Dict[Tuple[int, str], List[str]] = {}
    for size, paths in size_groups.items():
        if len(paths) < 2:
            continue
        for p in paths:
            digest = hash_results.get(p)
            if digest:
                hash_groups.setdefault((size, digest), []).append(p)

    duplicates: List[List[str]] = []
    # Confirm with byte compare to avoid rare hash collisions
    for (_size, _digest), paths in hash_groups.items():
        if len(paths) < 2:
            continue
        paths_sorted = sorted(paths)
        base = paths_sorted[0]
        confirmed = [base]
        for other in paths_sorted[1:]:
            try:
                if cmp_files(base, other):
                    confirmed.append(other)
                else:
                    unprocessed.append((other, "hash matched but cmp differs"))
            except Exception as exc:  # noqa: BLE001
                unprocessed.append((other, f"cmp failed: {exc}"))
        if len(confirmed) > 1:
            duplicates.append(confirmed)

    deletions: List[Tuple[str, str]] = []  # (kept, removed)
    if args.delete and duplicates:
        for group in duplicates:
            try:
                keep = choose_keep(group, args.delete)
            except Exception as exc:  # noqa: BLE001
                for p in group:
                    unprocessed.append((p, f"keep selection failed: {exc}"))
                continue
            for path in group:
                if path == keep:
                    continue
                try:
                    os.remove(path)
                    deletions.append((keep, path))
                except Exception as exc:  # noqa: BLE001
                    unprocessed.append((path, f"delete failed: {exc}"))

    # Write outputs
    with open(args.duplicates_file, "w", encoding="utf-8") as dup_out:
        for group in duplicates:
            dup_out.write("---\n")
            dup_out.write("\n".join(group))
            dup_out.write("\n")
        dup_out.write(f"Total duplicate sets: {len(duplicates)}\n")
        if deletions:
            dup_out.write(f"Deleted {len(deletions)} file(s).\n")

    if unprocessed:
        with open(args.unprocessed_file, "w", encoding="utf-8") as err_out:
            for path, reason in unprocessed:
                err_out.write(f"{path}\t{reason}\n")

    print(f"Duplicate sets: {len(duplicates)}")
    print(f"Unprocessed files: {len(unprocessed)} (see {args.unprocessed_file} if non-zero)")
    if deletions:
        print(f"Deleted files: {len(deletions)} (kept per policy: {args.delete})")

    return 1 if unprocessed else 0


if __name__ == "__main__":
    sys.exit(main())
