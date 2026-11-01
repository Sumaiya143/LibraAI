"""Deterministic production configuration audit; never performs live provider calls.

Usage:
  python production_preflight.py                 # report findings, exit 0
  python production_preflight.py --strict        # exit non-zero for blockers
"""
from __future__ import annotations

import argparse
import json
import os
import ipaddress
import re
from typing import Mapping, Any
from urllib.parse import urlsplit

PLACEHOLDER_MARKERS = ("replace_with", "changeme", "your_", "example", "placeholder", "dev-only")


def _value(env: Mapping[str, str], key: str) -> str:
    return str(env.get(key, "")).strip()


def _yes(env: Mapping[str, str], key: str) -> bool:
    return _value(env, key).lower() == "yes"


def _check(check_id: str, title: str, status: str, detail: str, severity: str = "blocker") -> dict[str, str]:
    return {"id": check_id, "title": title, "status": status, "severity": severity, "detail": detail}



def valid_public_url(value: str) -> bool:
    """Validate a public HTTPS origin, rejecting local/private/reserved hosts."""
    try:
        parsed = urlsplit(str(value or "").strip())
        port = parsed.port
        host = parsed.hostname
    except (ValueError, UnicodeError):
        return False
    if (parsed.scheme.lower() != "https" or not host or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")
            or port not in (None, 443) or host.endswith(".")):
        return False
    host_lower = host.rstrip(".").lower()
    if host_lower in {"localhost", "localhost.localdomain"}:
        return False
    try:
        address = ipaddress.ip_address(host_lower)
        return address.is_global
    except ValueError:
        # Numeric dotted hosts must be valid IP literals, never DNS fallbacks.
        if re.fullmatch(r"[0-9.]+", host_lower):
            return False
    try:
        ascii_host = host_lower.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return False
    if len(ascii_host) > 253 or "." not in ascii_host:
        return False
    labels = ascii_host.split(".")
    if any(not label or len(label) > 63 or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?", label) for label in labels):
        return False
    if labels[-1] in {"test", "invalid", "localhost", "internal", "local", "onion", "arpa"}:
        return False
    if ascii_host.endswith((".example.test", ".example.invalid", ".internal", ".home.arpa")):
        return False
    return True


def inspect(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Backward-compatible report shape for older launch-gate callers.

    New integrations should use :func:`audit_environment`; this adapter keeps
    legacy tests and tooling fail-closed while exposing no environment values.
    """
    report = audit_environment(env)
    checks: list[dict[str, Any]] = []
    supplied = os.environ if env is None else env
    for item in report["checks"]:
        check_id = "https" if item["id"] == "https-url" else item["id"]
        passed = item["status"] == "pass"
        if check_id == "https":
            public_url = _value(supplied, "LIBRAAI_PUBLIC_URL") or _value(supplied, "PUBLIC_BASE_URL")
            passed = valid_public_url(public_url)
        checks.append({"check": check_id, "passed": bool(passed), "detail": item["detail"]})
    return {"ready": bool(checks) and all(item["passed"] for item in checks), "checks": checks}

def audit_environment(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return a safe, secret-free audit report for the supplied environment."""
    env = os.environ if env is None else env
    production = _value(env, "LIBRAAI_ENV").lower() == "production"
    checks: list[dict[str, str]] = []

    secret = _value(env, "SECRET_KEY")
    secret_ok = len(secret) >= 32 and not any(marker in secret.lower() for marker in PLACEHOLDER_MARKERS)
    checks.append(_check("secret-key", "Strong application secret", "pass" if secret_ok else "blocker",
                         "Secret length and placeholder pattern checked; secret value is never returned." if secret_ok else
                         "Set SECRET_KEY to a unique random value of at least 32 characters; do not reuse the example value."))

    debug = _value(env, "LIBRAAI_DEBUG").lower()
    debug_ok = debug in ("0", "false", "no", "off", "")
    checks.append(_check("debug", "Debug mode disabled", "pass" if debug_ok else "blocker",
                         "Debug mode is disabled." if debug_ok else "Set LIBRAAI_DEBUG=0 before production."))

    public_url = _value(env, "LIBRAAI_PUBLIC_URL") or _value(env, "PUBLIC_BASE_URL")
    try:
        parsed_url = urlsplit(public_url)
        url_port = parsed_url.port
    except ValueError:
        parsed_url, url_port = urlsplit(""), None
    https_ok = (parsed_url.scheme == "https" and bool(parsed_url.hostname)
                and not parsed_url.username and not parsed_url.password
                and not parsed_url.query and not parsed_url.fragment
                and parsed_url.path in ("", "/") and url_port in (None, 443))
    checks.append(_check("https-url", "Public HTTPS origin", "pass" if https_ok else "blocker",
                         "A syntactically valid HTTPS origin is configured." if https_ok else "Set LIBRAAI_PUBLIC_URL to a valid public HTTPS origin without credentials, query, fragment, or application path."))

    canonical_url = _value(env, "LIBRAAI_PUBLIC_URL")
    legacy_url = _value(env, "PUBLIC_BASE_URL")
    aliases_match = not (canonical_url and legacy_url) or canonical_url.rstrip("/") == legacy_url.rstrip("/")
    checks.append(_check("public-url-alias", "Canonical and legacy URL consistency", "pass" if aliases_match else "blocker",
                         "Configured public URL aliases match." if aliases_match else "Set LIBRAAI_PUBLIC_URL and PUBLIC_BASE_URL to the same HTTPS origin."))

    session_backend = _value(env, "LIBRAAI_SESSION_BACKEND").lower()
    redis_url = _value(env, "REDIS_URL")
    multi_instance = _value(env, "LIBRAAI_MULTI_INSTANCE").lower() in ("1", "true", "yes")
    redis_url_ok = bool(redis_url) and (not production or redis_url.lower().startswith("rediss://"))
    session_ok = session_backend == "sqlite" or (session_backend == "redis" and redis_url_ok)
    checks.append(_check("session-backend", "Persistent session storage backend", "pass" if session_ok else "blocker",
                         "Redis shared sessions are configured; verify connectivity, TLS/authentication and failover in deployment." if session_backend == "redis" and session_ok else
                         "SQLite server-side sessions are configured for single-host deployment." if session_backend == "sqlite" and session_ok else
                         "Choose sqlite for single-host or redis with REDIS_URL for shared sessions."))
    rate_backend = _value(env, "LIBRAAI_RATE_LIMIT_BACKEND").lower() or "memory"
    rate_ok = rate_backend == "memory" or (rate_backend == "redis" and redis_url_ok)
    if multi_instance and (session_backend != "redis" or rate_backend != "redis"):
        rate_ok = False
    checks.append(_check("shared-rate-limit", "Shared atomic rate limiter", "pass" if rate_ok else "blocker",
                         "Redis-backed atomic rate limits configured; verify connectivity and failure alerts." if rate_backend == "redis" and rate_ok else
                         "In-memory rate limiting is single-process only." if rate_backend == "memory" and not multi_instance else
                         "Multi-instance deployments require Redis for both sessions and rate limiting, plus a shared primary database."))
    if multi_instance:
        checks.append(_check("primary-database-scale", "Multi-instance primary database", "blocker",
                             "This codebase still uses SQLite for the primary application database. Redis sessions/rate limits do not make SQLite safe for multi-host writes; migrate application data to PostgreSQL before multi-instance deployment."))

    db_path = _value(env, "LIBRAAI_DB_PATH")
    persistent_db = bool(db_path) and (db_path.startswith("/") or db_path.startswith("\\\\"))
    checks.append(_check("database-path", "Explicit persistent database path", "pass" if persistent_db else "blocker",
                         "Database path is absolute." if persistent_db else "Set LIBRAAI_DB_PATH to an absolute path on a persistent volume; verify volume durability separately."))

    ssl_ok = all(_value(env, key) for key in ("SSLCOMMERZ_STORE_ID", "SSLCOMMERZ_STORE_PASSWORD"))
    bkash_ok = all(_value(env, key) for key in ("BKASH_USERNAME", "BKASH_PASSWORD", "BKASH_APP_KEY", "BKASH_APP_SECRET"))
    payment_verified = (_yes(env, "LIBRAAI_LIVE_PAYMENT_E2E_VERIFIED") and
                        _yes(env, "LIBRAAI_GATEWAY_E2E_VERIFIED") and
                        _value(env, "SSLCOMMERZ_SANDBOX").lower() == "false" and
                        _value(env, "BKASH_SANDBOX").lower() == "false" and ssl_ok and bkash_ok)
    checks.append(_check("live-payments", "Live payment credentials and verification", "pass" if payment_verified else "blocker",
                         "Credentials are present and operator verification flags are set; live transactions must still be confirmed in provider dashboards." if payment_verified else
                         "Provider approval, production credentials, HTTPS callbacks, sandbox tests, and explicitly recorded live end-to-end verification are required."))

    cloud_ok = (_value(env, "LIBRAAI_STORAGE_BACKEND").lower() in ("s3", "minio") and
                all(_value(env, key) for key in ("LIBRAAI_STORAGE_BUCKET", "LIBRAAI_STORAGE_KEY", "LIBRAAI_STORAGE_SECRET")))
    checks.append(_check("private-storage", "Configured private object storage", "pass" if cloud_ok else "blocker",
                         "S3/MinIO settings are present; permissions, encryption, lifecycle and restore still need live verification." if cloud_ok else
                         "Configure private S3/MinIO bucket credentials and verify access policies, encryption, lifecycle and recovery."))
    storage_restore_ok = _yes(env, "LIBRAAI_STORAGE_RESTORE_VERIFIED")
    checks.append(_check("storage-restore", "Private storage access and restore verification", "pass" if storage_restore_ok else "blocker",
                         "Operator attestation exists; retain evidence of private access policy, encryption, lifecycle and recovery tests." if storage_restore_ok else
                         "Run real cloud-storage access-control, encryption, lifecycle and restore tests; a configured bucket alone is not enough."))

    rights_ok = _yes(env, "LIBRAAI_LICENSE_RIGHTS_VERIFIED") and _yes(env, "LIBRAAI_CONTENT_RIGHTS_VERIFIED")
    checks.append(_check("content-rights", "Publisher and audiobook rights attestation", "pass" if rights_ok else "blocker",
                         "Environment flags are set; attach and independently review the underlying agreements." if rights_ok else
                         "Document publisher/author permissions by format, territory, term, distribution and royalty. Flags alone are not legal proof."))

    security_ok = _yes(env, "LIBRAAI_SECURITY_REVIEW_PASSED") and _yes(env, "LIBRAAI_SECURITY_REVIEW_VERIFIED")
    checks.append(_check("security-review", "Independent security review", "pass" if security_ok else "blocker",
                         "Review flags are set; retain the signed report and evidence of remediation." if security_ok else
                         "Complete an independent security assessment, remediate findings and retain the report."))

    backup_ok = _yes(env, "LIBRAAI_BACKUP_RESTORE_VERIFIED")
    checks.append(_check("backup-restore", "Verified backup and restore drill", "pass" if backup_ok else "blocker",
                         "Restore drill flag is set; retain evidence, RPO/RTO and restore logs." if backup_ok else
                         "Configure encrypted scheduled backups and perform a documented restore drill for database and private files."))
    acceptance_ok = _yes(env, "LIBRAAI_PRODUCTION_ACCEPTANCE_PASSED")
    checks.append(_check("production-acceptance", "Full production acceptance suite", "pass" if acceptance_ok else "blocker",
                         "Acceptance attestation is set; preserve CI artifacts for backend, browser E2E, build, integration and recovery runs." if acceptance_ok else
                         "Run a clean dependency install, full backend tests, production frontend build, browser E2E, provider tests and recovery checks."))

    payout_configured = (_value(env, "LIBRAAI_PAYOUT_PROVIDER").lower() == "generic_http" and
                         all(_value(env, key) for key in ("LIBRAAI_PAYOUT_API_URL", "LIBRAAI_PAYOUT_API_KEY", "LIBRAAI_PAYOUT_WEBHOOK_SECRET")))
    payout_url = urlsplit(_value(env, "LIBRAAI_PAYOUT_API_URL")) if _value(env, "LIBRAAI_PAYOUT_API_URL") else urlsplit("")
    payout_https_ok = payout_url.scheme == "https" and bool(payout_url.hostname)
    payout_status = "blocker" if payout_configured and production and not payout_https_ok else "external_dependency"
    payout_detail = ("Generic idempotent HTTP adapter and signed webhook receiver are implemented. Provider contract approval, credentials, sandbox/live transfer, webhook replay and reconciliation evidence remain external." if payout_configured and (not production or payout_https_ok) else
                     "Configured production payout endpoint must use HTTPS." if payout_configured and production and not payout_https_ok else
                     "Automatic payout remains blocked until generic_http endpoint, API key, webhook secret and HTTPS production endpoint are configured. Provider approval and live verification are still required.")
    checks.append(_check("creator-payouts", "Configured disbursement adapter", payout_status, payout_detail, "external"))

    ai_configured = bool(_value(env, "LIBRAAI_LLM_API_KEY") or _value(env, "OPENAI_API_KEY"))
    checks.append(_check("external-ai", "External AI provider", "pass" if ai_configured else "optional",
                         "A server-side AI key is configured; provider connectivity and usage limits require live tests." if ai_configured else
                         "Optional for local fallback; configure a server-side key and verify provider response, timeout and budget controls.", "warning"))

    # False readiness is intentional whenever any blocking condition remains.
    blockers = sum(item["status"] == "blocker" for item in checks)
    externals = sum(item["status"] == "external_dependency" for item in checks)
    return {
        "production_environment": production,
        "status": "blocked" if blockers else ("needs_external_verification" if externals else "configuration_checks_passed"),
        "blocker_count": blockers,
        "external_dependency_count": externals,
        "check_count": len(checks),
        "note": "Configuration-only audit. It cannot prove provider approval, live transactions, legal rights, durable infrastructure, or independent security verification.",
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="exit 1 when blockers or external dependencies remain")
    parser.add_argument("--production-only", action="store_true", help="fail if LIBRAAI_ENV is not production")
    args = parser.parse_args()
    report = audit_environment()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if args.production_only and not report["production_environment"]:
        return 2
    if args.strict and (report["blocker_count"] or report["external_dependency_count"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
