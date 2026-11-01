"""Run the complete Python test suite and fail if any test is skipped.

Run this in the supported CI environment after installing requirements.txt.
Platform-specific tests should be executed on the Linux CI runner, where the
project's symlink security checks are expected to be available.
"""
from __future__ import annotations

import sys
import unittest
import importlib.util


def missing_runtime_dependencies(spec_finder=None) -> list[str]:
    """Return required imports that are absent, tolerating test-module stubs."""
    finder = spec_finder or importlib.util.find_spec
    missing = []
    for module in ("flask", "werkzeug"):
        try:
            found = finder(module) is not None
        except (ImportError, ValueError, AttributeError):
            found = False
        if not found:
            missing.append(module)
    return missing


def main() -> int:
    missing = missing_runtime_dependencies()
    if missing:
        print("ERROR: required runtime dependencies are missing: " + ", ".join(missing), file=sys.stderr)
        print("Install them in the active environment with: python -m pip install -r requirements.txt", file=sys.stderr)
        print("No test results were reported; the suite was not started.", file=sys.stderr)
        return 2
    loader = unittest.defaultTestLoader
    suite = loader.discover(start_dir='.', pattern='test_*.py', top_level_dir='.')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(
        f"\nSTRICT TEST SUMMARY: ran={result.testsRun}, "
        f"failures={len(result.failures)}, errors={len(result.errors)}, "
        f"skipped={len(result.skipped)}"
    )
    if result.skipped:
        print('ERROR: skipped tests are not accepted in the release verification suite.', file=sys.stderr)
    if result.failures or result.errors or result.skipped:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
