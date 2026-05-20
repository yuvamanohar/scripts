#!/usr/bin/env python3

from __future__ import annotations

import ast
import sys
import trace
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
MODULE = ROOT / "sync_folders.py"
MIN_COVERAGE = 90.0


def executable_lines(path: Path) -> set[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    lines: set[int] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            lines.add(node.lineno)

    return lines


def discover_and_run_tests() -> unittest.result.TestResult:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)


def run_tests() -> tuple[unittest.result.TestResult, float]:
    tracer = trace.Trace(count=True, trace=False, ignoredirs=[sys.prefix, sys.exec_prefix])
    result = tracer.runfunc(discover_and_run_tests)
    counts = tracer.results().counts

    executable = executable_lines(MODULE)
    covered = {line for (filename, line), count in counts.items() if Path(filename) == MODULE and count > 0}
    coverage = (len(executable & covered) / len(executable)) * 100
    return result, coverage


def main() -> int:
    result, coverage = run_tests()
    print(f"coverage - sync_folders.py: {coverage:.2f}%")

    if coverage < MIN_COVERAGE:
        print(f"coverage below {MIN_COVERAGE:.0f}%", file=sys.stderr)
        return 1

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
