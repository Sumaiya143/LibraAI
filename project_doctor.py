"""Dependency-free local environment diagnostics for LibraAI.

Reports actionable setup issues without printing environment values or secrets.
Exit status is non-zero only for required local-run prerequisites.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    "frontend/package.json",
    "frontend/app",
    ".env.example",
)
REQUIRED_PYTHON_MODULES = {
    "flask": "Flask web server",
    "werkzeug": "Flask runtime dependency",
    "cryptography": "cryptographic helpers",
}
OPTIONAL_PYTHON_MODULES = {
    "redis": "required only when Redis sessions or rate limiting are enabled",
}


def _module_available(module: str) -> bool:
    """Handle test doubles in sys.modules without crashing find_spec()."""
    loaded = sys.modules.get(module, ...)
    if loaded is not ...:
        if loaded is None:
            return False
        # A test-only ModuleType stub commonly has no __spec__ and no __file__.
        if getattr(loaded, "__spec__", None) is None:
            return bool(getattr(loaded, "__file__", None))
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def inspect_environment(root: Path = ROOT) -> dict:
    root = Path(root)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, str]] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append({"name": "python", "status": "ok" if py_ok else "error",
                   "detail": f"Python {sys.version_info.major}.{sys.version_info.minor}"})
    if not py_ok:
        errors.append("Python 3.10+ is required; Python 3.12+ is recommended.")

    for relative in REQUIRED_FILES:
        exists = (root / relative).exists()
        checks.append({"name": f"file:{relative}", "status": "ok" if exists else "error",
                       "detail": "present" if exists else "missing"})
        if not exists:
            errors.append(f"Required project item is missing: {relative}")

    for module, purpose in REQUIRED_PYTHON_MODULES.items():
        present = _module_available(module)
        checks.append({"name": f"python:{module}", "status": "ok" if present else "error",
                       "detail": "installed" if present else "not installed"})
        if not present:
            errors.append(f"Missing Python dependency {module}; run: python -m pip install -r requirements.txt")

    for module, purpose in OPTIONAL_PYTHON_MODULES.items():
        present = _module_available(module)
        checks.append({"name": f"python:{module}", "status": "ok" if present else "warning",
                       "detail": "installed" if present else purpose})
        if not present and (os.environ.get("LIBRAAI_SESSION_BACKEND", "sqlite").lower() == "redis"
                            or os.environ.get("LIBRAAI_RATE_LIMIT_BACKEND", "memory").lower() == "redis"):
            errors.append("Redis is configured but the Python redis package is missing; install requirements.txt.")
        elif not present:
            warnings.append("Redis is optional for single-host local development.")

    node = shutil.which("node")
    npm = shutil.which("npm")
    checks.append({"name": "node", "status": "ok" if node else "warning",
                   "detail": "available" if node else "not found; frontend cannot run"})
    checks.append({"name": "npm", "status": "ok" if npm else "warning",
                   "detail": "available" if npm else "not found; frontend cannot run"})
    if not node or not npm:
        warnings.append("Install Node.js 20+ (includes npm) to run the Next.js frontend.")

    frontend_lock = root / "frontend/package-lock.json"
    checks.append({"name": "frontend_lockfile", "status": "ok" if frontend_lock.is_file() else "warning",
                   "detail": "present" if frontend_lock.is_file() else "missing; npm install is not fully lockfile-reproducible"})
    if not frontend_lock.is_file():
        warnings.append("frontend/package-lock.json is missing; do not claim deterministic frontend installs until generated and committed.")

    return {"project": "LibraAI", "ok": not errors, "checks": checks,
            "errors": errors, "warnings": warnings}


def main() -> int:
    result = inspect_environment()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
