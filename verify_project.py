"""Reproducible local verification for LibraAI (no external services required)."""
from __future__ import annotations
import compileall
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main() -> int:
    print("LibraAI local verification")
    print("=========================")
    print("[1/3] Compiling Python sources...")
    compiled = compileall.compile_dir(str(ROOT), quiet=1, force=True,
                                      rx=re.compile(r"(^|[\\/])(\.venv|venv|__pycache__)([\\/]|$)"))
    if not compiled:
        print("FAIL: Python compilation failed.")
        return 1
    print("PASS: Python compilation succeeded.")

    print("[2/3] Running unit tests...")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-p", "test_*.py", "-q"],
        cwd=ROOT,
    )
    if result.returncode:
        print("FAIL: Unit tests failed.")
        return result.returncode
    print("PASS: Unit tests succeeded.")

    print("[3/3] Checking launch gate (expected to be blocked until configured)...")
    audit = subprocess.run(
        [sys.executable, "launch_audit.py", "--json"],
        cwd=ROOT, text=True, capture_output=True,
    )
    try:
        report = json.loads(audit.stdout)
    except json.JSONDecodeError:
        print("FAIL: Launch audit did not return valid JSON.")
        if audit.stderr:
            print(audit.stderr)
        return 1
    print(f"Launch readiness: {report.get('passed')}/{report.get('total')} checks passed.")
    print("Production-ready:", "YES" if report.get("production_ready") else "NO")
    if not report.get("production_ready"):
        print("NOTE: This is an honest release blocker, not a unit-test failure.")
        for check in report.get("checks", []):
            if not check.get("passed"):
                print(f"  BLOCK {check.get('id')}: {check.get('detail')}")
    print("Local verification complete.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
